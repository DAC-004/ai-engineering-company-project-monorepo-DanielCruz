"""In-file store for the most recent incident analysis and its owner.

API and Celery worker are separate processes, so this cannot live in memory.
last.json is the single-slot pointer used by GET /api/incidents/results*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.incident_analyzer.analyze import AnalysisResult

from app.storage import (
    atomic_write_json,
    last_analysis_path,
    read_json_with_retry,
)

_last_record: StoredAnalysis | None = None


@dataclass
class StoredAnalysis:
    """Last analysis plus the TinyDB user id that produced it (for ownership checks)."""

    result: AnalysisResult
    owner_user_id: str


def _result_to_payload(result: AnalysisResult) -> dict[str, Any]:
    return {
        "source_name": result.source_name,
        "total_records": result.total_records,
        "valid_count": result.valid_count,
        "invalid_count": result.invalid_count,
        "invalid_by_rule": dict(result.invalid_by_rule),
        "category_counts": dict(result.category_counts),
        "status_counts": dict(result.status_counts),
        "country_counts": dict(result.country_counts),
        "satisfaction_score_counts": {
            str(score): count for score, count in result.satisfaction_score_counts.items()
        },
        "satisfaction_scored_cases": result.satisfaction_scored_cases,
        "satisfaction_closed_cases": result.satisfaction_closed_cases,
        "satisfaction_average": result.satisfaction_average,
    }


def _result_from_payload(payload: dict[str, Any]) -> AnalysisResult:
    raw_scores = payload.get("satisfaction_score_counts") or {}
    score_counts = {int(score): int(count) for score, count in raw_scores.items()}
    return AnalysisResult(
        source_name=str(payload.get("source_name") or "upload.csv"),
        total_records=int(payload.get("total_records") or 0),
        valid_count=int(payload.get("valid_count") or 0),
        invalid_count=int(payload.get("invalid_count") or 0),
        invalid_by_rule=dict(payload.get("invalid_by_rule") or {}),
        category_counts=dict(payload.get("category_counts") or {}),
        status_counts=dict(payload.get("status_counts") or {}),
        country_counts=dict(payload.get("country_counts") or {}),
        satisfaction_score_counts=score_counts,
        satisfaction_scored_cases=int(payload.get("satisfaction_scored_cases") or 0),
        satisfaction_closed_cases=int(payload.get("satisfaction_closed_cases") or 0),
        satisfaction_average=payload.get("satisfaction_average"),
    )


def _read_last_from_disk() -> StoredAnalysis | None:
    document = read_json_with_retry(last_analysis_path())
    if document is None:
        return None
    owner_user_id = document.get("owner_user_id")
    result_payload = document.get("result")
    if not isinstance(owner_user_id, str) or not isinstance(result_payload, dict):
        return None
    return StoredAnalysis(
        result=_result_from_payload(result_payload),
        owner_user_id=owner_user_id,
    )


def save_analysis(result: AnalysisResult, *, owner_user_id: str) -> StoredAnalysis:
    global _last_record
    record = StoredAnalysis(result=result, owner_user_id=owner_user_id)
    atomic_write_json(
        last_analysis_path(),
        {
            "owner_user_id": owner_user_id,
            "result": _result_to_payload(result),
        },
    )
    _last_record = record
    return record


def get_last_analysis() -> AnalysisResult | None:
    record = get_last_record()
    return record.result if record is not None else None


def get_last_record() -> StoredAnalysis | None:
    global _last_record
    loaded = _read_last_from_disk()
    _last_record = loaded
    return loaded


def clear_last_analysis() -> bool:
    """Remove the stored analysis. Returns True if something was cleared."""
    global _last_record
    path = last_analysis_path()
    existed = path.exists()
    if existed:
        path.unlink()
    _last_record = None
    return existed
