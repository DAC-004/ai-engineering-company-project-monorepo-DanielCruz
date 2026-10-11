"""I03a A2: API incident list filters via TestClient (disposable TinyDB per phase)."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_AUTH_DATA = (API_DIR / "data" / "auth.json").resolve()

_ISOLATION_ROOT = tempfile.mkdtemp(prefix="i03a-api-incident-filters-")
_PHASE_ROOT = Path(_ISOLATION_ROOT)

os.environ["SECRET_KEY"] = "i03a-filter-harness-secret-32c!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["RESEND_API_KEY"] = "re_filter_harness_placeholder"
os.environ["RESEND_FROM_EMAIL"] = "HealthCore <onboarding@resend.dev>"
os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(PACKAGES_SHARED))
sys.path.insert(0, str(SCRIPTS_DIR))

SAMPLE_CSV = REPO_ROOT / "scripts" / "incidents-healthcore.csv"
EVIDENCE_PATH = API_DIR / "data" / "i03a-831ebff" / "api-incident-filters.txt"

HISTORICAL_COUNT_CASES: tuple[tuple[str, int], ...] = (
    ("origin=customer", 94),
    ("status=resolved", 52),
    ("category=patient_experience", 61),
    ("branch=manchester_central", 15),
)

F1_CREATE = {
    "title": "I03a filter harness F1 referral item",
    "description": "Synthetic open internal Dallas referral fixture.",
    "category": "referral_issue",
    "status": "open",
    "origin": "internal",
    "branch": "dallas_uptown",
}

F2_CREATE = {
    **F1_CREATE,
    "title": "I03a filter harness F2 referral item",
    "description": "Synthetic fixture progressed to resolved.",
}

OPEN_AND_QUERY = (
    "status=open&branch=dallas_uptown&origin=internal&category=referral_issue"
)
RESOLVED_AND_QUERY = (
    "status=resolved&branch=dallas_uptown&origin=internal&category=referral_issue"
)

INVALID_FILTER_CASES: tuple[tuple[str, str], ...] = (
    ("status", "OPEN"),
    ("origin", "clinic"),
    ("branch", "US-TX-01"),
    ("category", "APPOINTMENT"),
)


def _assert_isolated_tinydb(path: Path) -> None:
    resolved = path.resolve()
    if resolved == DEFAULT_AUTH_DATA:
        raise RuntimeError(f"TINYDB_PATH must not be main auth store: {resolved}")
    if str(resolved).startswith(str(DEFAULT_AUTH_DATA.parent)):
        raise RuntimeError(f"TINYDB_PATH under main data dir rejected: {resolved}")
    if not str(resolved).startswith(str(_PHASE_ROOT.resolve())):
        raise RuntimeError(f"TINYDB_PATH outside harness temp root: {resolved}")


def _configure_phase_store(phase: str) -> Path:
    phase_dir = _PHASE_ROOT / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    tinydb_path = phase_dir / "auth.json"
    inventory_db = phase_dir / "inventory.db"
    os.environ["TINYDB_PATH"] = str(tinydb_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{inventory_db.resolve().as_posix()}"
    _assert_isolated_tinydb(tinydb_path)

    from app.core.config import get_settings  # noqa: WPS433
    from app.db.database import reset_engine_for_tests  # noqa: WPS433
    from app.db.tinydb import reset_db_for_tests  # noqa: WPS433

    get_settings.cache_clear()
    reset_engine_for_tests()
    reset_db_for_tests()
    return tinydb_path


# Import app after first phase path is configured (updated before each phase).
_configure_phase_store("bootstrap")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from seed_incidents import seed  # noqa: E402


def _incident_ids(body: list[dict]) -> set[str]:
    return {str(item["id"]) for item in body}


def _auth_headers(client: TestClient) -> dict[str, str]:
    register = client.post(
        "/users",
        json={"email": "filters@healthcore.com", "password": "SecurePass1!"},
    )
    if register.status_code != 201:
        raise RuntimeError(f"Register failed: {register.status_code} {register.text}")
    login = client.post(
        "/auth/login",
        data={"username": "filters@healthcore.com", "password": "SecurePass1!"},
    )
    if login.status_code != 200:
        raise RuntimeError(f"Login failed: {login.status_code} {login.text}")
    token = login.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _create_f1(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/incidents", headers=headers, json=F1_CREATE)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"F1 create failed: {response.status_code} {response.text}")
    incident_id = response.json().get("id")
    if not incident_id:
        raise RuntimeError("F1 create returned no id")
    return str(incident_id)


def _create_f2_resolved(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/api/incidents", headers=headers, json=F2_CREATE)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"F2 create failed: {response.status_code} {response.text}")
    incident_id = str(response.json()["id"])
    step = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "in_progress"},
    )
    if step.status_code != 200:
        raise RuntimeError(f"F2 in_progress failed: {step.status_code} {step.text}")
    done = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "resolved"},
    )
    if done.status_code != 200:
        raise RuntimeError(f"F2 resolved failed: {done.status_code} {done.text}")
    if done.json().get("status") != "resolved":
        raise RuntimeError("F2 did not end resolved")
    return incident_id


def _historical_customer_dallas_ids(incidents: list[dict]) -> set[str]:
    return {
        str(row["id"])
        for row in incidents
        if row.get("origin") == "customer" and row.get("branch") == "dallas_uptown"
    }


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []
    lines: list[str] = []

    def emit(message: str) -> None:
        print(message)
        lines.append(message)

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            emit(f"PASS  {name}")
        else:
            failures.append(name)
            emit(f"FAIL  {name} {detail}")

    emit("I03a A2 API filter harness")
    emit(
        "Tested state: HEAD 831ebff + resolved uncommitted PR #10 merge "
        "(MERGE_HEAD 00c9946) + this harness"
    )
    emit(f"Timestamp (UTC): {datetime.now(UTC).isoformat()}")
    emit(f"Worktree: healthcore-i03-incidents")
    emit(f"CWD: {API_DIR}")
    emit(f"Command: uv run python scripts/run_i03a_api_incident_filters.py")
    emit(f"Python: {sys.version.split()[0]} ({sys.executable})")
    emit(f"Isolation root: {_PHASE_ROOT.resolve()}")
    emit(f"Default auth path (must not be used): {DEFAULT_AUTH_DATA}")
    emit("")

    # --- H-only ---
    h_db = _configure_phase_store("h-only")
    emit(f"Phase H-only TINYDB_PATH={h_db.resolve()}")
    headers = _auth_headers(client)
    seed_exit = seed(SAMPLE_CSV)
    check("H-only seed exits 0", seed_exit == 0, str(seed_exit))
    all_h = client.get("/api/incidents", headers=headers)
    check("H-only list 200", all_h.status_code == 200, str(all_h.status_code))
    historical_rows = all_h.json() if all_h.status_code == 200 else []
    expected_customer_dallas = _historical_customer_dallas_ids(historical_rows)
    emit(
        f"H-only baseline customer+dallas_uptown ids (n={len(expected_customer_dallas)}): "
        f"sorted sample omitted"
    )

    for query, expected_count in HISTORICAL_COUNT_CASES:
        response = client.get(f"/api/incidents?{query}", headers=headers)
        body = response.json() if response.status_code == 200 else []
        actual = len(body) if isinstance(body, list) else -1
        check(
            f"H-only count ?{query} == {expected_count}",
            response.status_code == 200 and actual == expected_count,
            f"status={response.status_code} actual={actual}",
        )

    # --- F1-only ---
    f1_db = _configure_phase_store("f1-only")
    emit(f"Phase F1-only TINYDB_PATH={f1_db.resolve()}")
    headers = _auth_headers(client)
    f1_id = _create_f1(client, headers)

    list_all = client.get("/api/incidents", headers=headers)
    check(
        "F1-only GET all ids",
        list_all.status_code == 200 and _incident_ids(list_all.json()) == {f1_id},
        str(_incident_ids(list_all.json()) if list_all.status_code == 200 else []),
    )

    for field, value in (
        ("status", "open"),
        ("origin", "internal"),
        ("branch", "dallas_uptown"),
        ("category", "referral_issue"),
    ):
        response = client.get(f"/api/incidents?{field}={value}", headers=headers)
        body = response.json() if response.status_code == 200 else []
        check(
            f"F1-only ?{field}={value} ids == {{f1}}",
            response.status_code == 200 and _incident_ids(body) == {f1_id},
            str(_incident_ids(body) if isinstance(body, list) else body),
        )

    and_open = client.get(f"/api/incidents?{OPEN_AND_QUERY}", headers=headers)
    check(
        "F1-only open AND ids",
        and_open.status_code == 200 and _incident_ids(and_open.json()) == {f1_id},
        str(_incident_ids(and_open.json()) if and_open.status_code == 200 else []),
    )

    empty_customer = client.get("/api/incidents?origin=customer", headers=headers)
    check(
        "F1-only ?origin=customer == []",
        empty_customer.status_code == 200 and empty_customer.json() == [],
        str(empty_customer.json()),
    )

    empty_resolved = client.get(f"/api/incidents?{RESOLVED_AND_QUERY}", headers=headers)
    check(
        "F1-only resolved AND == []",
        empty_resolved.status_code == 200 and empty_resolved.json() == [],
        str(empty_resolved.json()),
    )

    # --- H + F1 + F2 ---
    hf_db = _configure_phase_store("h-f1-f2")
    emit(f"Phase H+F1+F2 TINYDB_PATH={hf_db.resolve()}")
    headers = _auth_headers(client)
    seed_exit = seed(SAMPLE_CSV)
    check("H+F1+F2 seed exits 0", seed_exit == 0, str(seed_exit))
    seeded = client.get("/api/incidents", headers=headers).json()
    expected_h_customer_dallas = _historical_customer_dallas_ids(seeded)

    f1_id = _create_f1(client, headers)
    f2_id = _create_f2_resolved(client, headers)

    open_and = client.get(f"/api/incidents?{OPEN_AND_QUERY}", headers=headers)
    open_ids = _incident_ids(open_and.json()) if open_and.status_code == 200 else set()
    check(
        "H+F1+F2 open AND == {f1}",
        open_and.status_code == 200
        and open_ids == {f1_id}
        and f2_id not in open_ids,
        f"actual={sorted(open_ids)}",
    )

    resolved_and = client.get(f"/api/incidents?{RESOLVED_AND_QUERY}", headers=headers)
    resolved_ids = (
        _incident_ids(resolved_and.json()) if resolved_and.status_code == 200 else set()
    )
    check(
        "H+F1+F2 resolved AND == {f2}",
        resolved_and.status_code == 200
        and resolved_ids == {f2_id}
        and f1_id not in resolved_ids,
        f"actual={sorted(resolved_ids)}",
    )

    customer_branch = client.get(
        "/api/incidents?origin=customer&branch=dallas_uptown",
        headers=headers,
    )
    actual_cb = (
        _incident_ids(customer_branch.json())
        if customer_branch.status_code == 200
        else set()
    )
    check(
        "H+F1+F2 customer+dallas_uptown == historical baseline ids",
        customer_branch.status_code == 200 and actual_cb == expected_h_customer_dallas,
        f"expected_n={len(expected_h_customer_dallas)} actual_n={len(actual_cb)}",
    )
    check(
        "H+F1+F2 customer+dallas_uptown excludes F1",
        f1_id not in actual_cb,
        f"f1 in set={f1_id in actual_cb}",
    )
    check(
        "H+F1+F2 customer+dallas_uptown excludes F2",
        f2_id not in actual_cb,
        f"f2 in set={f2_id in actual_cb}",
    )

    # --- Invalid enum filters (F1-only store) ---
    _configure_phase_store("invalid-enum")
    emit("Phase invalid-enum (fresh store)")
    headers = _auth_headers(client)
    _create_f1(client, headers)
    for field, bad_value in INVALID_FILTER_CASES:
        response = client.get(
            f"/api/incidents?{field}={bad_value}",
            headers=headers,
        )
        body = response.json() if response.content else {}
        check(
            f"Invalid ?{field}={bad_value} -> 400 field={field}",
            response.status_code == 400
            and body.get("field") == field
            and isinstance(body.get("message"), str)
            and body["message"],
            f"{response.status_code} {body}",
        )

    emit("")
    if failures:
        emit(f"{len(failures)} assertion(s) failed.")
        exit_code = 1
    else:
        emit("All A2 API filter assertions passed.")
        exit_code = 0

    emit(f"Exit code: {exit_code}")
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    emit(f"Evidence written: {EVIDENCE_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
