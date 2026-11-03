"""Source checks applied after the model writes.

The workers and synthesizer can drop a stated clinic schedule, assign that
schedule to revenue, keep only one deadline qualifier, or call a deadline
reasonable. They can also drop a stated contract term, summarize only one
department, or blame a contact for a budget the source never stated. This
module repairs those cases from the screened document and the worker
sections. It does not invent a year, a budget, or a department fact the
document does not state. Equivalent paraphrases are left as the model wrote
them. The synthesizer text is kept; missing contacts are added from the
sections rather than replaced with a fixed sample paragraph.
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
_PROPOSAL_DEADLINE_ABSENCE = re.compile(
    r"no\s+proposal\s+deadline|proposal\s+deadline\s+(?:is\s+)?not\s+stated",
    re.IGNORECASE,
)


def is_proposal_deadline_absence_aspect(text: str) -> bool:
    """True when an aspect only records that the source omitted a proposal deadline."""
    return bool(_PROPOSAL_DEADLINE_ABSENCE.search(text.strip()))
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
_CONTRACT_TERM = re.compile(
    r"\b(?:contract term:\s*)?\d+\s+months?,?\s+with (?:an )?option to renew\b",
    re.IGNORECASE,
)
_CONTACT_WITHHELD_BUDGET = re.compile(
    r"\b(?:has not|have not|did not|hasn't|didn't|failed to|does not|do not|doesn't|don't)\s+"
    r"(?:provid\w*|includ\w*|stat\w*|suppl\w*|giv\w*)\b",
    re.IGNORECASE,
)
# "confirm there is no budget" asserts absence. A null budget_range means unknown.
_ASSERTS_ABSENT_BUDGET = re.compile(
    r"\b(?:confirm\s+(?:that\s+)?)?there\s+is\s+no\s+budget\b"
    r"|\bno\s+budget\s+(?:for\s+this\s+project|is\s+stated|was\s+provided)\b",
    re.IGNORECASE,
)
_APPOINTMENT_VOLUME = re.compile(
    r"\b(?:approximately|about|around)?\s*\d+\s+"
    r"(?:(?:on-?site\s+)?visits?|appointments?|consultations?)\s+per\s+month\b",
    re.IGNORECASE,
)
_PROPOSED_SERVICE_START = re.compile(
    rf"\bproposed(?:\s+service)?\s+start(?: date)?(?:\s+in|\s*:)?\s+(?:{_MONTHS})\s+\d{{4}}\b",
    re.IGNORECASE,
)


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


def _asks_stated_appointment_volume(question: str, source: str) -> bool:
    """Do not ask for monthly appointment volume the document already states."""
    if appointment_volume_clause(source) is None:
        return False
    lowered = question.lower()
    if "appointment" not in lowered:
        return False
    return bool(
        re.search(r"\b(volume|how many|per month|expected|anticipated)\b", lowered)
    )


def _asks_as_if_service_start_missing(question: str, source: str) -> bool:
    """Drop questions that treat start as absent when a month/year start is stated.

    An exact calendar day may still be unknown. That is not the same as no
    proposed service start. Exact-day questions are left alone.
    """
    if proposed_service_start_clause(source) is None:
        return False
    lowered = question.lower()
    if re.search(r"\b(exact|specific)\s+day\b|\bday of (the )?month\b|\bcalendar day\b", lowered):
        return False
    return bool(
        re.search(
            r"\b(what|when)\b.{0,40}\b(proposed\s+)?(service\s+)?start(\s+date)?\b",
            lowered,
        )
    )


def _sentence_asks_stated_appointment_volume(sentence: str, source: str) -> bool:
    if appointment_volume_clause(source) is None:
        return False
    lowered = sentence.lower()
    if "appointment" not in lowered:
        return False
    return bool(re.search(r"\b(volume|how many|per month|provide|expected|anticipated)\b", lowered))


def _sentence_asks_as_if_service_start_missing(sentence: str, source: str) -> bool:
    return _asks_as_if_service_start_missing(sentence, source)


def _scrub_answered_demand_asks(summary: str, source: str) -> str:
    """Remove summary asks for demand facts the source already stated."""
    sentences = _summary_sentences(summary)
    kept: list[str] = []
    for sentence in sentences:
        if _sentence_asks_stated_appointment_volume(sentence, source):
            continue
        if _sentence_asks_as_if_service_start_missing(sentence, source):
            continue
        kept.append(sentence)
    return " ".join(kept)


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
    """Keep every approximate deadline qualifier that appears in the document.

    A proposal deadline is not a service start month. When the source has no
    approximate deadline phrasing, drop model-invented relative-day deadlines
    such as "about 25 days" and keep only wording that still appears in the
    source. Unknown stays null.
    """
    relative, calendar = _source_deadline_phrases(source)
    if relative is None and calendar is None:
        if not isinstance(current, str) or not current.strip():
            return None
        text = _collapsed(current)
        # Remove relative-day inventions the document never stated.
        text = _RELATIVE_DEADLINE.sub("", text)
        text = _collapsed(text).strip(" ,;")
        if not text:
            return None
        if _normalized(text) in _normalized(source):
            return text
        return None
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


def contract_term_clause(source: str) -> str | None:
    """Return a stated duration plus renewal option, or None when the source has neither."""
    match = _CONTRACT_TERM.search(_collapsed(source))
    if match is None:
        return None
    clause = match.group(0).strip(" -")
    if not clause.lower().startswith("contract term"):
        clause = f"Contract term: {clause}"
    if clause[-1] not in ".!?":
        clause = f"{clause}."
    return clause[0].upper() + clause[1:]


def _states_contract_term(text: str, clause: str) -> bool:
    """An equivalent paraphrase keeps the duration figure and the renewal option."""
    figure = re.search(r"\d+", clause)
    if figure is None or figure.group(0) not in text:
        return False
    return re.search(r"\brenew", text, re.IGNORECASE) is not None


def _ensure_contract_term(source: str, sections: list[dict[str, Any]]) -> None:
    """Keep a stated contract term on Revenue Cycle when every worker dropped it.

    Duration and renewal are commercial terms. Clinical and compliance do not
    receive a copy. A section that already states the same figure and renewal
    is left unchanged.
    """
    clause = contract_term_clause(source)
    if clause is None:
        return
    for section in sections:
        if section.get("department_id") != "revenue":
            continue
        aspects = [str(aspect) for aspect in section.get("aspects") or []]
        if any(_states_contract_term(aspect, clause) for aspect in aspects):
            return
        section["aspects"] = [*aspects, clause]
        return


_NULL_LIKE_METADATA = frozenset(
    {
        "null",
        "none",
        "n/a",
        "na",
        "nil",
        "undefined",
        "unknown",
        "not stated",
        "not provided",
        "not specified",
    }
)


def normalize_optional_metadata_text(value: object) -> str | None:
    """Treat empty and null-like model strings as missing metadata."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.casefold() in _NULL_LIKE_METADATA:
        return None
    return stripped


def _budget_was_not_stated(metadata: dict[str, Any]) -> bool:
    return normalize_optional_metadata_text(metadata.get("budget_range")) is None


def _sentence_blames_revenue_for_missing_budget(sentence: str, contacts: list[str]) -> bool:
    """True when the sentence says the revenue contact withheld a budget the source omitted."""
    if _CONTACT_WITHHELD_BUDGET.search(sentence) is None:
        return False
    if re.search(r"\b(?:budget|payment)\b", sentence, re.IGNORECASE) is None:
        return False
    lowered = sentence.lower()
    if "revenue cycle contact" in lowered or re.search(r"\brevenue contact\b", lowered):
        return True
    return any(contact.lower() in lowered for contact in contacts)


def _sentence_asserts_absent_budget(sentence: str) -> bool:
    """True when the summary treats a missing budget as confirmed zero budget."""
    return _ASSERTS_ABSENT_BUDGET.search(sentence) is not None


def _reattribute_missing_budget(
    summary: str,
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
) -> str:
    """A missing budget belongs to the source request, not to the department contact."""
    if not _budget_was_not_stated(metadata):
        return summary
    contacts = [
        str(section.get("contact_name")).strip()
        for section in sections
        if section.get("department_id") == "revenue" and str(section.get("contact_name") or "").strip()
    ]
    sentences = re.split(r"(?<=[.!?])\s+|\n+", summary.strip())
    kept: list[str] = []
    replaced = False
    for sentence in sentences:
        stripped = sentence.strip()
        if not stripped:
            continue
        blames_contact = bool(contacts) and _sentence_blames_revenue_for_missing_budget(
            stripped, contacts
        )
        asserts_absent = _sentence_asserts_absent_budget(stripped)
        if blames_contact or asserts_absent:
            if not replaced:
                kept.append("The source request did not state a budget or payment terms.")
                replaced = True
            continue
        kept.append(stripped)
    return " ".join(kept)


def appointment_volume_clause(source: str) -> str | None:
    """Return a stated monthly appointment volume from the document, or None."""
    match = _APPOINTMENT_VOLUME.search(_collapsed(source))
    if match is None:
        return None
    clause = match.group(0).strip(" -")
    if clause and clause[-1] not in ".!?":
        clause = f"{clause}."
    return clause[0].upper() + clause[1:]


def proposed_service_start_clause(source: str) -> str | None:
    """Return a stated proposed service start month/year, not a proposal deadline."""
    match = _PROPOSED_SERVICE_START.search(_collapsed(source))
    if match is None:
        return None
    clause = match.group(0).strip(" -")
    if clause and clause[-1] not in ".!?":
        clause = f"{clause}."
    return clause[0].upper() + clause[1:]


def _aspect_covers_clause(aspects: list[str], clause: str) -> bool:
    """True when an aspect already carries the same figures or normalized wording."""
    target = _normalized(clause)
    target_figures = set(re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", clause))
    for aspect in aspects:
        if target in _normalized(aspect):
            return True
        if target_figures and target_figures <= set(re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", aspect)):
            lowered_aspect = aspect.lower()
            if "month" in lowered_aspect and any(
                token in lowered_aspect for token in ("appointment", "visit", "consultation")
            ):
                return True
            if "proposed start" in aspect.lower() or re.search(
                rf"\b(?:{_MONTHS})\s+\d{{4}}\b", aspect, re.IGNORECASE
            ):
                return True
    return False


def _ensure_clinical_demand_facts(source: str, sections: list[dict[str, Any]]) -> None:
    """Keep stated appointment volume and proposed service start on clinical.

    These are demand facts from the request. They are not proposal deadlines and
    are not invented when the source omits them.
    """
    volume = appointment_volume_clause(source)
    start = proposed_service_start_clause(source)
    if volume is None and start is None:
        return
    for section in sections:
        if section.get("department_id") != "clinical":
            continue
        aspects = [str(aspect) for aspect in section.get("aspects") or []]
        # Drop placeholder labels once the concrete source clause is known.
        if volume is not None:
            aspects = [
                aspect
                for aspect in aspects
                if not re.fullmatch(r"expected appointment volume\.?", aspect.strip(), re.IGNORECASE)
            ]
        additions: list[str] = []
        if volume is not None and not _aspect_covers_clause(aspects, volume):
            additions.append(volume)
        if start is not None and not _aspect_covers_clause(aspects, start):
            additions.append(start)
        section["aspects"] = [*aspects, *additions] if additions else aspects
        return


def _coverage_sentence(section: dict[str, Any]) -> str | None:
    """One ask built from the worker section. No sample paragraph is substituted."""
    contact = str(section.get("contact_name") or "").strip()
    if not contact:
        return None
    department = str(section.get("department_name") or section.get("department_id") or "").strip()
    aspects = [str(aspect).strip().rstrip(".") for aspect in section.get("aspects") or [] if str(aspect).strip()]
    questions = [
        str(question).strip().rstrip(".")
        for question in section.get("open_questions") or []
        if str(question).strip()
    ]
    # Prefer concrete stated facts over vague placeholders such as "expected appointment volume".
    contract_aspects = [aspect for aspect in aspects if re.search(r"\bcontract term\b", aspect, re.IGNORECASE)]
    demand_aspects = [
        aspect
        for aspect in aspects
        if re.search(r"\bappointments?\s+per\s+month\b", aspect, re.IGNORECASE)
        or re.search(r"\bproposed start\b", aspect, re.IGNORECASE)
    ]
    concrete = contract_aspects or demand_aspects
    remaining = [aspect for aspect in aspects if aspect not in concrete]
    points = (concrete + remaining)[:2] or questions[:1]
    detail = "; ".join(points) if points else "the points recorded for this department"
    label = f"{contact} ({department})" if department else contact
    return f"Ask {label} about {detail}."


_POINT_WORD = re.compile(r"[a-z0-9]{5,}")
_POINT_STOP_WORDS = frozenset(
    {"about", "which", "there", "their", "would", "should", "other", "these", "those", "being"}
)


def _section_point_words(section: dict[str, Any]) -> set[str]:
    """Words that identify a department finding. Contact labels are not findings."""
    texts = [
        str(item)
        for item in [*(section.get("aspects") or []), *(section.get("open_questions") or [])]
        if str(item).strip()
    ]
    words: set[str] = set()
    for text in texts:
        words.update(
            word for word in _POINT_WORD.findall(text.lower()) if word not in _POINT_STOP_WORDS
        )
    return words


def _sentence_links_contact_to_finding(sentence: str, contact: str, point_words: set[str]) -> bool:
    """A contact name in its own sentence is not a department synthesis."""
    if not point_words or contact.lower() not in sentence.lower():
        return False
    sentence_words = set(_POINT_WORD.findall(sentence.lower()))
    return any(word in sentence_words for word in point_words)


def _summary_sentences(summary: str) -> list[str]:
    """Split sentences without treating an abbreviated title such as Dr. as the end."""
    protected = re.sub(
        r"\b(Dr|Mr|Mrs|Ms)\.",
        lambda match: match.group(0).replace(".", "\u0000"),
        summary.strip(),
    )
    parts = re.split(r"(?<=[.!?])\s+|\n+", protected)
    return [part.replace("\u0000", ".").strip() for part in parts if part.strip()]


def _summary_synthesizes_section(summary: str, section: dict[str, Any]) -> bool:
    contact = str(section.get("contact_name") or "").strip()
    if not contact:
        return True
    point_words = _section_point_words(section)
    if not point_words:
        return contact.lower() in summary.lower()
    return any(
        _sentence_links_contact_to_finding(sentence, contact, point_words)
        for sentence in _summary_sentences(summary)
    )


def _ensure_department_coverage(summary: str, sections: list[dict[str, Any]]) -> str:
    """Add what to ask each contact when the summary never ties that person to a finding."""
    additions: list[str] = []
    current = summary
    for section in sections:
        if _summary_synthesizes_section(current, section):
            continue
        sentence = _coverage_sentence(section)
        if sentence is None:
            continue
        additions.append(sentence)
        current = f"{current} {sentence}"
    if not additions:
        return summary
    base = summary.strip()
    extra = " ".join(additions)
    return f"{base}\n{extra}".strip() if base else extra


def _ensure_missing_budget_question(metadata: dict[str, Any], sections: list[dict[str, Any]]) -> None:
    """A missing budget stays an open question even when the revenue worker omits it."""
    if normalize_optional_metadata_text(metadata.get("budget_range")) is not None:
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


def _ensure_missing_budget_summary(summary: str, metadata: dict[str, Any]) -> str:
    """State that an omitted budget belongs to the source when the summary never says so."""
    if not _budget_was_not_stated(metadata):
        return summary
    if re.search(r"\bsource request did not state a budget\b", summary, re.IGNORECASE):
        return summary
    line = "The source request did not state a budget or payment terms."
    base = summary.strip()
    return f"{base}\n{line}".strip() if base else line


_INTERNAL_DRAFT_LINE = re.compile(
    r"^\s*(?:Missing:|Add more details:|Information still needed:|Information still required:)",
    re.IGNORECASE,
)
_DOLLAR_AMOUNT = re.compile(r"\$\s*\d")
_ENSURES_HIPAA = re.compile(r"\bensures\s+compliance\s+with\s+hipaa\b", re.IGNORECASE)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _normalized_words(sentence: str) -> list[str]:
    # Commas on "Agreement," otherwise prevent token overlap with "Agreement".
    cleaned = re.sub(r"[^a-z0-9]+", " ", sentence.casefold())
    return [word for word in cleaned.split() if word]


_NEGATION_TOKENS = frozenset({"not", "no", "nor", "none", "never", "without", "except", "unless"})
_CONDITION_TOKENS = frozenset(
    {
        "only",
        "before",
        "after",
        "including",
        "excluding",
        "provided",
        "until",
        "if",
        "unless",
        "except",
        "without",
    }
)
_MONTH_TOKENS = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
)


def _content_tokens(words: list[str]) -> set[str]:
    """Tokens used for restatement detection. Short function words are ignored."""
    skip = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "will",
        "need",
        "also",
        "such",
        "as",
        "are",
        "is",
        "to",
        "of",
        "in",
        "a",
        "an",
    }
    kept: set[str] = set()
    for word in words:
        if word in _NEGATION_TOKENS or word in _CONDITION_TOKENS or word in _MONTH_TOKENS:
            kept.add(word)
            continue
        if word.isdigit():
            kept.add(word)
            continue
        if len(word) >= 4 and word not in skip:
            kept.add(word)
    return kept


def _distinguishing_tokens(tokens: set[str]) -> set[str]:
    return {word for word in tokens if word in _NEGATION_TOKENS or word in _CONDITION_TOKENS or word in _MONTH_TOKENS or word.isdigit()}


def _is_near_duplicate_sentence(sentence: str, kept: list[str]) -> bool:
    """Drop restated openings and continuation padding that reuse the same clause."""
    words = _normalized_words(sentence)
    if not words:
        return True
    prefix = " ".join(words[:6] if len(words) >= 6 else words)
    folded = " ".join(words)
    tokens = _content_tokens(words)
    for prior in kept:
        prior_words = _normalized_words(prior)
        prior_tokens = _content_tokens(prior_words)
        if _distinguishing_tokens(tokens) != _distinguishing_tokens(prior_tokens):
            continue
        prior_prefix = " ".join(prior_words[:6] if len(prior_words) >= 6 else prior_words)
        if prefix == prior_prefix:
            return True
        prior_fold = " ".join(prior_words)
        if folded in prior_fold or prior_fold in folded:
            return True
        shared = tokens & prior_tokens
        union = tokens | prior_tokens
        if len(shared) >= 5 and union and len(shared) / len(union) >= 0.62:
            return True
    return False


def sanitize_client_facing_draft(
    draft: str,
    department_id: str,
    metadata: dict[str, Any],
    *,
    key_aspects: list[str] | None = None,
) -> str:
    """Remove generator scaffolding and unsupported claims. Keep legitimate gap statements."""
    from data.pipelines.rfp_intake.source_fidelity import (
        draft_asserts_invented_capacity_commitment,
        draft_asserts_invented_facilities_in_place,
        draft_asserts_unsupported_compliance_assurance,
        draft_asserts_unsupported_price,
        draft_mentions_irrelevant_uk_instrument_for_us_client,
        is_generator_scaffolding_sentence,
        is_redundant_known_fact_question,
        keep_baa_requirement_without_usd_price,
        rewrite_consent_met_as_confirmation,
        rewrite_false_unstated_population,
        rewrite_state_that_category_instruction,
    )

    aspects = key_aspects or []
    sentences = _split_sentences(draft)
    seen: set[str] = set()
    kept: list[str] = []
    for sentence in sentences:
        rewritten_category_instruction = rewrite_state_that_category_instruction(sentence)
        if rewritten_category_instruction is not None:
            sentence = rewritten_category_instruction
        if is_generator_scaffolding_sentence(sentence):
            continue
        if department_id == "clinical" and is_redundant_known_fact_question(sentence, aspects):
            continue
        if department_id == "revenue" and draft_asserts_unsupported_price(sentence, metadata, aspects):
            continue
        if department_id == "revenue":
            rewritten_population = rewrite_false_unstated_population(
                sentence, metadata.get("covered_population")
            )
            if rewritten_population is not None:
                sentence = rewritten_population
        if department_id == "compliance":
            rewritten_baa = keep_baa_requirement_without_usd_price(sentence)
            if rewritten_baa is not None:
                sentence = rewritten_baa
            rewritten_consent = rewrite_consent_met_as_confirmation(sentence)
            if rewritten_consent is not None:
                sentence = rewritten_consent
            if draft_asserts_unsupported_compliance_assurance(sentence):
                continue
        if department_id == "clinical" and (
            draft_asserts_invented_capacity_commitment(sentence)
            or draft_asserts_invented_facilities_in_place(sentence)
        ):
            continue
        if department_id == "compliance" and draft_mentions_irrelevant_uk_instrument_for_us_client(
            sentence, metadata.get("client_country")
        ):
            continue
        key = re.sub(r"\s+", " ", sentence.casefold())
        if key in seen:
            continue
        if _is_near_duplicate_sentence(sentence, kept):
            continue
        seen.add(key)
        kept.append(sentence)
    return " ".join(kept)


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
    grounded_metadata["budget_range"] = normalize_optional_metadata_text(
        metadata.get("budget_range")
    )
    grounded_metadata["deadline"] = preserve_deadline_text(
        normalize_optional_metadata_text(metadata.get("deadline")),
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
                if not _assigns_revenue_staffing(question)
                and not _asks_stated_clinic_schedule(question, source)
                and not _asks_stated_appointment_volume(question, source)
                and not _asks_as_if_service_start_missing(question, source)
            ]
        else:
            questions = [
                question
                for question in questions
                if not _asks_stated_appointment_volume(question, source)
                and not _asks_as_if_service_start_missing(question, source)
            ]
        aspects = [aspect for aspect in aspects if not _assumed_staffing(aspect)]
        if section.get("department_id") != "revenue":
            aspects = [
                aspect for aspect in aspects if not is_proposal_deadline_absence_aspect(aspect)
            ]
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
    _ensure_contract_term(source, grounded_sections)
    _ensure_clinical_demand_facts(source, grounded_sections)

    grounded_summary = _without_revenue_staffing(summary, source)
    grounded_summary = _align_deadline_statement(grounded_summary, source)
    grounded_summary = _reattribute_missing_budget(grounded_summary, grounded_metadata, grounded_sections)
    grounded_summary = _scrub_answered_demand_asks(grounded_summary, source)
    grounded_summary = _ensure_department_coverage(grounded_summary, grounded_sections)
    grounded_summary = _ensure_missing_budget_summary(grounded_summary, grounded_metadata)
    return grounded_metadata, grounded_sections, grounded_summary
