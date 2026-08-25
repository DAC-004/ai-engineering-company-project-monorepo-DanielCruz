"""HealthCore inventory routes under /inventory.

All inventory access is authenticated (CONTEXT — Milestone 5). Writes store
the TinyDB user id in user_uuid. Stock is never accepted as input.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.deps import get_current_user
from app.db.database import get_db
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
from app.services import inventory_service
from app.services.inventory_service import InsufficientSupplyStockError

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/products", response_model=list[MedicalSupplyPublic])
def list_products(
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> list[MedicalSupplyPublic]:
    """List medical supplies with computed current_stock."""
    return inventory_service.list_medical_supplies(session)


@router.post("/products", response_model=MedicalSupplyPublic, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: MedicalSupplyCreate,
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> MedicalSupplyPublic:
    """Create a MedicalSupply catalog row. Authentication required."""
    return inventory_service.create_medical_supply(session, payload)


@router.get("/products/{id}", response_model=MedicalSupplyPublic)
def get_product(
    id: int,
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> MedicalSupplyPublic:
    """Return one MedicalSupply with computed current_stock."""
    return inventory_service.get_medical_supply(session, id)


@router.post(
    "/orders/inbound",
    response_model=SupplyDeliveryPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    payload: SupplyDeliveryCreate,
    session: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user),
) -> SupplyDeliveryPublic:
    """Register a SupplyDelivery attributed to the authenticated TinyDB user."""
    return inventory_service.create_supply_delivery(session, payload, current_user)


@router.post(
    "/orders/outbound",
    response_model=SupplyConsumptionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound_order(
    payload: SupplyConsumptionCreate,
    session: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user),
) -> SupplyConsumptionPublic:
    """Register a SupplyConsumption, or 400 if stock would go negative."""
    try:
        return inventory_service.create_supply_consumption(session, payload, current_user)
    except InsufficientSupplyStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/orders", response_model=list[InventoryOrderPublic])
def list_orders(
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> list[InventoryOrderPublic]:
    """List deliveries and consumptions with supply data, supply_id, and user_uuid."""
    return inventory_service.list_inventory_orders(session)
