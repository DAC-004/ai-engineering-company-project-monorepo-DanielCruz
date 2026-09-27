"""Classify a question before retrieval, tools, generation, or checkpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agent.guardrails.text_rules import content_is_prohibited

CASUAL_FRANCE = (
    "Paris is a general fact, not a HealthCore policy. Please ask about "
    "HealthCore appointments, insurance, referrals, or the new-patient checklist."
)
CASUAL_OTHER = (
    "I don't have a live clock for that question. Please ask about HealthCore "
    "appointments, insurance, referrals, or the new-patient checklist."
)
GENERAL_REGULATION = (
    "That is general industry context. Ask a HealthCore question about what "
    "HIPAA or UK GDPR permits. The indexed compliance reference answers that "
    "from HHS or ICO guidance, and it is not a previously issued internal "
    "HealthCore policy."
)
BREACH_NOTIFICATION = (
    "HealthCore's breach-notification comparison is 60 days under HIPAA and "
    "72 hours to the ICO under UK GDPR. The indexed library has no separate "
    "breach-notification document to cite."
)
CONTRACT_SCOPE = (
    "US vendors are handled with a Business Associate Agreement. UK vendors "
    "are handled with a Data Processing Agreement. Confidential commercial "
    "terms of those agreements are not disclosed."
)
CONTRACT_REFUSAL = (
    "I can't disclose confidential commercial terms of a vendor agreement. "
    "US vendors use a Business Associate Agreement and UK vendors use a "
    "Data Processing Agreement."
)
PERSONAL_REFUSAL = (
    "I can't help with personal tasks. Please ask a HealthCore policy question."
)
JAILBREAK_REFUSAL = (
    "I can't change my instructions. Please ask a HealthCore policy question."
)
PATIENT_REFUSAL = (
    "I can't use identifiable patient details. Rephrase the question without "
    "names, ages, diagnoses, locations, or record numbers."
)
BREACH_REFUSAL = "I can't confirm incident details for that request."

_CAPITAL = re.compile(r"\bcapital of\b", re.IGNORECASE)
_TIME = re.compile(r"\bwhat time is it\b", re.IGNORECASE)
_PERSONAL = re.compile(
    r"\b(salary|personal email|love poem|homework|therapist|essay|write code)\b",
    re.IGNORECASE,
)
_PERMISSIBILITY = re.compile(r"\bpermissib", re.IGNORECASE)
_PATIENT_CASE = re.compile(r"\bi have a patient\b", re.IGNORECASE)
_QUASI_IDENTIFIER = re.compile(
    r"\bage\s+\d{1,3}\b.{0,80}\b(austin|houston|miami|orlando|atlanta|london|manchester)\b"
    r"|\b(austin|houston|miami|orlando|atlanta|london|manchester)\b.{0,80}\bage\s+\d{1,3}\b",
    re.IGNORECASE,
)
# Indexed clinic operations stay on the knowledge path, including the
# checklist sentence that names HIPAA only to choose a consent form.
_INDEXED_TOPIC = re.compile(
    r"\b("
    r"appointments?|referrals?|insurance|checklists?|consent forms?|"
    r"no-shows?|cancellations?|medicare|medicaid|new patients?"
    r")\b",
    re.IGNORECASE,
)
# A HealthCore-specific compliance question stays on the knowledge path.
# Empty retrieval then returns the existing insufficient-information sentence.
# That sentence is not an authoritative HIPAA, breach, or contract answer.
_HEALTHCORE_SPECIFIC = re.compile(
    r"\b(healthcore|our policy|our procedure|our breach)\b",
    re.IGNORECASE,
)
_GENERAL_REGULATION = re.compile(
    r"\b("
    r"hipaa|gdpr|business associate|data processing agreement|"
    r"breach notification|protected health information"
    r")\b",
    re.IGNORECASE,
)
_BREACH_PROCEDURE = re.compile(r"\bbreach notification\b", re.IGNORECASE)
_CONTRACT_TOPIC = re.compile(
    r"\b(business associate|data processing agreement|\bbaa\b|\bdpa\b)\b",
    re.IGNORECASE,
)
_CONTRACT_TERMS = re.compile(
    r"\b(fee|price|commercial terms|confidential)\b",
    re.IGNORECASE,
)
_BREACH_PROBE = re.compile(
    r"("
    r"when was (?:it|the breach) discovered"
    r"|how many records"
    r"|which clinic.{0,40}breach"
    r"|breach.{0,40}which clinic"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InputDecision:
    """Fixed response for a blocked or redirected question."""

    allowed: bool
    response: str
    trace_label: str
    action: str
    failure_type: str
    guardrail: str


def screen_question(question: str) -> InputDecision:
    """Allow an in-domain question, or return a fixed response that omits it.

    Empty text is allowed so the graph can keep its existing empty-question
    rejection. A match does not echo the question.
    """
    if not isinstance(question, str) or not question.strip():
        return InputDecision(True, "", "", "allow", "", "")

    if content_is_prohibited(question) and _looks_like_jailbreak(question):
        return _block("jailbreak", JAILBREAK_REFUSAL, "security")
    if _BREACH_PROBE.search(question):
        return _block("breach_probe", BREACH_REFUSAL, "content")
    if _PATIENT_CASE.search(question) or _QUASI_IDENTIFIER.search(question):
        return _block("patient_case", PATIENT_REFUSAL, "content")
    if _PERSONAL.search(question):
        return _block("personal_task", PERSONAL_REFUSAL, "content")
    if _BREACH_PROCEDURE.search(question):
        return _answer("domain_breach_notification", BREACH_NOTIFICATION)
    if _CONTRACT_TOPIC.search(question):
        if _CONTRACT_TERMS.search(question):
            return _block("contract_terms", CONTRACT_REFUSAL, "content")
        return _answer("domain_contract", CONTRACT_SCOPE)
    if _CAPITAL.search(question) or _TIME.search(question):
        response = CASUAL_FRANCE if "france" in question.lower() else CASUAL_OTHER
        return InputDecision(
            allowed=False,
            response=response,
            trace_label="casual",
            action="redirect",
            failure_type="content",
            guardrail="input_scope",
        )
    if _is_general_regulation(question):
        return InputDecision(
            allowed=False,
            response=GENERAL_REGULATION,
            trace_label="general_regulation",
            action="redirect",
            failure_type="content",
            guardrail="input_scope",
        )
    return InputDecision(True, "", "", "allow", "", "")


def _is_general_regulation(question: str) -> bool:
    """True for industry regulation that is not an indexed HealthCore question.

    Naming HealthCore, or naming an indexed appointment, referral, insurance,
    or checklist topic, keeps the question on the knowledge path.
    """
    if not _GENERAL_REGULATION.search(question):
        return False
    # Permissibility is an in-domain question. The compliance reference
    # answers it through retrieval. A general industry question still redirects.
    if _PERMISSIBILITY.search(question):
        return False
    if _HEALTHCORE_SPECIFIC.search(question) or _INDEXED_TOPIC.search(question):
        return False
    return True


def _looks_like_jailbreak(question: str) -> bool:
    lowered = question.lower()
    return (
        "ignore your instructions" in lowered
        or "ignore your previous instructions" in lowered
        or "you are now" in lowered
        or "forget that you work" in lowered
        or "no compliance rules" in lowered
        or "no rules" in lowered
    )


def _answer(label: str, response: str) -> InputDecision:
    """Return a domain fact without retrieval. This is not a block or redirect."""
    return InputDecision(
        allowed=False,
        response=response,
        trace_label=label,
        action="answer",
        failure_type="",
        guardrail="input_scope",
    )


def _block(label: str, response: str, failure_type: str) -> InputDecision:
    return InputDecision(
        allowed=False,
        response=response,
        trace_label=label,
        action="block",
        failure_type=failure_type,
        guardrail="input_scope",
    )
