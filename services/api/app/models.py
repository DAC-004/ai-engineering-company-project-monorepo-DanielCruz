"""Pydantic contracts for the HealthCore Supplier Directory."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VALID_CATEGORIES = [
    "medical_supplies",
    "laboratory_services",
    "pharmaceutical",
    "clinical_software",
    "it_infrastructure",
    "hr_and_payroll_software",
    "cleaning_and_facilities",
    "patient_communication",
    "billing_and_coding_software",
    "training_platforms",
]

CountryCode = Literal["USA", "UK"]
CurrencyCode = Literal["USD", "GBP"]
ComplianceAgreement = Literal["BAA", "DPA", "both"]


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


COUNTRY_CURRENCY = {
    "USA": "USD",
    "UK": "GBP",
}


def validate_country_currency(country: str, currency: str) -> None:
    expected = COUNTRY_CURRENCY.get(country)
    if expected is None:
        raise ValueError("country must be 'USA' or 'UK'")
    if currency != expected:
        raise ValueError(
            f"currency for {country} must be {expected}; received {currency}"
        )


class SupplierCreate(BaseModel):
    """Client-submitted supplier payload. updated_at is system-generated."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    country: CountryCode
    categories: list[str] = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    currency: CurrencyCode
    status: SupplierStatus
    compliance_agreement: ComplianceAgreement | None = None
    contract_renewal_date: str | None = None
    contact_email: str | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def categories_must_be_valid(cls, categories: list[str]) -> list[str]:
        if not categories:
            raise ValueError("at least one category is required")
        invalid = [category for category in categories if category not in VALID_CATEGORIES]
        if invalid:
            raise ValueError(
                f"invalid categories: {invalid}; allowed: {VALID_CATEGORIES}"
            )
        return categories

    @field_validator("contract_renewal_date")
    @classmethod
    def renewal_date_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # Enforce YYYY-MM-DD without inventing calendar rules beyond parseability.
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("contract_renewal_date must use YYYY-MM-DD") from exc
        return value

    @model_validator(mode="after")
    def enforce_country_currency(self) -> SupplierCreate:
        validate_country_currency(self.country, self.currency)
        return self


class SupplierResponse(BaseModel):
    """Full supplier record returned by the API, including TinyDB id."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: CountryCode
    categories: list[str]
    monthly_rate: float
    currency: CurrencyCode
    updated_at: datetime
    status: SupplierStatus
    compliance_agreement: ComplianceAgreement | None = None
    contract_renewal_date: str | None = None
    contact_email: str | None = None
    notes: str | None = None


class RateUpdate(BaseModel):
    monthly_rate: float = Field(gt=0)


class StatusUpdate(BaseModel):
    status: SupplierStatus
