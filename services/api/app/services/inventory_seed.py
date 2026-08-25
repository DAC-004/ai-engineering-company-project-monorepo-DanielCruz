"""Idempotent HealthCore inventory seed from CONTEXT — Milestone 5.

Seeds the six required MedicalSupply rows, at least four SupplyDelivery rows
(including two different HCR-PPE-001 quantities), and at least three
SupplyConsumption rows of both required types. Repeating startup is a no-op
once any MedicalSupply row exists.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
from app.schemas.user import UserCreate, UserRole
from app.services import user_service

SEED_USER_EMAIL = "inventory.seed@healthcore.com"
SEED_USER_PASSWORD = "HealthCoreSeed1!"

SEED_SUPPLIES: tuple[dict[str, str], ...] = (
    {
        "name": "Nitrile gloves (box of 100)",
        "sku": "HCR-PPE-001",
        "category": "ppe",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Surgical mask (pack of 50)",
        "sku": "HCR-PPE-002",
        "category": "ppe",
        "unit": "pack",
        "country": "UK",
    },
    {
        "name": "Adhesive wound dressing",
        "sku": "HCR-WND-001",
        "category": "wound_care",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Rapid strep test kit",
        "sku": "HCR-DIAG-001",
        "category": "diagnostics",
        "unit": "unit",
        "country": "US",
    },
    {
        "name": "Blood glucose test strips (50)",
        "sku": "HCR-DIAG-002",
        "category": "diagnostics",
        "unit": "box",
        "country": "UK",
    },
    {
        "name": "0.9% Saline solution 500ml",
        "sku": "HCR-MED-001",
        "category": "medications",
        "unit": "vial",
        "country": "US",
    },
)

# sku -> list of (quantity, vendor_name, clinic_id)
SEED_DELIVERIES: tuple[tuple[str, int, str, int], ...] = (
    ("HCR-PPE-001", 80, "MedLine Industries", 1),
    ("HCR-PPE-001", 40, "Bound Tree Medical", 4),
    ("HCR-PPE-002", 25, "Cardinal Health UK", 10),
    ("HCR-WND-001", 18, "MedLine Industries", 2),
)

# sku -> list of (quantity, consumption_type, clinic_id)
SEED_CONSUMPTIONS: tuple[tuple[str, int, str, int], ...] = (
    ("HCR-PPE-001", 12, "clinical_use", 1),
    ("HCR-PPE-001", 5, "expiry_waste", 4),
    ("HCR-PPE-002", 4, "clinical_use", 11),
)


def expected_seed_stock() -> dict[str, int]:
    """Map SKU to delivery totals minus consumption totals."""
    totals = {row["sku"]: 0 for row in SEED_SUPPLIES}
    for sku, quantity, _vendor, _clinic_id in SEED_DELIVERIES:
        totals[sku] += quantity
    for sku, quantity, _consumption_type, _clinic_id in SEED_CONSUMPTIONS:
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
            name=row["name"],
            sku=row["sku"],
            category=row["category"],
            unit=row["unit"],
            country=row["country"],
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

    for sku, quantity, consumption_type, clinic_id in SEED_CONSUMPTIONS:
        supply = supplies_by_sku[sku]
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply is missing an id.")
        session.add(
            SupplyConsumption(
                supply_id=supply.id,
                quantity=quantity,
                consumption_type=consumption_type,
                clinic_id=clinic_id,
                user_uuid=user_uuid,
            )
        )
    session.commit()
