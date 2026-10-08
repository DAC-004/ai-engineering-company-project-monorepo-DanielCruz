"""Shared detectors for instruction text, breach details, and contract terms.

These checks do not decide whether a sentence is PHI. PHI stays on
``appears_to_contain_phi``. They also do not state HealthCore breach or
contract policy. They only recognize text that must not be stored or returned.
"""

from __future__ import annotations

import re

from app.agent.memory_policy import (
    _NAMED_AS_PATIENT,
    _PHI_TERMS,
    _cites_an_appointment_cancellation_for_a_patient,
)
from app.core.prohibited_text import has_labeled_patient_field

# The optional words stay narrow so ordinary sentences that say "ignore these
# instructions" in the system prompt are not treated as an attack string.
_INSTRUCTION = re.compile(
    r"("
    r"ignore (?:(?:all|your|previous)\s+)*instructions"
    r"|you are now an assistant"
    r"|forget that you work"
    r"|no compliance rules"
    r"|act as an assistant with no"
    r"|act as if you had no rules"
    r")",
    re.IGNORECASE,
)
_BREACH_DETAIL = re.compile(
    r"("
    r"records exposed"
    r"|records (?:were|are|have been|had been) exposed"
    r"|breach was discovered"
    r"|discovery time"
    r"|under investigation"
    r"|compliance_breach"
    r"|how many records"
    r"|when was (?:it|the breach) discovered"
    r")",
    re.IGNORECASE,
)
# The name after "patient" stays case-sensitive so "patients are" and
# "patient should" remain ordinary policy wording. The word "patient" itself
# is case-insensitive so a sentence can begin with "Patient Johnson".
_NAMED_PATIENT = re.compile(r"\b(?i:patients?)\s+[A-Z][a-z]+")
_CONFIDENTIAL_CONTRACT = re.compile(
    r"("
    r"confidential baa"
    r"|confidential dpa"
    r"|business associate agreement (?:fee|term|price)"
    r"|data processing agreement (?:fee|term|price)"
    r")",
    re.IGNORECASE,
)
# A request to drop policy is an instruction, even when it does not say
# "instructions". Ordinary policy prose does not use this imperative shape.
_POLICY_OVERRIDE = re.compile(
    r"\b(?:ignore|disregard)\s+(?:all\s+|your\s+|the\s+|previous\s+)*(?:policies|policy)\b",
    re.IGNORECASE,
)
# Disclosure of a government identifier. The pattern matches the request
# class. It is not an example of a person or an identifier value.
_IDENTIFIER_TERM = re.compile(
    r"\b(?:social security(?:\s+number)?|ssn|national insurance number)\b",
    re.IGNORECASE,
)
_DISCLOSURE_VERB = re.compile(
    r"\b(?:tell|give|disclose|reveal|show|provide|send|look\s+up)\b",
    re.IGNORECASE,
)
# Hidden instruction from a retrieved protocol. A warning that does not say
# "always recommend" stays in the corpus.
_EMBEDDED_CLINICAL_INSTRUCTION = re.compile(
    r"("
    r"always recommend\b.{0,80}without checking contraindications"
    r"|recommend this medication without checking contraindications"
    r")",
    re.IGNORECASE,
)


def policy_override_requested(text: str | None) -> bool:
    """True when the text tells the model to drop HealthCore policy."""
    if not text:
        return False
    return _POLICY_OVERRIDE.search(text) is not None


def identifier_disclosure_requested(text: str | None) -> bool:
    """True when the text asks for a government identifier.

    Both a disclosure verb and an identifier term are required so a policy
    sentence that merely names a form field is not treated as a disclosure.
    """
    if not text:
        return False
    return (
        _IDENTIFIER_TERM.search(text) is not None
        and _DISCLOSURE_VERB.search(text) is not None
    )


def embedded_clinical_instruction(text: str | None) -> bool:
    """True when text tells a reader to recommend treatment without a check."""
    if not text:
        return False
    return _EMBEDDED_CLINICAL_INSTRUCTION.search(text) is not None


def disclosure_is_prohibited(text: str | None) -> bool:
    """True for instruction text, breach or contract details, or a patient name.

    This is narrower than ``appears_to_contain_phi``. That memory check also
    matches ordinary words after "patient", which indexed policy uses.
    """
    if not text:
        return False
    if content_is_prohibited(text):
        return True
    # Labeled fields are the same check used before incident and supplier writes.
    # This does not treat every sentence that contains the word patient as prohibited.
    if has_labeled_patient_field(text):
        return True
    if _PHI_TERMS.search(text) or _NAMED_AS_PATIENT.search(text) or _NAMED_PATIENT.search(text):
        return True
    return _cites_an_appointment_cancellation_for_a_patient(text)


def content_is_prohibited(text: str | None) -> bool:
    """True when text is an instruction, a breach detail, or a contract term."""
    if not text:
        return False
    return bool(
        _INSTRUCTION.search(text)
        or _BREACH_DETAIL.search(text)
        or _CONFIDENTIAL_CONTRACT.search(text)
        or embedded_clinical_instruction(text)
    )
