"""Idempotent HealthCore inventory seed from CONTEXT — Milestone 5.

Catalog rows do not need an actor. Demonstration deliveries and consumptions
need a nonempty user_uuid. Unattended startup and scripts/seed_inventory.py
have no authenticated requester; they do not invent one.

The only approved unattended actor is the unique dedicated demo account
orders.quoteflow@gmail.com, used when it is already active Admin / Technology
and centralized policy would allow Clinical Operations order writes. A database
lookup is not an authenticated request. The generator never creates accounts,
never upgrades assignments, and never uses inventory.seed@healthcore.com.

Catalog presence is not completion of owner-dependent seed work. Missing
demonstration orders are inserted only when the approved actor is usable.
Existing matching seed tuples keep their historical user_uuid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import inspect, text
from sqlmodel import Session, select
from tinydb import Query

from app.access.catalog import Capability, has_capability, is_admin, normalize_role
from app.access.permissions import can_access_department
from app.db.tinydb import users_table
from app.inventory_constants import DEFAULT_MINIMUM_STOCK
from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
from app.schemas.user import UserInDB, UserRole
from app.services.inventory_service import (
    InsufficientSupplyStockError,
    assert_consumption_within_stock,
)

PENDING_ACTOR = "approved demo actor unavailable; required demonstration orders remain"
PENDING_STOCK = "demonstration consumption would make stock negative"
PENDING_ORDERS = "required demonstration deliveries or consumptions remain"


@dataclass(frozen=True)
class InventorySeedResult:
    """Outcome of one unattended seed pass. Complete means the exact 6/4/3 contract."""

    complete: bool
    pending_reason: str | None = None
    missing_products: tuple[str, ...] = ()
    missing_delivery_count: int = 0
    missing_consumption_count: int = 0

    @property
    def message(self) -> str:
        if self.complete:
            return "Inventory seed complete"
        reason = self.pending_reason or PENDING_ORDERS
        return f"Inventory seed pending: {reason}"


def apply_seed_command_result(result: InventorySeedResult) -> int:
    """Print the existing command status and return the process exit code."""
    print(result.message)
    return 0 if result.complete else 1


RETIRED_SEED_LOGIN_EMAIL = "inventory.seed@healthcore.com"
DEMO_ACTOR_EMAIL = "orders.quoteflow@gmail.com"
DEMO_ACTOR_DEPARTMENT_ID = "technology"
CATALOG_DEPARTMENT_ID = "clinical_operations"

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


def _canonical_email(email: object) -> str:
    return str(email or "").strip().lower()


def _matching_demo_identity_rows() -> list[dict]:
    """Exact approved demo address, including stored case variants. Does not list other accounts."""
    canonical = DEMO_ACTOR_EMAIL
    return list(
        users_table().search(
            Query().email.test(
                lambda value: _canonical_email(value) == canonical
            )
        )
    )


def _row_is_usable_demo_actor(row: dict) -> bool:
    """Require the stored Admin/Technology assignment. Do not normalize it onto disk."""
    if not row.get("id"):
        return False
    if row.get("is_active") is not True:
        return False
    try:
        role = normalize_role(row.get("role") or row.get("role_id"))
    except ValueError:
        return False
    stored_role_id = row.get("role_id")
    if stored_role_id is not None and str(stored_role_id).lower() != UserRole.admin.value:
        return False
    if role != UserRole.admin or row.get("department_id") != DEMO_ACTOR_DEPARTMENT_ID:
        return False
    try:
        user = UserInDB.model_validate(
            {
                **row,
                "role": role.value,
                "role_id": role.value,
                "department_id": row.get("department_id"),
            }
        )
    except Exception:
        return False
    if not is_admin(user.role):
        return False
    if not has_capability(user.role, Capability.create_department_record):
        return False
    return can_access_department(user, CATALOG_DEPARTMENT_ID)


def usable_demo_actor_id() -> str | None:
    """Return the approved demo account id, or None. Never creates or upgrades accounts."""
    matches = _matching_demo_identity_rows()
    if len(matches) != 1:
        return None
    row = matches[0]
    if not _row_is_usable_demo_actor(row):
        return None
    return str(row["id"])


def _catalog_is_empty(session: Session) -> bool:
    return session.exec(select(MedicalSupply.id)).first() is None


def _insert_catalog(session: Session) -> dict[str, MedicalSupply]:
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
            department_id=CATALOG_DEPARTMENT_ID,
        )
        session.add(supply)
        session.flush()
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply did not receive an id.")
        supplies_by_sku[str(row["sku"])] = supply
    return supplies_by_sku


def _supplies_by_sku(session: Session) -> dict[str, MedicalSupply]:
    return {supply.sku: supply for supply in session.exec(select(MedicalSupply)).all()}


def _seed_delivery_present(
    session: Session,
    sku: str,
    quantity: int,
    vendor_name: str,
    clinic_id: int,
) -> bool:
    row = session.exec(
        select(SupplyDelivery)
        .join(MedicalSupply, SupplyDelivery.supply_id == MedicalSupply.id)
        .where(MedicalSupply.sku == sku)
        .where(SupplyDelivery.quantity == quantity)
        .where(SupplyDelivery.vendor_name == vendor_name)
        .where(SupplyDelivery.clinic_id == clinic_id)
    ).first()
    return row is not None


def _seed_consumption_present(
    session: Session,
    sku: str,
    quantity: int,
    consumption_type: str,
    clinic_id: int,
    department: str,
) -> bool:
    row = session.exec(
        select(SupplyConsumption)
        .join(MedicalSupply, SupplyConsumption.supply_id == MedicalSupply.id)
        .where(MedicalSupply.sku == sku)
        .where(SupplyConsumption.quantity == quantity)
        .where(SupplyConsumption.consumption_type == consumption_type)
        .where(SupplyConsumption.clinic_id == clinic_id)
        .where(SupplyConsumption.department == department)
    ).first()
    return row is not None


def _missing_prescribed_skus(session: Session) -> tuple[str, ...]:
    present = set(_supplies_by_sku(session))
    return tuple(str(row["sku"]) for row in SEED_SUPPLIES if str(row["sku"]) not in present)


def _missing_demonstration_orders(
    session: Session,
) -> tuple[list[tuple[str, int, str, int]], list[tuple[str, int, str, int, str]]]:
    """Count every required tuple, including those whose SKU is not in the catalog.

    An absent SKU is a missing product, not a satisfied delivery or consumption.
    Presence still requires the exact SKU+quantity+vendor/type+clinic(+department)
    match. Matching historical rows are treated as present regardless of owner.
    """
    missing_deliveries = [
        item for item in SEED_DELIVERIES if not _seed_delivery_present(session, *item)
    ]
    missing_consumptions = [
        item for item in SEED_CONSUMPTIONS if not _seed_consumption_present(session, *item)
    ]
    return missing_deliveries, missing_consumptions


def _complete_seed_result() -> InventorySeedResult:
    return InventorySeedResult(complete=True)


def _incomplete_seed_result(
    session: Session,
    *,
    actor_unavailable: bool = False,
    stock_blocked: bool = False,
) -> InventorySeedResult:
    missing_products = _missing_prescribed_skus(session)
    missing_deliveries, missing_consumptions = _missing_demonstration_orders(session)
    if not missing_products and not missing_deliveries and not missing_consumptions:
        return _complete_seed_result()
    if stock_blocked:
        reason = PENDING_STOCK
    else:
        parts: list[str] = []
        if missing_products:
            parts.append("required products absent: " + ", ".join(missing_products))
        if missing_deliveries or missing_consumptions:
            parts.append(PENDING_ACTOR if actor_unavailable else PENDING_ORDERS)
        reason = "; ".join(parts) or PENDING_ORDERS
    return InventorySeedResult(
        complete=False,
        pending_reason=reason,
        missing_products=missing_products,
        missing_delivery_count=len(missing_deliveries),
        missing_consumption_count=len(missing_consumptions),
    )


def _insert_missing_demonstration_orders(
    session: Session,
    actor_id: str,
    supplies_by_sku: dict[str, MedicalSupply],
    missing_deliveries: list[tuple[str, int, str, int]],
    missing_consumptions: list[tuple[str, int, str, int, str]],
) -> None:
    """Insert missing seed tuples that already have a catalog row.

    Stock validation reuses assert_consumption_within_stock. This path does not
    call create_supply_consumption because that function commits per row and
    requires an authenticated current_user. Actor and department authorization
    remain the unattended usable_demo_actor_id checks.
    """
    for sku, quantity, vendor_name, clinic_id in missing_deliveries:
        supply = supplies_by_sku[sku]
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply is missing an id.")
        session.add(
            SupplyDelivery(
                supply_id=supply.id,
                quantity=quantity,
                vendor_name=vendor_name,
                clinic_id=clinic_id,
                user_uuid=actor_id,
            )
        )
    session.flush()

    for sku, quantity, consumption_type, clinic_id, department in missing_consumptions:
        supply = supplies_by_sku[sku]
        if supply.id is None:
            raise RuntimeError("Seeded MedicalSupply is missing an id.")
        assert_consumption_within_stock(session, supply, quantity)
        session.add(
            SupplyConsumption(
                supply_id=supply.id,
                quantity=quantity,
                consumption_type=consumption_type,
                department=department,
                clinic_id=clinic_id,
                user_uuid=actor_id,
            )
        )


def ensure_inventory_department_id(session: Session) -> None:
    """Ensure medical_supply.department_id exists and fill only missing values.

    Explicit nonempty departments are left unchanged, including unknown codes.
    Missing means SQL NULL only.
    """
    bind = session.get_bind()
    inspector = inspect(bind)
    if "medical_supply" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("medical_supply")}
    if "department_id" not in columns:
        session.execute(
            text(
                "ALTER TABLE medical_supply ADD COLUMN department_id VARCHAR(64) "
                "DEFAULT 'clinical_operations'"
            )
        )
        session.commit()
    session.execute(
        text(
            "UPDATE medical_supply SET department_id = 'clinical_operations' "
            "WHERE department_id IS NULL"
        )
    )
    session.commit()


def seed_inventory_if_empty(session: Session) -> InventorySeedResult:
    """Insert missing CONTEXT catalog and demonstration orders.

    Catalog is inserted only when medical_supply is empty. A nonempty catalog
    never receives invented products, even when prescribed SKUs are absent.
    Demonstration deliveries/consumptions are matched by SKU, quantity,
    vendor/type, clinic, and consumption department. An absent SKU keeps the
    corresponding required tuples missing; it does not satisfy the 4/3
    contract. Matching historical rows are left untouched, including
    user_uuid. Missing order rows whose SKU already exists are inserted only
    when the unique approved demo Admin is already usable. Already-complete
    historical 6/4/3 data is reported complete without requiring that actor.
    """
    if _catalog_is_empty(session):
        _insert_catalog(session)
        session.commit()

    missing_products = _missing_prescribed_skus(session)
    missing_deliveries, missing_consumptions = _missing_demonstration_orders(session)
    if not missing_products and not missing_deliveries and not missing_consumptions:
        return _complete_seed_result()

    supplies_by_sku = _supplies_by_sku(session)
    insertable_deliveries = [
        item for item in missing_deliveries if item[0] in supplies_by_sku
    ]
    insertable_consumptions = [
        item for item in missing_consumptions if item[0] in supplies_by_sku
    ]
    if not insertable_deliveries and not insertable_consumptions:
        return _incomplete_seed_result(session)

    actor_id = usable_demo_actor_id()
    if actor_id is None:
        return _incomplete_seed_result(session, actor_unavailable=True)

    try:
        _insert_missing_demonstration_orders(
            session,
            actor_id,
            supplies_by_sku,
            insertable_deliveries,
            insertable_consumptions,
        )
        session.commit()
    except InsufficientSupplyStockError:
        session.rollback()
        return _incomplete_seed_result(session, stock_blocked=True)

    remaining = _incomplete_seed_result(session)
    return remaining if not remaining.complete else _complete_seed_result()
