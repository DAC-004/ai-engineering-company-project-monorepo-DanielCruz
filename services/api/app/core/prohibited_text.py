"""Shared check for labeled patient fields in persisted free text.

The detector is the RFP screen. A program mention of a condition, with no
patient label, is not a match. Callers reject the write and keep the submitted
text out of the stored row and the error body.
"""

from __future__ import annotations

from data.pipelines.rfp_intake.phi import screen_text


def has_labeled_patient_field(text: str | None) -> bool:
    """Return whether ``text`` contains a labeled patient field."""
    if text is None or not text.strip():
        return False
    return screen_text(text).detected
