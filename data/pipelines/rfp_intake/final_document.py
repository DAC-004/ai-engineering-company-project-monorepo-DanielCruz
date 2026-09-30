"""Deterministic final document. This is not an LLM rewrite of the sections."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_final_document(
    ticket_id: str,
    ordered_sections: list[dict[str, str]],
    currency: str | None,
    generated_at: datetime,
) -> dict[str, Any]:
    """Copy the approved section texts in department order."""
    return {
        "ticket_id": ticket_id,
        "sections": [
            {
                "department_id": section["department_id"],
                "draft_content": section["draft_content"],
            }
            for section in ordered_sections
        ],
        "currency": currency,
        "generated_at": generated_at,
    }
