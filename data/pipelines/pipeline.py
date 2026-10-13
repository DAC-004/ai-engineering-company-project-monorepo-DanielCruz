"""HealthCore Monthly Clinic Supply Performance Prefect 3 pipeline.

Run from the repository root:

    python data/pipelines/pipeline.py

Intended schedule: first working day of month M, process UTC month M-1.
Requires DATABASE_URL (and SECRET_KEY for Settings) via environment or
``services/api/.env``. Never embed credentials.

Local Prefect does not require PREFECT_API_URL. On Windows, if PREFECT_HOME
is unset, this module uses a short LOCALAPPDATA (or TEMP) ``pf`` directory so
the ephemeral Prefect server can load Alembic files. An explicitly supplied
PREFECT_HOME is preserved.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
for _path in (str(REPO_ROOT), str(API_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_WINDOWS_MAX_PATH = 260
_PREFECT_MIGRATION_TAIL = (
    Path("prefect")
    / "server"
    / "database"
    / "_migrations"
    / "versions"
    / "sqlite"
    / "2022_01_20_115236_9725c1cbee35_initial_migration.py"
)


def _venv_prefect_package() -> Path | None:
    executable = Path(sys.executable).resolve()
    for candidate in (
        executable.parent.parent / "Lib" / "site-packages" / "prefect",
        executable.parent.parent / "lib" / "site-packages" / "prefect",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _sqlite_migrations_need_short_path(package: Path) -> bool:
    """True when any Prefect SQLite Alembic file is unreachable under MAX_PATH.

    The initial migration filename can be short enough to pass a single-file
    check while a later, longer revision name still exceeds Windows MAX_PATH.
    """
    sqlite_versions = (
        package / "server" / "database" / "_migrations" / "versions" / "sqlite"
    )
    try:
        migration_files = [path for path in sqlite_versions.iterdir() if path.suffix == ".py"]
    except OSError:
        return True
    if not migration_files:
        long_migration = package / _PREFECT_MIGRATION_TAIL.relative_to("prefect")
        return len(str(long_migration)) >= _WINDOWS_MAX_PATH or not long_migration.exists()
    return any(len(str(path)) >= _WINDOWS_MAX_PATH or not path.exists() for path in migration_files)


def _ensure_short_prefect_import_path(prefect_home: Path) -> None:
    """Import Prefect from a short junction when the venv path exceeds MAX_PATH.

    Alembic loads migration modules by filesystem path. Windows MAX_PATH makes
    those files invisible under a long ``.venv`` path, which prevents the
    ephemeral Prefect server from starting. A directory junction under the
    short Prefect home keeps orchestration intact without bypassing Prefect tasks.
    """
    package = _venv_prefect_package()
    if package is None:
        return
    if not _sqlite_migrations_need_short_path(package):
        return

    package_root = prefect_home / "pkg"
    if len(str(package_root / _PREFECT_MIGRATION_TAIL)) >= _WINDOWS_MAX_PATH:
        package_root = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "pf" / "pkg"
    junction = package_root / "prefect"
    short_migration = junction / _PREFECT_MIGRATION_TAIL.relative_to("prefect")
    if not short_migration.exists():
        package_root.mkdir(parents=True, exist_ok=True)
        if not junction.exists():
            import _winapi

            _winapi.CreateJunction(str(package), str(junction))
        if not short_migration.exists():
            raise RuntimeError(
                "Prefect Alembic migrations remain unreachable after creating a "
                f"short import path at {junction}"
            )
    package_root_str = str(package_root)
    if sys.path[:1] != [package_root_str]:
        sys.path.insert(0, package_root_str)


def configure_prefect_runtime() -> Path | None:
    """Set a short PREFECT_HOME when needed. Preserve an explicit value."""
    configured_home: Path | None = None
    existing = os.environ.get("PREFECT_HOME")
    if existing:
        configured_home = Path(existing)
        configured_home.mkdir(parents=True, exist_ok=True)
    elif os.name == "nt":
        configured_home = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "pf"
        configured_home.mkdir(parents=True, exist_ok=True)
        os.environ["PREFECT_HOME"] = str(configured_home)
    if os.name == "nt" and configured_home is not None:
        _ensure_short_prefect_import_path(configured_home)
    elif os.name == "nt":
        _ensure_short_prefect_import_path(
            Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "pf"
        )
    return configured_home


configure_prefect_runtime()

from prefect import flow, task  # noqa: E402
from prefect.states import State  # noqa: E402

from app.db.database import get_engine, init_databases  # noqa: E402
from data.pipelines.reporting_store import (  # noqa: E402
    OverlappingPipelineRunError,
    SourceUnavailableError,
    extract_supply_performance_events as read_supply_performance_events,
    finish_pipeline_run,
    get_latest_pipeline_run as read_latest_pipeline_run,
    get_monthly_clinic_supply_performance as read_monthly_clinic_supply_performance,
    get_pipeline_run,
    load_monthly_clinic_supply_performance as write_monthly_clinic_supply_performance,
    start_pipeline_run,
    telemetry_events_available,
)
from data.pipelines.transforms import (  # noqa: E402
    previous_completed_utc_month,
    transform_monthly_clinic_aggregates as compute_monthly_clinic_aggregates,
)

logger = logging.getLogger(__name__)

EVAL_SNAPSHOT_DIR = REPO_ROOT / "data" / "eval"


class PipelineRunFailedError(RuntimeError):
    """Raised when the flow records Failed after a critical stage error."""


def _configure_pipeline_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _sanitize_error(exc: BaseException) -> str:
    """Keep clinic ids and event types; never copy userId, emails, or PHI."""
    message = f"{type(exc).__name__}: {exc}"
    return message[:500]


def _parse_month_start(value: date | str | None) -> date:
    if value is None:
        return previous_completed_utc_month()
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        parsed = value
    else:
        parsed = date.fromisoformat(str(value))
    if parsed.day != 1:
        raise ValueError("month_start must be the first day of a UTC calendar month")
    return parsed


def transform_cache_key(_context: Any, parameters: dict[str, Any]) -> str:
    """Cache key is UTC month_start plus a hash of extracted event_id values.

    A different month or a different extracted event set cannot reuse a cached
    transform. Cached results remain valid for one hour (see cache_expiration).
    """
    month_start = parameters.get("month_start")
    events = parameters.get("events") or []
    event_ids = []
    for event in events:
        if isinstance(event, dict):
            event_ids.append(str(event.get("event_id", "")))
        else:
            event_ids.append(str(event))
    event_ids.sort()
    digest = hashlib.sha256("\0".join(event_ids).encode("utf-8")).hexdigest()
    month_token = str(month_start).replace(":", "-")
    # Filename-safe: Windows cannot persist a result whose key contains ':'.
    return f"healthcore-transform-{month_token}-{digest}"


@task(retries=3, retry_delay_seconds=[5, 15, 45])
def extract_supply_performance_events(month_start: date) -> list[dict[str, Any]]:
    """Read-only extract from telemetry_events for one UTC month.

    Three retries with increasing delays absorb transient PostgreSQL/Supabase
    pooler disconnects without failing the first-working-day board pack.
    """
    engine = get_engine()
    return read_supply_performance_events(engine, month_start)


@task(
    cache_key_fn=transform_cache_key,
    cache_expiration=timedelta(hours=1),
    persist_result=True,
)
def transform_monthly_clinic_aggregates(
    events: list[dict[str, Any]],
    month_start: date,
) -> dict[str, Any]:
    """Compute the four HealthCore KPIs for one clinic-month grain."""
    return compute_monthly_clinic_aggregates(events, month_start)


@task(retries=1, retry_delay_seconds=10)
def load_monthly_clinic_supply_performance(
    transform_result: dict[str, Any],
    run_id: str,
    month_start: date,
) -> int:
    """Transactional upsert of clinic-month rows.

    One retry starts a new transaction after a transient database error. The
    unique (clinic_id, month_start) constraint makes a retry replace numbers
    instead of inserting duplicates.
    """
    engine = get_engine()
    return write_monthly_clinic_supply_performance(
        engine,
        aggregates=transform_result["aggregates"],
        run_id=run_id,
        month_start=month_start,
        max_event_timestamp=transform_result.get("max_event_timestamp"),
    )


@task
def write_eval_snapshot(
    transform_result: dict[str, Any],
    month_start: date,
    snapshot_path: str | None = None,
) -> str:
    """Optional evaluation snapshot. Failure must not stop extract-transform-load."""
    target = (
        Path(snapshot_path)
        if snapshot_path
        else EVAL_SNAPSHOT_DIR / f"monthly_clinic_supply_performance_{month_start.isoformat()}.json"
    )
    payload = {
        "month_start": month_start.isoformat(),
        "records_extracted": transform_result.get("records_extracted", 0),
        "records_rejected": transform_result.get("records_rejected", 0),
        "clinics": [
            {
                "clinic_id": row["clinic_id"],
                "country": row["country"],
                "total_supply_cost": str(row["total_supply_cost"]),
                "supply_consumption_count": row["supply_consumption_count"],
                "critical_stockout_count": row["critical_stockout_count"],
                "expiry_risk_count": row["expiry_risk_count"],
                "currency": row["currency"],
            }
            for row in transform_result.get("aggregates", [])
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(target)


def _handle_optional_snapshot_state(snapshot_state: State) -> None:
    if snapshot_state.is_failed():
        logger.warning(
            "Optional eval snapshot failed; continuing extract-transform-load. "
            "state_name=%s state_type=%s",
            snapshot_state.name,
            snapshot_state.type,
        )
        return
    logger.info("Optional eval snapshot completed: %s", snapshot_state)


@flow(name="extract_clinic_supply_performance_events")
def extract_clinic_supply_performance_events_flow(
    month_start: date,
) -> list[dict[str, Any]]:
    """Extract the four HealthCore v1 supply events for one UTC month.

    Input: ``month_start`` (first day of the UTC calendar month).
    Output: projected ``telemetry_events`` rows (no ``user_id``) for
    ``inbound_order_created``, ``outbound_order_created``,
    ``stock_threshold_triggered``, and ``supply_expiry_flagged``.
    """
    init_databases()
    engine = get_engine()
    if not telemetry_events_available(engine):
        raise SourceUnavailableError("telemetry_events table is not available")
    return extract_supply_performance_events(month_start)


@flow(name="transform_monthly_clinic_supply_kpis")
def transform_monthly_clinic_supply_kpis_flow(
    events: list[dict[str, Any]],
    month_start: date,
) -> dict[str, Any]:
    """Compute the four Monthly Clinic Supply Performance KPIs.

    Input: extracted events plus ``month_start``.
    Output: clinic-month aggregates for Supply Cost per Clinic
    (``total_supply_cost``), Supply Consumption Volume
    (``supply_consumption_count``), Critical Stockout Frequency
    (``critical_stockout_count``), and Expiry Risk Count
    (``expiry_risk_count``), plus extract/reject counts.
    """
    return transform_monthly_clinic_aggregates(events, month_start)


@flow(name="load_monthly_clinic_supply_performance")
def load_monthly_clinic_supply_performance_flow(
    transform_result: dict[str, Any],
    run_id: str,
    month_start: date,
) -> int:
    """Upsert clinic-month KPI rows into the reporting destination.

    Input: transform result, ``run_id``, and ``month_start``.
    Output: number of rows written to
    ``reporting.monthly_clinic_supply_performance``.
    """
    init_databases()
    return load_monthly_clinic_supply_performance(transform_result, run_id, month_start)


@flow(name="write_monthly_clinic_supply_eval_snapshot")
def write_monthly_clinic_supply_eval_snapshot_flow(
    transform_result: dict[str, Any],
    month_start: date,
    snapshot_path: str | None = None,
) -> str:
    """Optional evaluation snapshot under ``data/eval/``.

    Input: transform result, ``month_start``, optional snapshot path.
    Output: filesystem path of the written snapshot.
    Failure of this subflow must not stop extract-transform-load.
    """
    return write_eval_snapshot(transform_result, month_start, snapshot_path)


def _execute_pipeline(
    *,
    month_start: date,
    trigger_type: str,
    eval_snapshot_path: str | None,
) -> dict[str, Any]:
    """Coordinate run metadata and invoke the extract, transform, and load subflows."""
    init_databases()
    engine = get_engine()
    run_id = start_pipeline_run(engine, month_start, trigger_type)
    records_extracted = 0
    records_rejected = 0
    records_loaded = 0
    try:
        events = extract_clinic_supply_performance_events_flow(month_start)
        transform_result = transform_monthly_clinic_supply_kpis_flow(events, month_start)
        snapshot_state = write_monthly_clinic_supply_eval_snapshot_flow(
            transform_result,
            month_start,
            eval_snapshot_path,
            return_state=True,
        )
        _handle_optional_snapshot_state(snapshot_state)
        records_loaded = load_monthly_clinic_supply_performance_flow(
            transform_result,
            run_id,
            month_start,
        )
        records_extracted = int(transform_result["records_extracted"])
        records_rejected = int(transform_result["records_rejected"])
        finish_pipeline_run(
            engine,
            run_id,
            status="Completed",
            records_extracted=records_extracted,
            records_loaded=records_loaded,
            records_rejected=records_rejected,
        )
    except OverlappingPipelineRunError:
        raise
    except SourceUnavailableError as exc:
        finish_pipeline_run(
            engine,
            run_id,
            status="Failed",
            records_extracted=records_extracted,
            records_loaded=records_loaded,
            records_rejected=records_rejected,
            error_message=_sanitize_error(exc),
        )
        raise
    except Exception as exc:
        finish_pipeline_run(
            engine,
            run_id,
            status="Failed",
            records_extracted=records_extracted,
            records_loaded=records_loaded,
            records_rejected=records_rejected,
            error_message=_sanitize_error(exc),
        )
        raise

    result = get_pipeline_run(engine, run_id)
    if result is None:
        raise PipelineRunFailedError("pipeline run metadata was not recorded")
    return result


@flow(name="monthly_clinic_supply_performance_flow")
def monthly_clinic_supply_performance_flow(
    month_start: date | str | None = None,
    trigger_type: str = "scheduled",
    eval_snapshot_path: str | None = None,
) -> dict[str, Any]:
    """Main flow: coordinate extract, transform, and load subflows in sequence."""
    resolved_month = _parse_month_start(month_start)
    return _execute_pipeline(
        month_start=resolved_month,
        trigger_type=trigger_type,
        eval_snapshot_path=eval_snapshot_path,
    )


def run_monthly_clinic_supply_performance(
    month_start: date | str | None = None,
    trigger_type: str = "scheduled",
    eval_snapshot_path: str | None = None,
) -> dict[str, Any]:
    """CLI and API entry. Always submits the Prefect flow."""
    return monthly_clinic_supply_performance_flow(
        month_start=month_start,
        trigger_type=trigger_type,
        eval_snapshot_path=eval_snapshot_path,
    )


def get_monthly_clinic_supply_performance(month_start: date | None = None) -> dict[str, Any] | None:
    init_databases()
    return read_monthly_clinic_supply_performance(get_engine(), month_start)


def get_latest_pipeline_run() -> dict[str, Any] | None:
    init_databases()
    return read_latest_pipeline_run(get_engine())


def trigger_manual_pipeline_run(month_start: date | str | None = None) -> dict[str, Any]:
    """Invoke the approved pipeline. Aggregation stays in data/pipelines/."""
    return run_monthly_clinic_supply_performance(
        month_start=month_start,
        trigger_type="manual",
    )


if __name__ == "__main__":
    _configure_pipeline_logging()
    run_result = run_monthly_clinic_supply_performance(trigger_type="scheduled")
    print(json.dumps(run_result, indent=2, default=str))
    if run_result.get("status") != "Completed":
        sys.exit(1)
