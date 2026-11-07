"""Celery tick for supplier-contract alerts. Default schedule is off. Internal outbox only."""

from __future__ import annotations

from app.celery_app import celery_app


@celery_app.task(name="app.tasks_supplier_contracts.tick_supplier_contract_alerts")
def tick_supplier_contract_alerts() -> dict:
    from app.services.supplier_contracts_service import tick

    return tick()
