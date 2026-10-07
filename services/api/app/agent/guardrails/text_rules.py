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


def disclosure_is_prohibited(text: str | None) -> bool:
    """True for instruction text, breach or contract details, or a patient name.

    This is narrower than ``appears_to_contain_phi``. That memory check also
    matches ordinary words after "patient", which indexed policy uses.
    """
    if not text:
        return False
    if content_is_prohibited(text):
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
    )
