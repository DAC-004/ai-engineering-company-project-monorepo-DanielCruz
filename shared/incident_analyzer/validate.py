"""Record validation for HealthCore incident CSV rows.

Canonical implementation lives in packages/shared/csv_validate.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGES_SHARED = Path(__file__).resolve().parents[2] / "packages" / "shared"
if str(_PACKAGES_SHARED) not in sys.path:
    sys.path.insert(0, str(_PACKAGES_SHARED))

from csv_validate import _cell, classify_invalid_rules  # noqa: E402

__all__ = ["_cell", "classify_invalid_rules"]
