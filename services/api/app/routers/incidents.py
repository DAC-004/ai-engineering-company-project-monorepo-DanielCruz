"""Incident analysis endpoints — shared logic with scripts/analyze.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from shared.incident_analyzer import analysis_to_csv_rows, analyze_csv_bytes
from shared.incident_analyzer.analyze import IncidentCsvError
from shared.incident_analyzer.export_csv import rows_to_csv_text

from app.core.deps import get_current_user
from app.incidents_store import (
    clear_last_analysis,
    get_last_analysis,
    get_last_record,
    save_analysis,
)
from app.schemas.user import UserInDB, UserRole

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _require_analysis_owner_or_admin(current_user: UserInDB) -> None:
    """403 when an authenticated caller tries to clear another user's stored analysis."""
    record = get_last_record()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis available. Upload a CSV to /api/incidents/analyze first.",
        )
    if current_user.id == record.owner_user_id:
        return
    if current_user.role == UserRole.admin:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to modify this analysis",
    )


@router.post("/analyze")
async def analyze_incidents(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """Protected: analyze an uploaded incident CSV (sensitive operational data)."""
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Incorrect file format: only CSV files are accepted.",
        )

    try:
        data = await file.read()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The file could not be read. Try again.",
        ) from exc
    if not data or not data.strip():
        raise HTTPException(status_code=400, detail="The CSV file is empty.")

    try:
        result = analyze_csv_bytes(data, source_name=filename)
    except IncidentCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_analysis(result, owner_user_id=current_user.id)
    return result.to_dict()


@router.get("/results")
async def get_results(
    _current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """
    Protected: return the last analysis as JSON.

    Sensitive operational metrics from patient-incident CSV processing.
    """
    result = get_last_analysis()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis available. Upload a CSV to /api/incidents/analyze first.",
        )
    return result.to_dict()


@router.get("/results/summary")
async def get_results_summary(
    _current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """
    Protected: compact operational summary of the last analysis.

    Exposes aggregate incident quality metrics appropriate for authenticated operators.
    """
    result = get_last_analysis()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis available. Upload a CSV to /api/incidents/analyze first.",
        )
    return {
        "source_name": result.source_name,
        "total_records": result.total_records,
        "valid_count": result.valid_count,
        "invalid_count": result.invalid_count,
        "satisfaction_average": result.satisfaction_average,
        "country_counts": dict(result.country_counts),
        "status_counts": dict(result.status_counts),
    }


@router.get("/results/export")
async def export_results(
    _current_user: UserInDB = Depends(get_current_user),
) -> Response:
    """Protected: export the last analysis CSV (sensitive operational output)."""
    result = get_last_analysis()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis available. Upload a CSV to /api/incidents/analyze first.",
        )

    csv_text = rows_to_csv_text(analysis_to_csv_rows(result))
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="results.csv"',
        },
    )


@router.delete("/results", status_code=status.HTTP_204_NO_CONTENT)
async def delete_results(
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """
    Protected: clear the stored analysis.

    Only the analysis owner or an admin may clear it (403 otherwise).
    """
    _require_analysis_owner_or_admin(current_user)
    clear_last_analysis()
