"""HealthCore incident contract from incidents-healthcore CONTEXT.

Canonical definitions live in packages/shared/csv_constants.py. This module
re-exports them so existing CLI and analyzer API imports keep working.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGES_SHARED = Path(__file__).resolve().parents[2] / "packages" / "shared"
if str(_PACKAGES_SHARED) not in sys.path:
    sys.path.insert(0, str(_PACKAGES_SHARED))

from csv_constants import (  # noqa: E402
    CLINIC_COUNTRY,
    INCIDENT_ID_PATTERN,
    INVALID_RULE_LABELS,
    INVALID_RULE_ORDER,
    PATIENT_ID_PATTERN,
    SATISFACTION_LABELS,
    VALID_CATEGORIES,
    VALID_CLINIC_IDS,
    VALID_STATUSES,
)

__all__ = [
    "CLINIC_COUNTRY",
    "INCIDENT_ID_PATTERN",
    "INVALID_RULE_LABELS",
    "INVALID_RULE_ORDER",
    "PATIENT_ID_PATTERN",
    "SATISFACTION_LABELS",
    "VALID_CATEGORIES",
    "VALID_CLINIC_IDS",
    "VALID_STATUSES",
]
