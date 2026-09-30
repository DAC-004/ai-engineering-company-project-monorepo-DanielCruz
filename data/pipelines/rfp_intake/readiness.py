"""Decide whether a Part 1 ticket may enter response generation.

This module reads the stored handoff only. It does not open the PDF and it
does not build a second summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS


@dataclass(frozen=True)
class Readiness:
    """accepted is true only for intake_complete plus a matching handoff."""

    accepted: bool
    reason: str | None
    handoff: dict[str, Any] | None


def _section_ids(handoff: dict[str, Any]) -> set[str]:
    sections = handoff.get("sections")
    if not isinstance(sections, list):
        return set()
    found: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            continue
        department_id = section.get("department_id")
        key_aspects = section.get("key_aspects")
        if isinstance(department_id, str) and isinstance(key_aspects, dict):
            found.add(department_id)
    return found


def assess_readiness(status: str, ticket_id: str, handoff: object) -> Readiness:
    """Accept the same ticket Part 1 marked ready. Refuse every other state."""
    if status != "intake_complete":
        return Readiness(False, "not_intake_complete", None)
    if not isinstance(handoff, dict):
        return Readiness(False, "handoff_missing", None)
    if handoff.get("ticket_id") != ticket_id:
        return Readiness(False, "handoff_mismatch", None)
    metadata = handoff.get("metadata")
    if not isinstance(metadata, dict):
        return Readiness(False, "handoff_incomplete", None)
    if not set(DEPARTMENT_IDS).issubset(_section_ids(handoff)):
        return Readiness(False, "handoff_incomplete", None)
    return Readiness(True, None, handoff)
