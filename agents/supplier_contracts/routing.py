"""Deterministic question classifier. This is not an LLM and does not invent figures."""

from __future__ import annotations

from agents.supplier_contracts.types import RequestKind


def classify_question(kind: RequestKind, question: str) -> RequestKind:
    """Map free-text questions onto a specialist route without hidden kind selection.

    The assignment's supervisor decides whom to consult. Classification is an
    explicit keyword router so alternatives, notice dates, and briefs work from
    the question string. Arithmetic and clause extraction stay in deterministic
    specialist tools.
    """
    if kind != "question":
        return kind
    text = question.lower()
    if any(token in text for token in ("brief", "renegot")):
        return "brief"
    if any(token in text for token in ("draft", "write to the supplier", "communication to")):
        return "draft_communication"
    if any(token in text for token in ("alternative", "compar", "quote")):
        return "compare"
    if any(token in text for token in ("notice", "expir", "deadline", "renew")):
        return "question"
    if any(token in text for token in ("dpa", "baa", "missing agreement")):
        return "missing_agreements"
    if any(token in text for token in ("increase", "impact", "threshold", "price")):
        return "evaluate_increase"
    return "evaluate_increase"


def pricing_calculation(kind: RequestKind) -> str:
    if kind in {"compare"}:
        return "compare"
    if kind in {"evaluate_increase", "impact", "brief", "draft_communication"}:
        return "increase"
    return "history"
