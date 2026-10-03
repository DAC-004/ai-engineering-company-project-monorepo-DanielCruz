"""Decide which ticket fields may be copied into an answer."""

from __future__ import annotations

from typing import Any

from app.agent.guardrails.text_rules import disclosure_is_prohibited

_FIELD_NAMES = (
    "id",
    "status",
    "category",
    "origin",
    "branch",
    "title",
    "description",
    "created_at",
    "updated_at",
)


def _field(row: Any, name: str) -> str:
    if isinstance(row, dict):
        value = row.get(name, "")
    else:
        value = getattr(row, name, "")
    return "" if value is None else str(value)


def row_verdict(row: Any) -> str:
    """Return allow, withhold, or malformed. Do not copy a failed row."""
    if row is None:
        return "malformed"
    category = _field(row, "category").strip()
    if category == "compliance_breach":
        return "withhold"
    blob = "\n".join(_field(row, name) for name in _FIELD_NAMES)
    if disclosure_is_prohibited(blob):
        return "withhold"
    if not _field(row, "id").strip() or not _field(row, "status").strip():
        return "malformed"
    return "allow"


def partition_rows(rows: list[Any]) -> tuple[list[Any], bool, bool]:
    """Split rows into quotable rows plus withhold and malformed flags."""
    allowed: list[Any] = []
    withheld = False
    malformed = False
    for row in rows:
        verdict = row_verdict(row)
        if verdict == "allow":
            allowed.append(row)
        elif verdict == "withhold":
            withheld = True
        else:
            malformed = True
    return allowed, withheld, malformed
