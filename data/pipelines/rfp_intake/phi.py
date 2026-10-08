"""Detect and redact patient identifiers before text is stored or shown.

A program mention of a condition, with no patient label, is not treated as PHI.
Labeled patient fields are. Values found on input are also removed from later
model text so a completion cannot repeat them.
"""

from __future__ import annotations

import contextvars
import re
from dataclasses import dataclass

# Label plus a value. The label list is the Part 1 patient-field set.
# The separator is a colon, or a hyphen that is followed by a space, so a
# phrase such as "patient-centered" is not treated as a labeled field.
# A sentence such as "chronic condition management (diabetes, hypertension)"
# has no label, so it stays. That keeps the Meridian workforce scope intact.
_LABEL = (
    r"patient(?:'s)? name|patient|diagnosis|date of birth|dob|"
    r"medical record(?: number)?|mrn|ssn|social security(?: number)?|nhs number"
)
_LABELED_FIELD = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_LABEL})\s*(?::|-\s)\s*(?P<value>[^.;\n]+)"
)

_REDACTION = "[redacted]"
_blocked_values: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "rfp_phi_blocked_values",
    default=(),
)


@dataclass(frozen=True)
class PhiScreen:
    """Screen result. blocked_values is in-memory only and must not be logged."""

    text: str
    detected: bool
    blocked_values: tuple[str, ...]


def bind_blocked_values(values: tuple[str, ...]) -> contextvars.Token[tuple[str, ...]]:
    """Hold input values for output redaction without placing them in graph state."""
    cleaned = tuple(value.strip() for value in values if value and value.strip())
    return _blocked_values.set(cleaned)


def reset_blocked_values(token: contextvars.Token[tuple[str, ...]]) -> None:
    _blocked_values.reset(token)


def screen_text(text: str, *, extra_values: tuple[str, ...] = ()) -> PhiScreen:
    """Redact labeled patient fields and any previously blocked values."""
    detected = False
    found: list[str] = []

    def replace_label(match: re.Match[str]) -> str:
        nonlocal detected
        value = match.group("value").strip()
        if value and value != _REDACTION:
            detected = True
            found.append(value)
        return f"{match.group('label')}: {_REDACTION}"

    redacted = _LABELED_FIELD.sub(replace_label, text)
    for value in (*extra_values, *_blocked_values.get()):
        if value and value in redacted:
            detected = True
            redacted = redacted.replace(value, _REDACTION)
            found.append(value)
    # Stable unique values, longest first, so a shorter piece cannot survive inside a longer one.
    unique = tuple(sorted(set(found), key=len, reverse=True))
    return PhiScreen(text=redacted, detected=detected, blocked_values=unique)


def screen_structure(value: object, *, extra_values: tuple[str, ...] = ()) -> tuple[object, bool, tuple[str, ...]]:
    """Screen every string in a model payload before it is saved or returned."""
    detected = False
    blocked: list[str] = []

    def walk(item: object) -> object:
        nonlocal detected
        if isinstance(item, str):
            screened = screen_text(item, extra_values=extra_values)
            if screened.detected:
                detected = True
                blocked.extend(screened.blocked_values)
            return screened.text
        if isinstance(item, list):
            return [walk(entry) for entry in item]
        if isinstance(item, dict):
            return {key: walk(entry) for key, entry in item.items()}
        return item

    screened_value = walk(value)
    return screened_value, detected, tuple(sorted(set(blocked), key=len, reverse=True))


def screen_generated_structure(value: object) -> tuple[object, bool]:
    """Screen every stored string with the generated-text rules.

    ``screen_structure`` redacts labeled fields. Generated prose such as a
    named patient sentence is covered by ``screen_generated``. Callers that
    persist model text use this walk so the stored copy is the screened copy.
    """
    detected = False

    def walk(item: object) -> object:
        nonlocal detected
        if isinstance(item, str):
            screened = screen_generated(item)
            detected = detected or screened.detected
            return screened.text
        if isinstance(item, list):
            return [walk(entry) for entry in item]
        if isinstance(item, dict):
            return {key: walk(entry) for key, entry in item.items()}
        return item

    return walk(value), detected


# Prose patterns the labeled-field screen does not cover. A workforce mention of a
# condition, with no patient attached, is still not PHI.
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_MRN = re.compile(r"(?i)\bmrn\b\s*[:#-]?\s*\d{3,}")
_NHS = re.compile(r"(?i)\bnhs\s+number\b\s*[:#-]?\s*\d{3,}")
_PATIENT_NAME = re.compile(
    r"(?i:\bpatient(?:'s)?\s+(?:name\s+is\s+|named\s+)?)(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)
_DIAGNOSIS_PROSE = re.compile(r"(?i)\b(?:diagnosed\s+with|diagnosis\s+of)\s+(?P<condition>[^.;\n]+)")
_DEFAULT_ALLOWED_NAMES = ("Tom Callahan", "Dr. Marcus Reid", "Marcus Reid", "Claire Whitfield")


def screen_generated(text: str, *, allowed_names: tuple[str, ...] = ()) -> PhiScreen:
    """Redact labeled fields and patient-attached prose before a draft is stored.

    Detection is about the original text. Callers must keep that flag after the
    redacted string no longer matches.
    """
    labeled = screen_text(text)
    detected = labeled.detected
    redacted = labeled.text
    found = list(labeled.blocked_values)
    allowed = {name.casefold() for name in (*_DEFAULT_ALLOWED_NAMES, *allowed_names) if name}

    def replace_pattern(pattern: re.Pattern[str], group: str | None) -> None:
        nonlocal detected, redacted

        def replace_match(match: re.Match[str]) -> str:
            nonlocal detected
            value = match.group(group) if group else match.group(0)
            cleaned = value.strip()
            if cleaned.casefold() in allowed:
                return match.group(0)
            detected = True
            found.append(cleaned)
            if group:
                return match.group(0).replace(value, _REDACTION, 1)
            return _REDACTION

        redacted = pattern.sub(replace_match, redacted)

    replace_pattern(_SSN, None)
    replace_pattern(_MRN, None)
    replace_pattern(_NHS, None)
    replace_pattern(_PATIENT_NAME, "name")
    replace_pattern(_DIAGNOSIS_PROSE, "condition")
    unique = tuple(sorted(set(found), key=len, reverse=True))
    return PhiScreen(text=redacted, detected=detected, blocked_values=unique)
