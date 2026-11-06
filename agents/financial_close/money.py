"""Deterministic Decimal arithmetic. Never use float for money or percentages."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from agents.financial_close.constants import DEVIATION_THRESHOLD, FX_GBP_USD


def decimal_from_text(value: str) -> Decimal:
    text = value.strip()
    if text == "" or any(letter in text.lower() for letter in "einfinitynan"):
        raise InvalidOperation("non_decimal")
    return Decimal(text)


def convert_gbp_usd(amount_gbp: Decimal, rate: Decimal = FX_GBP_USD) -> Decimal:
    return amount_gbp * rate


def unsigned_cost(signed_amount: Decimal) -> Decimal:
    return -signed_amount if signed_amount < 0 else signed_amount


def amount_deviation(actual: Decimal | None, budget: Decimal | None, *, incomplete: bool) -> Decimal | None:
    """Signed actual minus budget. Missing or incomplete lines stay None, never zero."""
    if incomplete or actual is None or budget is None:
        return None
    return actual - budget


def percentage_deviation(actual: Decimal, budget: Decimal) -> Decimal | None:
    """(actual - budget) / budget using unrounded Decimal.

    Missing or zero budget never yields a percentage. Caller must not treat
    None as 0% or -100%.
    """
    if budget == 0:
        return None
    return (actual - budget) / budget


def is_relevant(percent: Decimal | None, threshold: Decimal = DEVIATION_THRESHOLD) -> bool:
    if percent is None:
        return False
    return abs(percent) >= threshold


def display_percent(percent: Decimal) -> str:
    quantized = (percent * Decimal("100")).quantize(Decimal("0.1"))
    return f"{quantized}%"
