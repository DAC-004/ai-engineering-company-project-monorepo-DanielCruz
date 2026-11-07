"""Grounded Q&A: cite official material or route. Never invent an answer.

Lexical overlap is not coverage. A distinctive claim token that never appears
in the allowed official documents, or a number absent from the cited section,
means the question is uncovered and must be routed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agents.onboarding_orchestrator.content import (
    DOCUMENT_FILES,
    DocumentSection,
    load_documents,
    sections_for,
    token_overlap,
)
from agents.onboarding_orchestrator.state import (
    FRAMEWORK_HIPAA,
    FRAMEWORK_UK_GDPR,
    ROLE_DIGITAL_ENGINEER,
    ROLE_REVENUE_ANALYST,
)

_MIN_OVERLAP = 3

_COMPLIANCE_MARKERS = frozenset(
    {
        "hipaa",
        "gdpr",
        "compliance",
        "minimum",
        "necessary",
        "breach",
        "incident",
        "phi",
        "article",
        "notification",
        "72",
        "60",
        "logging",
        "lawful",
        "baa",
        "fine",
    }
)

# Verbs and fillers that do not establish a documented fact.
_WEAK_TOKENS = frozenset(
    {
        "what",
        "which",
        "where",
        "when",
        "does",
        "do",
        "how",
        "many",
        "much",
        "let",
        "take",
        "home",
        "over",
        "without",
        "applies",
        "apply",
        "amount",
        "staff",
        "time",
        "leave",
        "year",
        "founded",
    }
)


@dataclass(frozen=True)
class GroundedAnswer:
    covered: bool
    answer: str
    source_document: str
    source_heading: str
    route_to: str | None


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _is_compliance_question(question: str) -> bool:
    tokens = _tokenize(question)
    return bool(tokens & _COMPLIANCE_MARKERS) or "minimum necessary" in question.lower()


def allowed_document_ids(*, framework: str | None, role_key: str | None) -> list[str]:
    """Restrict retrieval so a UK hire cannot be shown a US-only compliance window."""
    allowed = ["stage-02-the-company", "stage-03-how-we-operate", "stage-06-how-we-work"]
    if framework == FRAMEWORK_UK_GDPR:
        allowed.append("stage-04-compliance-uk-gdpr")
    elif framework == FRAMEWORK_HIPAA:
        allowed.append("stage-04-compliance-hipaa")
    if role_key == ROLE_REVENUE_ANALYST:
        allowed.append("stage-05-role-revenue-cycle-analyst")
    elif role_key == ROLE_DIGITAL_ENGINEER:
        allowed.append("stage-05-role-digital-engineer")
    elif role_key is None:
        allowed.extend(
            [
                "stage-05-role-digital-engineer",
                "stage-05-role-revenue-cycle-analyst",
            ]
        )
    return [item for item in allowed if item in DOCUMENT_FILES]


def _corpus_tokens(document_ids: list[str]) -> set[str]:
    tokens: set[str] = set()
    bodies = load_documents()
    for document_id in document_ids:
        tokens |= _tokenize(bodies[document_id])
    return tokens


def _claim_tokens_missing_from_corpus(question: str, corpus: set[str]) -> set[str]:
    distinctive = _tokenize(question) - _WEAK_TOKENS
    return {token for token in distinctive if token not in corpus and len(token) > 2}


def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def _uncovered(question: str, *, route: str) -> GroundedAnswer:
    target = "Claire Whitfield" if route == "claire" else "Diane Foster"
    return GroundedAnswer(
        covered=False,
        answer=(
            "This question is not covered by official onboarding material. "
            f"It is routed to {target} instead of an invented answer."
        ),
        source_document="",
        source_heading="",
        route_to=route,
    )


def answer_question(
    question: str,
    *,
    framework: str | None = None,
    role_key: str | None = None,
) -> GroundedAnswer:
    """Return a cited paragraph only when the allowed official text supports the asked fact."""
    allowed = allowed_document_ids(framework=framework, role_key=role_key)
    route = "claire" if _is_compliance_question(question) else "diane"
    if not allowed:
        return _uncovered(question, route=route)

    # Both compliance variants in one search would let a generic notification
    # question pick a US window for a UK hire. Require an explicit framework.
    if framework is None and _is_compliance_question(question):
        both = "stage-04-compliance-hipaa" in DOCUMENT_FILES and "stage-04-compliance-uk-gdpr" in DOCUMENT_FILES
        if both and ("notification" in question.lower() or "window" in question.lower()):
            return _uncovered(question, route="claire")

    corpus = _corpus_tokens(allowed)
    if _claim_tokens_missing_from_corpus(question, corpus):
        return _uncovered(question, route=route)

    best: tuple[int, DocumentSection] | None = None
    for document_id in allowed:
        for section in sections_for(document_id):
            overlap = token_overlap(question, section)
            if best is None or overlap > best[0]:
                best = (overlap, section)
    if best is None or best[0] < _MIN_OVERLAP:
        return _uncovered(question, route=route)

    section = best[1]
    question_numbers = _numbers_in(question)
    if question_numbers and not question_numbers.issubset(_numbers_in(section.text)):
        return _uncovered(question, route=route)
    return GroundedAnswer(
        covered=True,
        answer=section.text,
        source_document=section.document_id,
        source_heading=section.heading,
        route_to=None,
    )
