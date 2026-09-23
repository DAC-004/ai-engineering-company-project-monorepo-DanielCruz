"""SQLModel table models for HealthCore medical-supply inventory (Supabase).

Entity names and columns match CONTEXT — Milestone 5. Request/response
shapes live in app/schemas/inventory.py and must not be returned as ORM
objects. There is no SQLModel User table; user_uuid stores a TinyDB id.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class MedicalSupply(SQLModel, table=True):
    """Product-equivalent catalog row. current_stock is never stored."""

    __tablename__ = "medical_supply"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=64, unique=True, index=True)
    category: str = Field(min_length=1, max_length=32, index=True)
    unit: str = Field(min_length=1, max_length=16)
    country: str = Field(min_length=2, max_length=2, index=True)
    # Configured reorder floor used by stock_threshold_triggered. Not stored stock.
    minimum_stock: int = Field(default=10, ge=0)
    # Supply expiry on the catalog row so supply_expiry_flagged is computable.
    expiry_date: date | None = Field(default=None)


class SupplyDelivery(SQLModel, table=True):
    """Inbound-equivalent vendor shipment received at a clinic."""

    __tablename__ = "supply_delivery"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="supply_delivery_quantity_positive"),
        CheckConstraint("clinic_id >= 1 AND clinic_id <= 12", name="supply_delivery_clinic_id_range"),
    )

    id: int | None = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="medical_supply.id", index=True)
    quantity: int
    vendor_name: str = Field(min_length=1, max_length=200)
    clinic_id: int = Field(ge=1, le=12, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    user_uuid: str = Field(min_length=1, max_length=64, index=True)


class SupplyConsumption(SQLModel, table=True):
    """Outbound-equivalent clinical use or expiry waste. Cannot go negative."""

    __tablename__ = "supply_consumption"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="supply_consumption_quantity_positive"),
        CheckConstraint("clinic_id >= 1 AND clinic_id <= 12", name="supply_consumption_clinic_id_range"),
    )

    id: int | None = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="medical_supply.id", index=True)
    quantity: int
    consumption_type: str = Field(min_length=1, max_length=32, index=True)
    department: str = Field(min_length=1, max_length=64, index=True)
    clinic_id: int = Field(ge=1, le=12, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    user_uuid: str = Field(min_length=1, max_length=64, index=True)


class TaskFailure(SQLModel, table=True):
    """Terminal Celery failure after three consecutive attempts (DEV-55 DLQ record)."""

    __tablename__ = "task_failure"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(min_length=1, max_length=64, unique=True, index=True)
    attempt: int = Field(ge=1)
    error_message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
