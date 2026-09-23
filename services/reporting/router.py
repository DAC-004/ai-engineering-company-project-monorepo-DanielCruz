"""Business reporting routes under /reporting.

Separate from services/telemetry. Endpoints import pipeline functions and do
not duplicate extract, transform, or load logic.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.schemas.user import UserInDB
from data.pipelines.pipeline import (
    get_latest_pipeline_run,
    get_monthly_clinic_supply_performance,
    trigger_manual_pipeline_run,
)
from data.pipelines.reporting_store import (
    OverlappingPipelineRunError,
    SourceUnavailableError,
)
from data.pipelines.transforms import previous_completed_utc_month
from services.reporting.schemas import (
    MonthlyClinicSupplyPerformanceResponse,
    PipelineRunAcceptedResponse,
    PipelineRunLatestResponse,
    PipelineRunTriggerRequest,
)

router = APIRouter(prefix="/reporting", tags=["reporting"])


def _parse_month_start_query(raw: str | None) -> date | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        parsed = date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="month_start must be YYYY-MM-DD",
        ) from exc
    if parsed.day != 1:
        raise HTTPException(
            status_code=422,
            detail="month_start must be the first day of a UTC calendar month",
        )
    return parsed


@router.get(
    "/monthly-clinic-supply-performance",
    response_model=MonthlyClinicSupplyPerformanceResponse,
)
def read_monthly_clinic_supply_performance(
    month_start: str | None = Query(default=None),
    _current_user: UserInDB = Depends(get_current_user),
) -> dict:
    resolved = _parse_month_start_query(month_start)
    payload = get_monthly_clinic_supply_performance(resolved)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed Monthly Clinic Supply Performance report is available",
        )
    return payload


@router.get("/pipeline-runs/latest", response_model=PipelineRunLatestResponse)
def read_latest_pipeline_run(
    _current_user: UserInDB = Depends(get_current_user),
) -> dict:
    payload = get_latest_pipeline_run()
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pipeline runs have been recorded",
        )
    return payload


@router.post(
    "/pipeline-runs",
    response_model=PipelineRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_pipeline_run(
    body: PipelineRunTriggerRequest | None = None,
    _current_user: UserInDB = Depends(get_current_user),
) -> dict:
    requested_month = body.month_start if body is not None else None
    if requested_month is not None and requested_month.day != 1:
        raise HTTPException(
            status_code=422,
            detail="month_start must be the first day of a UTC calendar month",
        )
    month_start = requested_month or previous_completed_utc_month()
    try:
        result = trigger_manual_pipeline_run(month_start)
    except OverlappingPipelineRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pipeline run for this month is already in progress",
        ) from exc
    except SourceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telemetry_events is not available",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    return {
        "run_id": result["run_id"],
        "status": result["status"],
        "month_start": result["month_start"],
        "records_processed": result.get("records_processed", 0),
        "error_message": result.get("error_message"),
    }
