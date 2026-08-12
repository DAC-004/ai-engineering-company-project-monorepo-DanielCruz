"""In-memory store for the most recent incident analysis and its owner."""

from __future__ import annotations

from dataclasses import dataclass

from shared.incident_analyzer.analyze import AnalysisResult

_last_record: StoredAnalysis | None = None


@dataclass
class StoredAnalysis:
    """Last analysis plus the TinyDB user id that produced it (for ownership checks)."""

    result: AnalysisResult
    owner_user_id: str


def save_analysis(result: AnalysisResult, *, owner_user_id: str) -> StoredAnalysis:
    global _last_record
    _last_record = StoredAnalysis(result=result, owner_user_id=owner_user_id)
    return _last_record


def get_last_analysis() -> AnalysisResult | None:
    return _last_record.result if _last_record is not None else None


def get_last_record() -> StoredAnalysis | None:
    return _last_record


def clear_last_analysis() -> bool:
    """Remove the stored analysis. Returns True if something was cleared."""
    global _last_record
    if _last_record is None:
        return False
    _last_record = None
    return True
