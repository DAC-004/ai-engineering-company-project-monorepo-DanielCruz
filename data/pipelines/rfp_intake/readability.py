"""Readability metrics for processing cost, not for literary grading."""

from __future__ import annotations

import os
from typing import Any

from data.pipelines.rfp_intake.generation import REPO_ROOT

NLTK_DATA_DIR = REPO_ROOT / "data" / "process" / "nltk_data"
_MINIMUM_WORDS = 100


def _prepare_nltk() -> None:
    """Point NLTK at the local punkt data. Do not download during a request."""
    import nltk

    if NLTK_DATA_DIR.is_dir():
        location = str(NLTK_DATA_DIR)
        if location not in nltk.data.path:
            nltk.data.path.insert(0, location)
    override = os.environ.get("NLTK_DATA", "").strip()
    if override and override not in nltk.data.path:
        nltk.data.path.insert(0, override)


def _numeric_grade(grade_level: object) -> float | None:
    """Keep a calculated number. Labels such as 'college' are not grades we store."""
    if isinstance(grade_level, bool) or grade_level is None:
        return None
    if isinstance(grade_level, (int, float)):
        return float(grade_level)
    if isinstance(grade_level, str):
        try:
            return float(grade_level.strip())
        except ValueError:
            return None
    return None


def _unavailable_reason(metric_name: str, grade_level: object) -> str:
    label = str(grade_level).strip() or "empty"
    return f"{metric_name} grade_level was {label!r}, which is not a numeric grade"


def readability_metrics(markdown: str) -> dict[str, Any]:
    """Attempt Flesch-Kincaid and Gunning fog. Null means the scorer did not return a number.

    py-readability-metrics requires 100 words and raises ReadabilityException
    ('100 words required.') below that. Gunning fog can also return a label
    such as 'college' instead of a number when the rounded score is 13 or
    higher. Those labels are recorded in unavailable_reason and are not
    converted into a grade.
    """
    result: dict[str, Any] = {
        "flesch_kincaid_grade": None,
        "gunning_fog": None,
        "unavailable_reason": None,
    }
    if not markdown or not markdown.strip():
        result["unavailable_reason"] = "empty text; no grade was calculated"
        return result
    try:
        _prepare_nltk()
        from readability import Readability

        scores = Readability(markdown)
    except Exception as exc:
        message = str(exc)
        if "100 words" in message:
            result["unavailable_reason"] = (
                f"fewer than {_MINIMUM_WORDS} words; py-readability-metrics did not return a grade"
            )
        else:
            result["unavailable_reason"] = f"{type(exc).__name__}; no grade was calculated"
        return result

    reasons: list[str] = []
    try:
        flesch = scores.flesch_kincaid()
        result["flesch_kincaid_grade"] = _numeric_grade(flesch.grade_level)
        if result["flesch_kincaid_grade"] is None:
            reasons.append(_unavailable_reason("flesch_kincaid", flesch.grade_level))
    except Exception as exc:
        message = str(exc)
        if "100 words" in message:
            reasons.append(
                f"flesch_kincaid: fewer than {_MINIMUM_WORDS} words; no grade was calculated"
            )
        else:
            reasons.append(f"flesch_kincaid: {type(exc).__name__}; no grade was calculated")
    try:
        fog = scores.gunning_fog()
        result["gunning_fog"] = _numeric_grade(fog.grade_level)
        if result["gunning_fog"] is None:
            reasons.append(_unavailable_reason("gunning_fog", fog.grade_level))
    except Exception as exc:
        message = str(exc)
        if "100 words" in message:
            reasons.append(f"gunning_fog: fewer than {_MINIMUM_WORDS} words; no grade was calculated")
        else:
            reasons.append(f"gunning_fog: {type(exc).__name__}; no grade was calculated")
    if reasons and all("fewer than 100 words" in reason for reason in reasons):
        result["unavailable_reason"] = (
            f"fewer than {_MINIMUM_WORDS} words; py-readability-metrics did not return a grade"
        )
    elif reasons:
        result["unavailable_reason"] = "; ".join(reasons)
    return result
