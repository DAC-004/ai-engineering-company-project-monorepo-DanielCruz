"""Exact seven briefing suppliers. Interpreting is not coerced into directory categories."""

from __future__ import annotations

from dataclasses import dataclass

from agents.supplier_contracts.country import to_directory_country


@dataclass(frozen=True)
class SupplierRecord:
    supplier_id: str
    display_name: str
    country: str
    directory_country: str
    category: str
    currency: str
    processes_patient_data: bool
    has_contract: bool
    contract_id: str | None
    quote_only: bool
    product: str
    unit: str
    base_price: str
    monthly_volume: str
    estimated_annual_value: str | None
    dpa_kind: str | None  # BAA, DPA, none, na


SUPPLIERS: tuple[SupplierRecord, ...] = (
    SupplierRecord(
        "HC-S01",
        "MedSupply Partners",
        "United States",
        to_directory_country("United States"),
        "clinical_consumables",
        "USD",
        False,
        True,
        "CT-HC-01",
        False,
        "Disposable consultation kit",
        "kit",
        "3.20",
        "14000",
        "537600",
        "na",
    ),
    SupplierRecord(
        "HC-S02",
        "CareSource Medical",
        "United States",
        to_directory_country("United States"),
        "clinical_consumables",
        "USD",
        False,
        False,
        None,
        True,
        "Disposable consultation kit",
        "kit",
        "3.05",
        "0",
        None,
        "na",
    ),
    SupplierRecord(
        "HC-S03",
        "ClearPath Labs",
        "United States",
        to_directory_country("United States"),
        "laboratory",
        "USD",
        True,
        True,
        "CT-HC-02",
        False,
        "Basic metabolic panel",
        "test",
        "18.00",
        "2500",
        "540000",
        "BAA",
    ),
    SupplierRecord(
        "HC-S04",
        "Lone Star Diagnostics",
        "United States",
        to_directory_country("United States"),
        "laboratory",
        "USD",
        True,
        False,
        None,
        True,
        "Basic metabolic panel",
        "test",
        "17.20",
        "0",
        None,
        None,
    ),
    SupplierRecord(
        "HC-S05",
        "BritMed Supplies",
        "United Kingdom",
        to_directory_country("United Kingdom"),
        "clinical_consumables",
        "GBP",
        False,
        False,
        None,
        False,
        "Disposable consultation kit",
        "kit",
        "2.70",
        "3500",
        None,
        "na",
    ),
    SupplierRecord(
        "HC-S06",
        "Thames Pathology",
        "United Kingdom",
        to_directory_country("United Kingdom"),
        "laboratory",
        "GBP",
        True,
        True,
        "CT-HC-03",
        False,
        "Basic metabolic panel",
        "test",
        "14.50",
        "700",
        "121800",
        None,
    ),
    SupplierRecord(
        "HC-S07",
        "LinguaCare Interpreting",
        "United States",
        to_directory_country("United States"),
        "medical_interpreting",
        "USD",
        True,
        True,
        "CT-HC-04",
        False,
        "Medical interpreting",
        "minute",
        "1.95",
        "9000",
        "210600",
        "BAA",
    ),
)

BY_ID = {item.supplier_id: item for item in SUPPLIERS}


def require_supplier(supplier_id: str) -> SupplierRecord:
    if supplier_id not in BY_ID:
        raise KeyError(supplier_id)
    return BY_ID[supplier_id]
