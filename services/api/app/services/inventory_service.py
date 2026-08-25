"""Inventory business logic: computed MedicalSupply stock and order writes.

current_stock = SUM(SupplyDelivery.quantity) - SUM(SupplyConsumption.quantity)
for each MedicalSupply. clinic_id is recorded on movements but does not
partition catalog rows or the stock formula.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
from app.schemas.inventory import (
    InventoryOrderPublic,
    MedicalSupplyCreate,
    MedicalSupplyPublic,
    SupplyConsumptionCreate,
    SupplyConsumptionPublic,
    SupplyDeliveryCreate,
    SupplyDeliveryPublic,
)
from app.schemas.user import UserInDB

INSUFFICIENT_STOCK_TEMPLATE = (
    "Insufficient stock for supply '{name}'. Available: {available}, requested: {quantity}."
)


class InsufficientSupplyStockError(Exception):
    """Consumption quantity exceeds computed stock for the MedicalSupply."""

    def __init__(self, *, name: str, available: int, requested: int) -> None:
        self.name = name
        self.available = available
        self.requested = requested
        super().__init__(
            INSUFFICIENT_STOCK_TEMPLATE.format(name=name, available=available, quantity=requested)
        )


def _to_supply_public(supply: MedicalSupply, current_stock: int) -> MedicalSupplyPublic:
    if supply.id is None:
        raise RuntimeError("MedicalSupply is missing a persisted id.")
    return MedicalSupplyPublic(
        id=supply.id,
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=current_stock,
    )


def _stock_totals_by_supply_id(session: Session) -> dict[int, int]:
    """
    Compute current_stock for every supply in two grouped queries.

    One delivery SUM and one consumption SUM avoid the N+1 pattern of querying
    each supply's movements separately on GET /inventory/products.
    """
    delivery_rows = session.exec(
        select(
            SupplyDelivery.supply_id,
            func.coalesce(func.sum(SupplyDelivery.quantity), 0),
        ).group_by(SupplyDelivery.supply_id)
    ).all()
    consumption_rows = session.exec(
        select(
            SupplyConsumption.supply_id,
            func.coalesce(func.sum(SupplyConsumption.quantity), 0),
        ).group_by(SupplyConsumption.supply_id)
    ).all()

    delivery_totals = {supply_id: int(total) for supply_id, total in delivery_rows}
    consumption_totals = {supply_id: int(total) for supply_id, total in consumption_rows}
    supply_ids = set(delivery_totals) | set(consumption_totals)
    return {
        supply_id: delivery_totals.get(supply_id, 0) - consumption_totals.get(supply_id, 0)
        for supply_id in supply_ids
    }


def computed_stock_for_supply(session: Session, supply_id: int) -> int:
    """Stock for one MedicalSupply: delivery sum minus consumption sum."""
    delivery_total = session.exec(
        select(func.coalesce(func.sum(SupplyDelivery.quantity), 0)).where(
            SupplyDelivery.supply_id == supply_id
        )
    ).one()
    consumption_total = session.exec(
        select(func.coalesce(func.sum(SupplyConsumption.quantity), 0)).where(
            SupplyConsumption.supply_id == supply_id
        )
    ).one()
    return int(delivery_total) - int(consumption_total)


def get_supply_or_404(session: Session, supply_id: int) -> MedicalSupply:
    supply = session.get(MedicalSupply, supply_id)
    if supply is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical supply not found")
    return supply


def list_medical_supplies(session: Session) -> list[MedicalSupplyPublic]:
    supplies = session.exec(select(MedicalSupply).order_by(col(MedicalSupply.id))).all()
    stocks = _stock_totals_by_supply_id(session)
    return [_to_supply_public(supply, stocks.get(supply.id or 0, 0)) for supply in supplies]


def get_medical_supply(session: Session, supply_id: int) -> MedicalSupplyPublic:
    supply = get_supply_or_404(session, supply_id)
    return _to_supply_public(supply, computed_stock_for_supply(session, supply_id))


def create_medical_supply(session: Session, payload: MedicalSupplyCreate) -> MedicalSupplyPublic:
    supply = MedicalSupply(
        name=payload.name,
        sku=payload.sku,
        category=payload.category,
        unit=payload.unit,
        country=payload.country,
    )
    session.add(supply)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A medical supply with this SKU already exists.",
        ) from exc
    session.refresh(supply)
    return _to_supply_public(supply, 0)


def create_supply_delivery(
    session: Session,
    payload: SupplyDeliveryCreate,
    current_user: UserInDB,
) -> SupplyDeliveryPublic:
    get_supply_or_404(session, payload.supply_id)
    delivery = SupplyDelivery(
        supply_id=payload.supply_id,
        quantity=payload.quantity,
        vendor_name=payload.vendor_name,
        clinic_id=payload.clinic_id,
        user_uuid=current_user.id,
    )
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    if delivery.id is None:
        raise RuntimeError("SupplyDelivery is missing a persisted id.")
    return SupplyDeliveryPublic(
        id=delivery.id,
        supply_id=delivery.supply_id,
        quantity=delivery.quantity,
        vendor_name=delivery.vendor_name,
        clinic_id=delivery.clinic_id,
        created_at=delivery.created_at,
        user_uuid=delivery.user_uuid,
    )


def create_supply_consumption(
    session: Session,
    payload: SupplyConsumptionCreate,
    current_user: UserInDB,
) -> SupplyConsumptionPublic:
    """
    Reject a consumption write before persistence when it would make stock
    negative. Availability is computed from all deliveries minus consumptions
    for the MedicalSupply, matching the CONTEXT formula.
    """
    supply_query = select(MedicalSupply).where(MedicalSupply.id == payload.supply_id)
    if not str(session.get_bind().url).startswith("sqlite"):
        supply_query = supply_query.with_for_update()
    locked = session.exec(supply_query).first()
    if locked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical supply not found")

    available = computed_stock_for_supply(session, payload.supply_id)
    if payload.quantity > available:
        raise InsufficientSupplyStockError(
            name=locked.name,
            available=available,
            requested=payload.quantity,
        )

    consumption = SupplyConsumption(
        supply_id=payload.supply_id,
        quantity=payload.quantity,
        consumption_type=payload.consumption_type,
        clinic_id=payload.clinic_id,
        user_uuid=current_user.id,
    )
    session.add(consumption)
    session.commit()
    session.refresh(consumption)
    if consumption.id is None:
        raise RuntimeError("SupplyConsumption is missing a persisted id.")
    return SupplyConsumptionPublic(
        id=consumption.id,
        supply_id=consumption.supply_id,
        quantity=consumption.quantity,
        consumption_type=consumption.consumption_type,
        clinic_id=consumption.clinic_id,
        created_at=consumption.created_at,
        user_uuid=consumption.user_uuid,
    )


def list_inventory_orders(session: Session) -> list[InventoryOrderPublic]:
    """
    List deliveries and consumptions with MedicalSupply fields loaded via JOIN
    so listing does not issue one extra query per order (N+1).
    """
    delivery_rows = session.exec(
        select(SupplyDelivery, MedicalSupply)
        .join(MedicalSupply, SupplyDelivery.supply_id == MedicalSupply.id)
        .order_by(col(SupplyDelivery.created_at))
    ).all()
    consumption_rows = session.exec(
        select(SupplyConsumption, MedicalSupply)
        .join(MedicalSupply, SupplyConsumption.supply_id == MedicalSupply.id)
        .order_by(col(SupplyConsumption.created_at))
    ).all()

    orders: list[InventoryOrderPublic] = []
    for delivery, supply in delivery_rows:
        if delivery.id is None:
            continue
        orders.append(
            InventoryOrderPublic(
                id=delivery.id,
                order_type="delivery",
                supply_id=delivery.supply_id,
                supply_name=supply.name,
                supply_sku=supply.sku,
                supply_category=supply.category,
                supply_unit=supply.unit,
                supply_country=supply.country,
                quantity=delivery.quantity,
                clinic_id=delivery.clinic_id,
                created_at=delivery.created_at,
                user_uuid=delivery.user_uuid,
                vendor_name=delivery.vendor_name,
            )
        )
    for consumption, supply in consumption_rows:
        if consumption.id is None:
            continue
        orders.append(
            InventoryOrderPublic(
                id=consumption.id,
                order_type="consumption",
                supply_id=consumption.supply_id,
                supply_name=supply.name,
                supply_sku=supply.sku,
                supply_category=supply.category,
                supply_unit=supply.unit,
                supply_country=supply.country,
                quantity=consumption.quantity,
                clinic_id=consumption.clinic_id,
                created_at=consumption.created_at,
                user_uuid=consumption.user_uuid,
                consumption_type=consumption.consumption_type,
            )
        )
    orders.sort(key=lambda order: (order.created_at, order.order_type, order.id))
    return orders
