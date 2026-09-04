"""Pydantic contracts for the Monthly Clinic Supply Performance report."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class ClinicSupplyPerformance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: str
    country: str
    total_supply_cost: float
    supply_consumption_count: int
    critical_stockout_count: int
    expiry_risk_count: int
    currency: str


class MonthlyClinicSupplyPerformanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month_start: date
    clinics: list[ClinicSupplyPerformance]


class PipelineRunLatestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    started_at: str
    finished_at: str | None
    records_processed: int
    records_extracted: int
    records_loaded: int
    records_rejected: int
    month_start: date
    trigger_type: str
    error_message: str | None = None


class PipelineRunTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month_start: date | None = None


class PipelineRunAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    month_start: date
    records_processed: int = 0
    error_message: str | None = None
