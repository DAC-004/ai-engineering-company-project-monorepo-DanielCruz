"""Standalone Pydantic request/response schemas for HealthCore inventory.

Kept separate from SQLModel table classes in app/models.py. Field names match
CONTEXT — Milestone 5. Endpoints must return these models, never raw ORM rows.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.inventory_constants import (
    CATEGORIES,
    CLINIC_ID_MAX,
    CLINIC_ID_MIN,
    CONSUMPTION_TYPES,
    COUNTRIES,
    DEFAULT_MINIMUM_STOCK,
    DEPARTMENTS,
    UNITS,
)

Category = Literal["ppe", "wound_care", "diagnostics", "medications", "consumables"]
Unit = Literal["box", "unit", "pack", "vial"]
Country = Literal["US", "UK"]
ConsumptionType = Literal["clinical_use", "expiry_waste"]
Department = Literal[
    "primary_care",
    "specialty_care",
    "chronic_disease_management",
    "preventive_health",
    "general_consultation",
    "chronic_care",
]


class MedicalSupplyCreate(BaseModel):
    """Catalog create payload. Stock fields are forbidden (order-only writes)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=64)
    category: Category
    unit: Unit
    country: Country
    minimum_stock: int = Field(default=DEFAULT_MINIMUM_STOCK, ge=0)
    expiry_date: date | None = None


class MedicalSupplyPublic(BaseModel):
    """Medical-supply response. current_stock is computed, never stored."""

    model_config = ConfigDict(from_attributes=False)

    id: int
    name: str
    sku: str
    category: str
    unit: str
    country: str
    current_stock: int
    minimum_stock: int
    expiry_date: date | None = None
    clinic_current_stock: int | None = None


class SupplyDeliveryCreate(BaseModel):
    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0, description="Units received; must be greater than zero.")
    vendor_name: str = Field(min_length=1, max_length=200)
    clinic_id: int = Field(ge=CLINIC_ID_MIN, le=CLINIC_ID_MAX)


class SupplyDeliveryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: int
    supply_id: int
    quantity: int
    vendor_name: str
    clinic_id: int
    created_at: datetime
    user_uuid: str


class SupplyConsumptionCreate(BaseModel):
    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0, description="Units consumed; must be greater than zero.")
    consumption_type: ConsumptionType
    department: Department
    clinic_id: int = Field(ge=CLINIC_ID_MIN, le=CLINIC_ID_MAX)


class SupplyConsumptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: int
    supply_id: int
    quantity: int
    consumption_type: str
    department: str
    clinic_id: int
    created_at: datetime
    user_uuid: str


class InventoryOrderPublic(BaseModel):
    """Unified delivery/consumption row with related MedicalSupply fields."""

    model_config = ConfigDict(from_attributes=False)

    id: int
    order_type: Literal["delivery", "consumption"]
    supply_id: int
    supply_name: str
    supply_sku: str
    supply_category: str
    supply_unit: str
    supply_country: str
    quantity: int
    clinic_id: int
    created_at: datetime
    user_uuid: str
    vendor_name: str | None = None
    consumption_type: str | None = None
    department: str | None = None


assert CATEGORIES == ("ppe", "wound_care", "diagnostics", "medications", "consumables")
assert UNITS == ("box", "unit", "pack", "vial")
assert COUNTRIES == ("US", "UK")
assert CONSUMPTION_TYPES == ("clinical_use", "expiry_waste")
assert DEPARTMENTS == (
    "primary_care",
    "specialty_care",
    "chronic_disease_management",
    "preventive_health",
    "general_consultation",
    "chronic_care",
)
assert CLINIC_ID_MIN == 1 and CLINIC_ID_MAX == 12
