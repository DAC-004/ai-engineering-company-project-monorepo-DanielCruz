"""Idempotent HealthCore inventory seed from CONTEXT — Milestone 5.

Seeds the six required MedicalSupply rows, at least four SupplyDelivery rows
(including two different HCR-PPE-001 quantities), and at least three
SupplyConsumption rows of both required types. Repeating startup is a no-op
once any MedicalSupply row exists.
"""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.inventory_constants import DEFAULT_MINIMUM_STOCK
from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
from app.schemas.user import UserCreate, UserRole
from app.services import user_service

SEED_USER_EMAIL = "inventory.seed@healthcore.com"
SEED_USER_PASSWORD = "HealthCoreSeed1!"

SEED_SUPPLIES: tuple[dict[str, object], ...] = (
    {
        "name": "Nitrile gloves (box of 100)",
        "sku": "HCR-PPE-001",
        "category": "ppe",
        "unit": "box",
        "country": "US",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": None,
    },
    {
        "name": "Surgical mask (pack of 50)",
        "sku": "HCR-PPE-002",
        "category": "ppe",
        "unit": "pack",
        "country": "UK",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": None,
    },
    {
        "name": "Adhesive wound dressing",
        "sku": "HCR-WND-001",
        "category": "wound_care",
        "unit": "box",
        "country": "US",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": None,
    },
    {
        "name": "Rapid strep test kit",
        "sku": "HCR-DIAG-001",
        "category": "diagnostics",
        "unit": "unit",
        "country": "US",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": None,
    },
    {
        "name": "Blood glucose test strips (50)",
        "sku": "HCR-DIAG-002",
        "category": "diagnostics",
        "unit": "box",
        "country": "UK",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": None,
    },
    {
        "name": "0.9% Saline solution 500ml",
        "sku": "HCR-MED-001",
        "category": "medications",
        "unit": "vial",
        "country": "US",
        "minimum_stock": DEFAULT_MINIMUM_STOCK,
        "expiry_date": date(2026, 9, 12),
    },
)

# sku -> list of (quantity, vendor_name, clinic_id)
SEED_DELIVERIES: tuple[tuple[str, int, str, int], ...] = (
    ("HCR-PPE-001", 80, "MedLine Industries", 1),
    ("HCR-PPE-001", 40, "Bound Tree Medical", 4),
    ("HCR-PPE-002", 25, "Cardinal Health UK", 10),
    ("HCR-WND-001", 18, "MedLine Industries", 2),
)

# sku -> list of (quantity, consumption_type, clinic_id, department)
SEED_CONSUMPTIONS: tuple[tuple[str, int, str, int, str], ...] = (
    ("HCR-PPE-001", 12, "clinical_use", 1, "primary_care"),
    ("HCR-PPE-001", 5, "expiry_waste", 4, "chronic_care"),
    ("HCR-PPE-002", 4, "clinical_use", 11, "general_consultation"),
)


def expected_seed_stock() -> dict[str, int]:
    """Map SKU to delivery totals minus consumption totals."""
    totals = {str(row["sku"]): 0 for row in SEED_SUPPLIES}
    for sku, quantity, _vendor, _clinic_id in SEED_DELIVERIES:
        totals[sku] += quantity
    for sku, quantity, _consumption_type, _clinic_id, _department in SEED_CONSUMPTIONS:
        totals[sku] -= quantity
    return totals


def _seed_user_uuid() -> str:
    existing = user_service.get_user_by_email(SEED_USER_EMAIL)
    if existing is not None:
        return existing.id
    created = user_service.create_user(
        UserCreate(email=SEED_USER_EMAIL, password=SEED_USER_PASSWORD, name="Inventory Seed"),
        role=UserRole.user,
    )
    return created.id


def seed_inventory_if_empty(session: Session) -> None:
    """Insert the required CONTEXT seed once, when medical_supply is empty."""
    existing = session.exec(select(MedicalSupply.id)).first()
    if existing is not None:
        return

    user_uuid = _seed_user_uuid()
    supplies_by_sku: dict[str, MedicalSupply] = {}
    for row in SEED_SUPPLIES:
        supply = MedicalSupply(
            name=str(row["name"]),
            sku=str(row["sku"]),
            category=str(row["category"]),
            unit=str(row["unit"]),
            country=str(row["country"]),
            minimum_stock=int(row["minimum_stock"]),
            expiry_date=row["expiry_date"] if isinstance(row["expiry_date"], date) else None,
        )
        session.add(supply)
        session.flush()
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply did not receive an id.")
        supplies_by_sku[row["sku"]] = supply

    for sku, quantity, vendor_name, clinic_id in SEED_DELIVERIES:
        supply = supplies_by_sku[sku]
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply is missing an id.")
        session.add(
            SupplyDelivery(
                supply_id=supply.id,
                quantity=quantity,
                vendor_name=vendor_name,
                clinic_id=clinic_id,
                user_uuid=user_uuid,
            )
        )

    for sku, quantity, consumption_type, clinic_id, department in SEED_CONSUMPTIONS:
        supply = supplies_by_sku[sku]
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply is missing an id.")
        session.add(
            SupplyConsumption(
                supply_id=supply.id,
                quantity=quantity,
                consumption_type=consumption_type,
                department=department,
                clinic_id=clinic_id,
                user_uuid=user_uuid,
            )
        )
    session.commit()
