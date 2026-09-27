"""Explicit memory rules for the HealthCore support agent.

The criterion decides whether a turn is worth a proposal. Intent classification
decides what a later message does to a pending proposal. Neither path treats
a substring such as "yes" as approval, and neither path can mark a claim verified.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Literal

MemoryKind = Literal["clinic_protocol", "incident_pattern", "staff_preference"]
IntentLabel = Literal["approve", "reject", "edit", "unclear"]

# Appearance check only. A miss does not mean the text is safe.
PHI_WITHHELD = "phi withheld"
PHI_REFUSAL = (
    "I can't remember that. Patient information cannot be stored in agent memory "
    "under HIPAA or UK GDPR."
)
UNVERIFIED_NOTE_LABEL = "Unverified staff-approved note"
CONFIDENCE_FLOOR = 0.6

_CLINICS = (
    "austin",
    "houston",
    "miami",
    "orlando",
    "atlanta",
    "london",
    "manchester",
)
_PATIENT_NAME = re.compile(r"\bpatients?\s+[A-Za-z][A-Za-z'-]+\b", re.IGNORECASE)
_PHI_TERMS = re.compile(
    r"\b("
    r"medical record|mrn|date of birth|\bdob\b|diagnosis|diagnosed|"
    r"insurance number|nhs number|national insurance|"
    r"lab results?|clinical notes?|"
    r"member identifier"
    r")\b",
    re.IGNORECASE,
)
_CLOSING = re.compile(
    r"\b(thanks|thank you|that settles|goodbye|that's all|that is all)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"^\s*(how|what|what's|when|where|why|which|who|can you|could you)\b|\?\s*$",
    re.IGNORECASE,
)
_CHANGE = re.compile(
    r"\b(now|changed|change|go through|goes through|before the specialist|"
    r"no longer|instead|because of|not a real problem|needs)\b",
    re.IGNORECASE,
)
_PROTOCOL = re.compile(
    r"\b(referrals?|protocols?|schedules?|front[- ]desk|reminders?)\b",
    re.IGNORECASE,
)
_INCIDENT = re.compile(
    r"\b(road closure|overnight batch|monday morning)\b",
    re.IGNORECASE,
)
_STAFF = re.compile(r"\bdiane foster\b", re.IGNORECASE)
_PREFERENCE = re.compile(r"\b(vacanc(?:y|ies)|by role|weekly report)\b", re.IGNORECASE)


@dataclass(frozen=True)
class MemoryCandidate:
    """A proposal the criterion is willing to show. It is not stored yet."""

    kind: MemoryKind
    subject_key: str
    proposal_text: str
    reason: str


@dataclass(frozen=True)
class IntentDecision:
    """Classification of one message against one pending proposal."""

    label: IntentLabel
    confidence: float = 1.0
    revised_text: str | None = None
    residual_question: str | None = None


def appears_to_contain_phi(text: str) -> bool:
    """Return whether the text appears to carry a patient identifier or visit content.

    Staff names used in operational preferences, such as Diane Foster, do not
    match this check by themselves. The check is not a complete detector of
    every PHI phrase under HIPAA or UK GDPR.
    """
    if not text or not text.strip():
        return False
    if _PATIENT_NAME.search(text):
        return True
    if _PHI_TERMS.search(text):
        return True
    lowered = text.casefold()
    if "appointment" in lowered and "cancel" in lowered and "patient" in lowered:
        return True
    return False


def normalize_memory_text(text: str) -> str:
    """Compare proposals without spacing or case differences."""
    return " ".join(text.casefold().split())


def evaluate_memorable(text: str) -> MemoryCandidate | None:
    """Return a candidate only for a new operational fact of an allowed kind.

    One-off dashboard questions and conversation closings return None. Most
    turns therefore produce nothing to remember. Patient content is refused
    by the caller before this function runs; this function also refuses it
    so a candidate cannot be built from that text.
    """
    cleaned = " ".join(text.split())
    if not cleaned or appears_to_contain_phi(cleaned):
        return None
    if _is_dashboard_question(cleaned) or (_CLOSING.search(cleaned) and not _CHANGE.search(cleaned)):
        return None

    lowered = cleaned.casefold()
    clinic = _named_clinic(lowered)
    if _INCIDENT.search(cleaned) and (clinic or "no-show" in lowered or "noshow" in lowered):
        subject = f"{clinic or 'network'}_incident_pattern"
        return MemoryCandidate(
            kind="incident_pattern",
            subject_key=subject,
            proposal_text=cleaned,
            reason="Patient-free incident pattern for clinic operations.",
        )
    if _STAFF.search(cleaned) and _PREFERENCE.search(cleaned):
        return MemoryCandidate(
            kind="staff_preference",
            subject_key="diane_foster_vacancy_report",
            proposal_text=cleaned,
            reason="Staff preference for how operational information is presented.",
        )
    protocol_change = _PROTOCOL.search(cleaned) and _CHANGE.search(cleaned)
    if protocol_change and (clinic or "referral" in lowered) and not _is_bare_question(cleaned):
        subject = f"{clinic or 'network'}_operational_protocol"
        if "referral" in lowered:
            subject = f"{clinic or 'network'}_internal_referrals"
        return MemoryCandidate(
            kind="clinic_protocol",
            subject_key=subject,
            proposal_text=cleaned,
            reason="Recurring operational correction for a clinic process.",
        )
    return None


def proposal_prompt(proposal_text: str) -> str:
    """Question shown in the same reply. The fact is not written by this string."""
    return f"Want me to remember this for next time? {proposal_text}"


def unverified_note_sentence(proposal_text: str) -> str:
    """Label a stored note as authorized but not checked for truth."""
    return (
        f"{UNVERIFIED_NOTE_LABEL}: {proposal_text} "
        "This note was not checked against company knowledge."
    )


def classify_pending_intent(
    message: str,
    pending_text: str,
    *,
    model: Callable[[str, str], str] | None = None,
) -> IntentDecision:
    """Classify a reply to one pending proposal from structured model output.

    Invalid JSON, an unknown label, or confidence below the floor becomes
    ``unclear``. The message text is not searched for approval words.
    """
    completer = model if model is not None else _model_completer
    try:
        raw = completer(message, pending_text)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Intent output must be a JSON object.")
        label = parsed.get("label")
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return IntentDecision(label="unclear", confidence=0.0)
    if label not in {"approve", "reject", "edit", "unclear"} or confidence < CONFIDENCE_FLOOR:
        return IntentDecision(label="unclear", confidence=confidence if label else 0.0)
    revised = parsed.get("revised_text")
    residual = parsed.get("residual_question")
    return IntentDecision(
        label=label,
        confidence=confidence,
        revised_text=revised if isinstance(revised, str) and revised.strip() else None,
        residual_question=residual if isinstance(residual, str) and residual.strip() else None,
    )


def _model_completer(message: str, pending_text: str) -> str:
    """Ask the existing generator for one JSON intent object.

    Any failure, including a missing local model, is raised to the caller and
    becomes ``unclear``. This function does not decide the label itself.
    """
    from data.pipelines.rag import _run_generation_model

    messages = [
        {
            "role": "system",
            "content": (
                "Classify the user message against the pending operational-memory "
                "proposal. Reply with one JSON object and no other text. "
                'Keys: "label" (approve, reject, edit, or unclear), '
                '"confidence" (0 to 1), "revised_text" (string or null), '
                '"residual_question" (string or null). '
                "Use unclear when the message is not a clear decision. "
                "Do not treat silence or a topic change as approval."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Pending proposal:\n{pending_text}\n\nUser message:\n{message}"
            ),
        },
    ]
    return _run_generation_model(messages)


def _named_clinic(lowered: str) -> str | None:
    for clinic in _CLINICS:
        if re.search(rf"\b{clinic}\b", lowered):
            return clinic
    return None


def _is_dashboard_question(text: str) -> bool:
    lowered = text.casefold()
    asks_rate = "no-show rate" in lowered or "noshow rate" in lowered
    if not asks_rate:
        return False
    return "?" in text or lowered.startswith("what")


def _is_bare_question(text: str) -> bool:
    """A how/what question is not a correction unless it also states a change."""
    if not _QUESTION.search(text):
        return False
    return _CHANGE.search(text) is None
