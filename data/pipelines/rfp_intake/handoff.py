"""Part 2 handoff built from screened intake output. Part 2 does not re-read the PDF."""

from __future__ import annotations

from typing import Any


def build_handoff(
    *,
    ticket_id: str,
    metadata: dict[str, Any],
    readability: dict[str, Any],
    sections: list[dict[str, Any]],
    summary: str,
    phi_detected: bool,
    compliance_review_required: bool,
) -> dict[str, Any]:
    """Carry the ticket id, key aspects, and synthesizer summary for the same ticket."""
    return {
        "ticket_id": ticket_id,
        "phi_detected": phi_detected,
        "compliance_review_required": compliance_review_required,
        "metadata": metadata,
        "readability": readability,
        "sections": [
            {
                "department_id": section["department_id"],
                "department_name": section["department_name"],
                "contact_name": section["contact_name"],
                "key_aspects": {
                    "aspects": section["aspects"],
                    "open_questions": section["open_questions"],
                },
            }
            for section in sections
        ],
        "synthesizer_summary": summary,
    }
