"""HealthCore Centralized Incident Manager allowed values and CSV maps.

These are the CONTEXT model values (not the analyzer CSV codes). The API and
seed script import this module so allowed values are not duplicated.
"""

from __future__ import annotations

CATEGORIES: tuple[str, ...] = (
    "clinical_equipment",
    "it_system",
    "billing_error",
    "compliance_breach",
    "patient_experience",
    "staff_issue",
    "facility_issue",
    "referral_issue",
    "other",
)

STATUSES: tuple[str, ...] = (
    "open",
    "in_progress",
    "resolved",
    "discarded",
)

ORIGINS: tuple[str, ...] = (
    "customer",
    "branch",
    "internal",
)

# Exact CONTEXT model values. Do not reduce this set to the "12 clinics" prose.
BRANCHES: tuple[str, ...] = (
    "central",
    "austin_north",
    "dallas_uptown",
    "houston_med_center",
    "san_antonio_west",
    "miami_brickell",
    "miami_doral",
    "orlando_east",
    "tampa_bay",
    "atlanta_midtown",
    "savannah",
    "london_city",
    "london_west",
    "manchester_central",
)

# Display labels must match CONTEXT exactly, including the em dash on central.
BRANCH_LABELS: dict[str, str] = {
    "central": "Central — Austin Main Clinic",
    "austin_north": "Austin — North",
    "dallas_uptown": "Dallas Uptown",
    "houston_med_center": "Houston Medical Center",
    "san_antonio_west": "San Antonio West",
    "miami_brickell": "Miami Brickell",
    "miami_doral": "Miami Doral",
    "orlando_east": "Orlando East",
    "tampa_bay": "Tampa Bay",
    "atlanta_midtown": "Atlanta Midtown",
    "savannah": "Savannah",
    "london_city": "London City",
    "london_west": "London West End",
    "manchester_central": "Manchester Central",
}

# resolved and discarded are final: no outbound transitions.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress", "discarded"}),
    "in_progress": frozenset({"resolved", "discarded"}),
    "resolved": frozenset(),
    "discarded": frozenset(),
}

CSV_STATUS_MAP: dict[str, str] = {
    "OPEN": "open",
    "CLOSED": "resolved",
    "DISCARDED": "discarded",
}

CSV_CATEGORY_MAP: dict[str, str] = {
    "APPOINTMENT": "patient_experience",
    "BILLING": "billing_error",
    "CLINICAL_CARE": "patient_experience",
    "ACCESSIBILITY": "patient_experience",
    "ADMINISTRATIVE": "other",
}

# Intentional rollups: US-GA-02 -> atlanta_midtown, UK-LON-02 -> london_west.
CSV_CLINIC_TO_BRANCH: dict[str, str] = {
    "US-TX-01": "central",
    "US-TX-02": "austin_north",
    "US-TX-03": "houston_med_center",
    "US-FL-01": "miami_brickell",
    "US-FL-02": "orlando_east",
    "US-FL-03": "tampa_bay",
    "US-GA-01": "atlanta_midtown",
    "US-GA-02": "atlanta_midtown",
    "US-GA-03": "savannah",
    "UK-LON-01": "london_city",
    "UK-LON-02": "london_west",
    "UK-MAN-01": "manchester_central",
}

DEFAULT_BRANCH = "central"
DEFAULT_CREATE_STATUS = "open"
SEED_ORIGIN = "customer"
