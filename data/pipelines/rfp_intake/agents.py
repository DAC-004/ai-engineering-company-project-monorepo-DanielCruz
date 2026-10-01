"""Separate RFP agents. Each one has its own role, input, and JSON output.

The graph calls these functions. It does not decide for them. A missing local
model raises ModelAssetMissing. These functions do not keyword-classify the
document when that happens.
"""

from __future__ import annotations

import json
import re
from typing import Any

from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS, DEPARTMENTS, country_rule
from data.pipelines.rfp_intake.generation import ChatComplete, PipelineFailure, complete_local
from data.pipelines.rfp_intake.phi import screen_structure, screen_text

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

CLASSIFIER_ROLE = (
    "You are the HealthCore RFP classifier agent. "
    "Read only the user document. "
    "Return JSON with keys decision and reason_code. "
    "decision is accept or discard. "
    "reason_code is healthcore_rfp or not_healthcore_rfp. "
    "Accept a client request for occupational health, corporate wellness, or a referral partnership, "
    "including an informal email that asks HealthCore for a proposal. "
    "Discard a vendor pitch or any document that is not a request for a HealthCore proposal. "
    "Do not copy document text into the JSON."
)

ORCHESTRATOR_ROLE = (
    "You are the HealthCore RFP orchestrator agent. "
    "You do not write department key aspects. "
    "Split the document into shared metadata and one extract each for revenue, clinical, and compliance. "
    "Copy figures only when they appear in the document. "
    "Keep approximate wording such as 'about 3,000' and relative timing such as 'about 25 days' or 'around August 28'. "
    "When the document states more than one deadline qualifier, keep every qualifier. "
    "Do not add a year the document does not state. "
    "A clinic staffing schedule belongs in the clinical extract. "
    "A stated contract duration and renewal option belongs in the revenue extract. "
    "Use null for a missing budget, headcount, or deadline. "
    "unknown_departments lists names outside revenue, clinical, and compliance. "
    "Return JSON with keys client_name, client_country, program_type, covered_population, deadline, "
    "budget_range, unknown_departments, and extracts. "
    "client_country is US, UK, or null. "
    "extracts has keys revenue, clinical, and compliance. Each extract is only the text that department needs."
)

WORKER_ROLES = {
    "revenue": (
        "You are the HealthCore revenue worker agent for Tom Callahan in Revenue Cycle. "
        "You see shared metadata and the revenue extract only. "
        "Return JSON with keys aspects and open_questions, both arrays of strings. "
        "If budget or payment terms are absent, add an open question. Do not invent amounts. "
        "If the extract states a contract duration or an option to renew, include that term as a key aspect. "
    "Do not say Revenue Cycle is staffed, scheduled, or sized from a clinic or program fact "
    "unless the revenue extract itself states that. "
    "Do not ask whether Revenue Cycle has a staffing requirement because a clinic is staffed. "
    "Do not call a deadline reasonable."
    ),
    "clinical": (
        "You are the HealthCore clinical worker agent for Dr. Marcus Reid in Clinical Operations. "
        "You see shared metadata and the clinical extract only. "
        "Return JSON with keys aspects and open_questions, both arrays of strings. "
        "If headcount, sites, or staffing volume is absent, add an open question. Do not invent figures. "
        "If the extract states how many days a clinic is staffed, include that schedule as a key aspect. "
        "Do not ask whether another department is staffed."
    ),
    "compliance": (
        "You are the HealthCore compliance worker agent for Claire Whitfield. "
        "You see shared metadata and the compliance extract only. "
        "Compliance reviews every accepted RFP. "
        "A US client needs USD and a Business Associate Agreement. "
        "A UK client needs GBP and a Data Processing Agreement referencing UK GDPR. "
        "Return JSON with keys aspects and open_questions, both arrays of strings. "
        "Do not invent a country."
    ),
}

SYNTHESIZER_ROLE = (
    "You are the HealthCore synthesizer agent. "
    "You see worker results and the fixed contacts only. You do not read the original document. "
    "Write one Sales summary that names every department contact and states what to ask that contact. "
    "When budget or payment terms are missing, say the source request did not state them. "
    "Do not say a department contact failed to provide a figure the source request omitted. "
    "If two workers state conflicting figures or facts, keep both and mark that disagreement unresolved. "
    "A missing budget, headcount, deadline, or payment term is an open question, not a disagreement. "
    "Do not say Revenue Cycle is staffed on a schedule unless the revenue section states that schedule. "
    "Do not ask about revenue staffing unless the revenue section states it. "
    "Do not describe a deadline as reasonable. "
    "Keep every deadline qualifier the workers stated, and do not add a year. "
    "Return JSON with keys summary and unresolved_disagreements. "
    "summary is a string. unresolved_disagreements is an array of strings."
)


def _complete(messages: list[dict[str, str]], complete_fn: ChatComplete | None) -> str:
    if complete_fn is None:
        return complete_local(messages)
    return complete_fn(messages)


def _parse_object(raw: str) -> dict[str, Any]:
    """Parse the first JSON object. Trailing model prose is ignored.

    The local model sometimes closes the object and then adds a sentence.
    The agents still supply the object. The extra sentence is not a second result.
    """
    cleaned = _FENCE.sub("", raw.strip())
    start = cleaned.find("{")
    if start < 0:
        raise PipelineFailure("model_output_invalid")
    try:
        parsed, _end = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise PipelineFailure("model_output_invalid") from exc
    if not isinstance(parsed, dict):
        raise PipelineFailure("model_output_invalid")
    return parsed


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


_FIGURE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
_MISSING_INFORMATION = re.compile(
    r"\b(missing|not stated|not provided|absent|no budget|was not stated|unknown|unavailable|not specified)\b",
    re.IGNORECASE,
)


def _source_text(metadata: dict[str, Any], extract: str) -> str:
    """Text the worker was allowed to see, used to check later claims."""
    parts = [extract]
    for value in metadata.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(item for item in value if isinstance(item, str))
    return "\n".join(parts)


def _department_is_staffing_subject(text: str, department_name: str) -> bool:
    """True when the sentence says this department itself is staffed."""
    names = [department_name]
    first_word = department_name.split()[0]
    if first_word and first_word not in names:
        names.append(first_word)
    pattern = "|".join(re.escape(name) for name in names)
    return re.search(
        rf"\b(?:{pattern})\b.{{0,160}}\bstaff(?:ed|ing)?\b",
        text,
        re.IGNORECASE,
    ) is not None


def _aspect_is_grounded(aspect: str, source: str, department_name: str) -> bool:
    """Drop a claim whose figure or staffing subject is not in the worker's source.

    A clinic schedule can appear beside revenue text. That does not make it a
    Revenue Cycle staffing fact. The figure has to be present, and a sentence
    that says this department is staffed has to say so in the source as well.
    """
    for figure in _FIGURE.findall(aspect):
        if figure not in source:
            return False
    if _department_is_staffing_subject(aspect, department_name) and not _department_is_staffing_subject(
        source, department_name
    ):
        return False
    return True


def _is_actual_contradiction(text: str) -> bool:
    """A missing value is an open question. A contradiction states a real conflict."""
    stripped = text.strip()
    if not stripped or stripped.endswith("?"):
        return False
    lowered = stripped.lower()
    if "disagree" in lowered or "contradict" in lowered or "conflict" in lowered:
        return True
    if len(set(_FIGURE.findall(stripped))) >= 2:
        return True
    if _MISSING_INFORMATION.search(stripped):
        return False
    return False


def _scrub_summary(summary: str, sections: list[dict[str, Any]]) -> str:
    """Remove summary sentences that assign a department a staffing fact it did not state."""
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", summary.strip()):
        if not sentence.strip():
            continue
        unsupported = False
        for section in sections:
            department_name = str(section.get("department_name") or "")
            if not department_name:
                continue
            if not _department_is_staffing_subject(sentence, department_name):
                continue
            aspects = " ".join(section.get("aspects") or [])
            if not _department_is_staffing_subject(aspects, department_name):
                unsupported = True
                break
        if not unsupported:
            kept.append(sentence.strip())
    return " ".join(kept)


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def classify_rfp(markdown: str, complete_fn: ChatComplete | None = None) -> dict[str, str]:
    """Classifier agent. Input is the screened Markdown and nothing else."""
    raw = _complete(
        [
            {"role": "system", "content": CLASSIFIER_ROLE},
            {"role": "user", "content": markdown},
        ],
        complete_fn,
    )
    parsed = _parse_object(raw)
    decision = parsed.get("decision")
    reason_code = parsed.get("reason_code")
    if decision not in {"accept", "discard"} or reason_code not in {"healthcore_rfp", "not_healthcore_rfp"}:
        raise PipelineFailure("model_output_invalid")
    # Only the two enum fields are kept, so this output cannot carry document text.
    return {"decision": decision, "reason_code": reason_code}


def orchestrate_rfp(markdown: str, complete_fn: ChatComplete | None = None) -> dict[str, Any]:
    """Orchestrator agent. It decomposes the document and does not write key aspects."""
    raw = _complete(
        [
            {"role": "system", "content": ORCHESTRATOR_ROLE},
            {"role": "user", "content": markdown},
        ],
        complete_fn,
    )
    parsed = _parse_object(raw)
    country = parsed.get("client_country")
    if country not in {"US", "UK", None}:
        country = None
    extracts_raw = parsed.get("extracts")
    if not isinstance(extracts_raw, dict):
        raise PipelineFailure("model_output_invalid")
    extracts = {department_id: _optional_text(extracts_raw.get(department_id)) or "" for department_id in DEPARTMENT_IDS}
    payload = {
        "client_name": _optional_text(parsed.get("client_name")),
        "client_country": country,
        "program_type": _optional_text(parsed.get("program_type")),
        "covered_population": _optional_text(parsed.get("covered_population")),
        "deadline": _optional_text(parsed.get("deadline")),
        "budget_range": _optional_text(parsed.get("budget_range")),
        "unknown_departments": _string_list(parsed.get("unknown_departments")),
        "extracts": extracts,
    }
    screened, _detected, _blocked = screen_structure(payload)
    return screened  # type: ignore[return-value]


def analyze_department(
    department_id: str,
    metadata: dict[str, Any],
    extract: str,
    complete_fn: ChatComplete | None = None,
) -> dict[str, Any]:
    """One worker agent. It receives metadata and its own extract, not the full document."""
    if department_id not in WORKER_ROLES:
        raise PipelineFailure("unknown_department")
    user_payload = json.dumps(
        {"metadata": metadata, "extract": extract},
        ensure_ascii=True,
    )
    raw = _complete(
        [
            {"role": "system", "content": WORKER_ROLES[department_id]},
            {"role": "user", "content": user_payload},
        ],
        complete_fn,
    )
    parsed = _parse_object(raw)
    department_name = DEPARTMENTS[department_id]["department_name"]
    source = _source_text(metadata, extract)
    section = {
        "department_id": department_id,
        "department_name": department_name,
        "contact_name": DEPARTMENTS[department_id]["contact_name"],
        "aspects": [
            aspect
            for aspect in _string_list(parsed.get("aspects"))
            if _aspect_is_grounded(aspect, source, department_name)
        ],
        "open_questions": _string_list(parsed.get("open_questions")),
    }
    screened, _detected, _blocked = screen_structure(section)
    return screened  # type: ignore[return-value]


def synthesize_findings(
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
    complete_fn: ChatComplete | None = None,
) -> dict[str, Any]:
    """Synthesizer agent. Input is worker output and contacts, not the PDF."""
    user_payload = json.dumps(
        {
            "metadata": metadata,
            "sections": sections,
            "country_rule": country_rule(metadata.get("client_country")),
        },
        ensure_ascii=True,
    )
    raw = _complete(
        [
            {"role": "system", "content": SYNTHESIZER_ROLE},
            {"role": "user", "content": user_payload},
        ],
        complete_fn,
    )
    parsed = _parse_object(raw)
    summary_value = parsed.get("summary")
    disagreement_value = parsed.get("unresolved_disagreements", [])
    # A parsed object can still have the wrong shape. Coercing it would hide a bad completion.
    if not isinstance(summary_value, str) or not isinstance(disagreement_value, list):
        raise PipelineFailure("model_output_invalid")
    if any(not isinstance(item, str) for item in disagreement_value):
        raise PipelineFailure("model_output_invalid")
    summary = summary_value.strip()
    summary = _scrub_summary(summary, sections)
    disagreements = [
        item for item in _string_list(disagreement_value) if _is_actual_contradiction(item)
    ]
    rule = country_rule(metadata.get("client_country"))
    if rule not in summary:
        summary = f"{summary}\n{rule}".strip()
    if disagreements:
        summary = f"{summary}\nUnresolved disagreement: {'; '.join(disagreements)}".strip()
    screened = screen_text(summary)
    return {
        "summary": screened.text,
        "unresolved_disagreements": disagreements,
        "phi_detected": screened.detected,
    }
