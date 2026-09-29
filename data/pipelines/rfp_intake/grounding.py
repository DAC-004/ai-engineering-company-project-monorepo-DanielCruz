"""Source checks applied after the model writes.

The workers and synthesizer can drop a stated clinic schedule, assign that
schedule to revenue, keep only one deadline qualifier, or call a deadline
reasonable. This module repairs those cases from the screened document.
It does not invent a year, a budget, or a department fact the document
does not state. Equivalent paraphrases are left as the model wrote them.
"""

from __future__ import annotations

import re
from typing import Any

_MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
_RELATIVE_DEADLINE = re.compile(r"\b(?:about|around|approximately)\s+\d+\s+days\b", re.IGNORECASE)
_CALENDAR_DEADLINE = re.compile(
    rf"\b(?:about|around|approximately)\s+(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_SCHEDULE = re.compile(
    r"\b(\d+|two|three|four|five)\s+days?\s*(?:/|a|per)\s*week\b",
    re.IGNORECASE,
)
_CLINIC_SCHEDULE = re.compile(
    r"\bclinic\s+staffed\s+\d+\s*days?\s*/\s*week\b",
    re.IGNORECASE,
)
_REVENUE_STAFFING_PHRASE = re.compile(
    r"(?:,\s*|\s+and\s+)?(?:the\s+)?(?:specific\s+)?staffing\s+[^,.]{0,80}?"
    r"\brevenue(?:\s+(?:cycle|department))?\b\s*,?"
    r"|(?:^|\s)(?:the\s+)?revenue(?:\s+cycle|\s+department)?\s+is\s+staffed\b[^.]*(?:\.|$)",
    re.IGNORECASE,
)
_REASONABLE_CLAUSE = re.compile(
    r",?\s*\bwhich is (?:a )?reasonable\b[^.]*(?=\.|$)",
    re.IGNORECASE,
)
_WORD_FIGURE = {"two": "2", "three": "3", "four": "4", "five": "5"}


def _collapsed(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalized(text: str) -> str:
    """Compare deadline phrases without ordinal suffixes or extra space."""
    lowered = text.lower()
    lowered = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", lowered)
    return re.sub(r"\s+", " ", lowered)


def _schedule_figure(text: str) -> str | None:
    match = _SCHEDULE.search(_collapsed(text))
    if match is None:
        return None
    token = match.group(1).lower()
    return _WORD_FIGURE.get(token, token)


def _assigns_revenue_staffing(text: str) -> bool:
    """True when revenue, not the clinic, is the subject of a staffing claim or question."""
    collapsed = _collapsed(text)
    for name in ("revenue cycle", "revenue department", "revenue"):
        for match in re.finditer(rf"\b{re.escape(name)}\b", collapsed, re.IGNORECASE):
            window = collapsed[max(0, match.start() - 80) : min(len(collapsed), match.end() + 80)]
            if re.search(r"\bstaff(?:ed|ing|s)?\b", window, re.IGNORECASE):
                return True
    return False


def _is_clinic_schedule(text: str) -> bool:
    collapsed = _collapsed(text).lower()
    return "clinic" in collapsed and "staff" in collapsed and _schedule_figure(collapsed) is not None


def clinic_schedule_clause(source: str) -> str | None:
    """Return the document's clinic schedule, unchanged except for whitespace."""
    collapsed = _collapsed(source)
    match = _CLINIC_SCHEDULE.search(collapsed)
    if match is None:
        return None
    # Keep a leading "on-site" qualifier. Do not pull in the previous bullet.
    prefix_start = max(0, match.start() - 80)
    prefix = collapsed[prefix_start : match.start()]
    on_site = re.search(r"\bon-site\b[^.]{0,80}$", prefix, re.IGNORECASE)
    if on_site:
        clause = collapsed[prefix_start + on_site.start() : match.end()]
    else:
        clause = match.group(0)
    clause = clause.strip(" -")
    if clause and clause[-1] not in ".!?":
        clause = f"{clause}."
    return clause[0].upper() + clause[1:]


def _assumed_staffing(text: str) -> bool:
    """An explicit assumption is not a fact stated in the document."""
    return re.search(r"\bassumed\b", text, re.IGNORECASE) is not None and re.search(
        r"\bstaff",
        text,
        re.IGNORECASE,
    ) is not None


def _asks_stated_clinic_schedule(question: str, source: str) -> bool:
    """Do not ask for a clinic schedule the document already states."""
    if clinic_schedule_clause(source) is None:
        return False
    lowered = question.lower()
    return "clinic" in lowered and "staff" in lowered and "how many" in lowered


def _clinical_has_schedule(aspects: list[str], figure: str) -> bool:
    for aspect in aspects:
        if _schedule_figure(aspect) == figure and _is_clinic_schedule(aspect):
            return True
    return False


def _without_revenue_staffing(text: str, source: str) -> str:
    if _assigns_revenue_staffing(source):
        return text
    cleaned = _REVENUE_STAFFING_PHRASE.sub(" ", text)
    cleaned = re.sub(r"\b(include|includes)\s+,", r"\1", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    return cleaned.strip(" ,")


def _strip_reasonable_deadline(text: str) -> str:
    """Remove the judgment that a deadline is reasonable. Keep the stated timing."""
    cleaned = _REASONABLE_CLAUSE.sub("", text)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned.strip())
    kept: list[str] = []
    for sentence in sentences:
        if re.search(r"\breasonable\b", sentence, re.IGNORECASE) and re.search(
            r"\b(?:deadline|days|August|September|October)\b",
            sentence,
            re.IGNORECASE,
        ):
            sentence = re.sub(
                r"\b(?:a\s+)?reasonable(?:\s+timeframe)?\b",
                "",
                sentence,
                flags=re.IGNORECASE,
            )
            sentence = re.sub(r"\s{2,}", " ", sentence)
            sentence = re.sub(r"\s+,", ",", sentence)
            sentence = re.sub(r"\(\s*\)", "", sentence)
        stripped = sentence.strip(" ,")
        if stripped:
            kept.append(stripped)
    return " ".join(kept)


def _source_deadline_phrases(source: str) -> tuple[str | None, str | None]:
    collapsed = _collapsed(source)
    relative = _RELATIVE_DEADLINE.search(collapsed)
    calendar = _CALENDAR_DEADLINE.search(collapsed)
    return (
        relative.group(0) if relative else None,
        calendar.group(0) if calendar else None,
    )


def _strip_invented_year(text: str, calendar_phrase: str | None) -> str:
    """Drop a year the model attached to a date the document left without one."""
    if calendar_phrase is None or re.search(r"\b(?:19|20)\d{2}\b", calendar_phrase):
        return text
    month = re.search(rf"\b(?:{_MONTHS})\b", calendar_phrase, re.IGNORECASE)
    day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", calendar_phrase, re.IGNORECASE)
    if month is None or day is None:
        return text
    day_token = day.group(1)
    return re.sub(
        rf"(\b{month.group(0)}\s+{day_token}(?:st|nd|rd|th)?)\s*,?\s*(?:19|20)\d{{2}}\b",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )


def _mentions_deadline(text: str, relative: str | None, calendar: str | None) -> bool:
    lowered = text.lower()
    if "deadline" in lowered:
        return True
    if relative is not None and _normalized(relative) in _normalized(text):
        return True
    if calendar is not None:
        month = re.search(rf"\b(?:{_MONTHS})\b", calendar, re.IGNORECASE)
        day = re.search(r"\d{1,2}", calendar)
        if month and day and month.group(0).lower() in lowered and day.group(0) in lowered:
            return True
    return False


def _ensure_phrase(text: str, phrase: str) -> str:
    if _normalized(phrase) in _normalized(text):
        return text
    month_day = re.sub(r"^(?:about|around|approximately)\s+", "", phrase, flags=re.IGNORECASE)
    month_day_pattern = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1(?:st|nd|rd|th)?", month_day, flags=re.IGNORECASE)
    if month_day.lower() != phrase.lower():
        replaced, count = re.subn(month_day_pattern, phrase, text, count=1, flags=re.IGNORECASE)
        if count:
            return replaced
    separator = "" if not text.strip() else ", "
    base = text.rstrip(" .")
    return f"{base}{separator}{phrase}" if base else phrase


def preserve_deadline_text(current: str | None, source: str) -> str | None:
    """Keep every approximate deadline qualifier that appears in the document."""
    relative, calendar = _source_deadline_phrases(source)
    if relative is None and calendar is None:
        return current
    text = _strip_invented_year(_collapsed(current or ""), calendar)
    text = _strip_reasonable_deadline(text)
    if relative is not None:
        text = _ensure_phrase(text, relative)
    if calendar is not None:
        text = _ensure_phrase(text, calendar)
    text = _collapsed(text).strip(" ,")
    return text or None


def _align_deadline_statement(text: str, source: str) -> str:
    relative, calendar = _source_deadline_phrases(source)
    if relative is None and calendar is None:
        return _strip_reasonable_deadline(text)
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    aligned: list[str] = []
    for sentence in sentences:
        if not sentence.strip():
            continue
        if _mentions_deadline(sentence, relative, calendar):
            sentence = preserve_deadline_text(sentence, source) or ""
            if sentence and sentence[-1] not in ".!?":
                sentence = f"{sentence}."
        else:
            sentence = _strip_reasonable_deadline(sentence)
        if sentence.strip():
            aligned.append(sentence.strip())
    return " ".join(aligned)


def _ensure_missing_budget_question(metadata: dict[str, Any], sections: list[dict[str, Any]]) -> None:
    """A missing budget stays an open question even when the revenue worker omits it."""
    budget = metadata.get("budget_range")
    if isinstance(budget, str) and budget.strip():
        return
    for section in sections:
        if section.get("department_id") != "revenue":
            continue
        questions = [str(question) for question in section.get("open_questions") or []]
        if any(re.search(r"\b(budget|payment)\b", question, re.IGNORECASE) for question in questions):
            section["open_questions"] = questions
            return
        section["open_questions"] = [*questions, "Budget or payment terms were not stated."]
        return


def apply_source_grounding(
    source: str,
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
    summary: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Repair department placement, deadline qualifiers, and unsupported judgments.

    An unanswered budget may still be described as unresolved. That wording is
    not treated as a disagreement. A clinic schedule stays on clinical even
    when a worker attached it to revenue.
    """
    grounded_metadata = dict(metadata)
    grounded_metadata["deadline"] = preserve_deadline_text(
        metadata.get("deadline") if isinstance(metadata.get("deadline"), str) else None,
        source,
    )
    schedule = clinic_schedule_clause(source)
    figure = _schedule_figure(schedule or "")
    grounded_sections: list[dict[str, Any]] = []
    for section in sections:
        aspects = [str(aspect) for aspect in section.get("aspects") or []]
        questions = [str(question) for question in section.get("open_questions") or []]
        if not _assigns_revenue_staffing(source):
            repaired: list[str] = []
            for aspect in aspects:
                if _assigns_revenue_staffing(aspect):
                    aspect = _without_revenue_staffing(aspect, source)
                if aspect.strip() and not _assigns_revenue_staffing(aspect):
                    repaired.append(aspect)
            aspects = repaired
            questions = [
                question
                for question in questions
                if not _assigns_revenue_staffing(question) and not _asks_stated_clinic_schedule(question, source)
            ]
        aspects = [aspect for aspect in aspects if not _assumed_staffing(aspect)]
        if section.get("department_id") != "clinical":
            aspects = [aspect for aspect in aspects if not _is_clinic_schedule(aspect)]
        aspects = [_align_deadline_statement(aspect, source) for aspect in aspects]
        aspects = [aspect for aspect in aspects if aspect.strip()]
        copy = dict(section)
        copy["aspects"] = aspects
        copy["open_questions"] = questions
        grounded_sections.append(copy)

    if schedule and figure:
        for section in grounded_sections:
            if section.get("department_id") != "clinical":
                continue
            if not _clinical_has_schedule(section["aspects"], figure):
                section["aspects"] = [*section["aspects"], schedule]

    _ensure_missing_budget_question(grounded_metadata, grounded_sections)

    grounded_summary = _without_revenue_staffing(summary, source)
    grounded_summary = _align_deadline_statement(grounded_summary, source)
    return grounded_metadata, grounded_sections, grounded_summary
