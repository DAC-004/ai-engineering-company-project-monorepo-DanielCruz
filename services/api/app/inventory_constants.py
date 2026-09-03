"""HealthCore inventory domain values from CONTEXT — Milestone 5."""

from __future__ import annotations

CATEGORIES = ("ppe", "wound_care", "diagnostics", "medications", "consumables")
UNITS = ("box", "unit", "pack", "vial")
COUNTRIES = ("US", "UK")
CONSUMPTION_TYPES = ("clinical_use", "expiry_waste")
DEPARTMENTS = (
    "primary_care",
    "specialty_care",
    "chronic_disease_management",
    "preventive_health",
    "general_consultation",
    "chronic_care",
)
CLINIC_ID_MIN = 1
CLINIC_ID_MAX = 12
DEFAULT_MINIMUM_STOCK = 10
