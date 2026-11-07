"""Generate the briefing CSV and four English contract PDFs."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.supplier_contracts.pdf import write_pdf
from agents.supplier_contracts.registry import SUPPLIERS

# Exact last-month unit prices from the briefing. Do not quantize S01's 3.344
# to two decimals; that would change 4.5% / USD 24192 into a different case.
LAST_MONTH_PRICE = {
    "HC-S01": Decimal("3.344"),
    "HC-S02": Decimal("3.05"),
    "HC-S03": Decimal("19.26"),
    "HC-S04": Decimal("17.20"),
    "HC-S05": Decimal("2.70"),
    "HC-S06": Decimal("14.79"),
    "HC-S07": Decimal("1.95"),
}

ANNUAL_VALUE_CLAUSES = {
    "CT-HC-01": "8. Estimated annual value. The estimated annual value of this agreement is 537600 USD.",
    "CT-HC-02": "8. Estimated annual value. The estimated annual value of this agreement is 540000 USD.",
    "CT-HC-03": "8. Estimated annual value. The estimated annual value of this agreement is 121800 GBP.",
    "CT-HC-04": "8. Estimated annual value. The estimated annual value of this agreement is 210600 USD.",
}

BILLING_BODIES = {
    "CT-HC-01": (
        "9. Billing. Invoices are payable to MedSupply Partners Treasury, "
        "100 Fictional Way, Austin. Bank sort code 12-99-00 account 00019991. "
        "Billing contact: Reese Dalton, 14 Harbor Lane, reese.dalton@medsupply.invalid, +1-555-0148."
    ),
    "CT-HC-02": (
        "9. Billing. Pay ClearPath Labs Finance, 22 Specimen Street, Dallas. "
        "IBAN GB82WEST12345698765432. Billing contact: Morgan Ellis, "
        "9 Copper Road, morgan.ellis@clearpathlabs.invalid, +1-555-0172."
    ),
    "CT-HC-03": (
        "9. Billing. Thames Pathology Accounts, 7 Millbank Street, London. "
        "Sort code 20-00-00 account 12345678. Billing contact: Samira Cole, "
        "3 Quay Lane, samira.cole@thamespath.invalid, +44-555-0199."
    ),
    "CT-HC-04": (
        "9. Billing. LinguaCare Interpreting Treasury, 55 Congress Avenue, Austin. "
        "Account 44556677. Billing contact: Avery Quinn, 8 River Way, "
        "avery.quinn@linguacare.invalid, +1-555-0188."
    ),
}

BAA_ANNEX = [
    "Annex A. Signed Business Associate Agreement.",
    "This annex is the signed Business Associate Agreement between HealthCore Compliance and the supplier.",
    "It covers protected health information processed under this contract.",
    "The annex is fictional evidence for extraction tests and contains no bank details.",
]


def month_keys(load_date: date) -> list[str]:
    year, month = load_date.year, load_date.month
    keys: list[str] = []
    for _ in range(12):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    keys.reverse()
    return keys


def write_price_csv(path: Path, load_date: date) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    months = month_keys(load_date)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["supplier_id", "product", "unit", "currency", "month", "unit_price", "monthly_volume"]
        )
        for supplier in SUPPLIERS:
            last = LAST_MONTH_PRICE[supplier.supplier_id]
            base = Decimal(supplier.base_price)
            for index, month in enumerate(months):
                price = last if index == 11 else base
                writer.writerow(
                    [
                        supplier.supplier_id,
                        supplier.product,
                        supplier.unit,
                        supplier.currency,
                        month,
                        format(price, "f"),
                        supplier.monthly_volume,
                    ]
                )
    return path


def _pages(contract_id: str, body: list[str], annex: bool) -> list[list[str]]:
    pages = [
        body,
        [BILLING_BODIES[contract_id], "10. Notices. Formal notices use the addresses in clause 9."],
    ]
    if annex:
        pages.append(list(BAA_ANNEX))
    return pages


def write_contract_pdfs(directory: Path) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    specs = {
        "CT-HC-01": (
            [
                "CT-HC-01 MedSupply Partners clinical consumables agreement.",
                "1. Parties. HealthCore and MedSupply Partners.",
                "2. Term. This agreement expires 180 days after the HealthCore data-load date.",
                "3. Non-renewal notice. Either party must give 60 days' notice before expiry.",
                "4. Price revision. Annual increases are capped at 5 percent of the prior unit price.",
                "5. Exit. Either party may exit with 90 days' notice and no penalty.",
                "6. Data protection. Not applicable. This supplier does not process patient data.",
                "7. Governing language. English.",
                ANNUAL_VALUE_CLAUSES["CT-HC-01"],
            ],
            False,
        ),
        "CT-HC-02": (
            [
                "CT-HC-02 ClearPath Labs laboratory services agreement.",
                "1. Parties. HealthCore and ClearPath Labs.",
                "2. Term. This agreement expires 60 days after the HealthCore data-load date.",
                "3. Non-renewal notice. Either party must give 45 days' notice before expiry.",
                "4. Price revision. Annual increases are capped at the US Consumer Price Index.",
                "5. Exit. Early termination carries a penalty of two months of average billing. The averaging period is not specified in this agreement.",
                "6. Data protection. A signed BAA is annexed to this contract.",
                "7. Governing language. English.",
                ANNUAL_VALUE_CLAUSES["CT-HC-02"],
            ],
            True,
        ),
        "CT-HC-03": (
            [
                "CT-HC-03 Thames Pathology laboratory services agreement.",
                "1. Parties. HealthCore and Thames Pathology.",
                "2. Term. This agreement expires 210 days after the HealthCore data-load date.",
                "3. Non-renewal notice. Either party must give 90 days' notice before expiry.",
                "4. Price revision. Annual increases are capped at 3 percent of the prior unit price.",
                "5. Exit. Either party may exit with 90 days' notice and no penalty.",
                "6. Data protection. This contract includes no DPA.",
                "7. Governing language. English.",
                ANNUAL_VALUE_CLAUSES["CT-HC-03"],
            ],
            False,
        ),
        "CT-HC-04": (
            [
                "CT-HC-04 LinguaCare Interpreting medical interpreting agreement.",
                "1. Parties. HealthCore and LinguaCare Interpreting.",
                "2. Term. This agreement expires 28 days after the HealthCore data-load date.",
                "3. Non-renewal notice. Either party must give 15 days' notice before expiry.",
                "4. Price revision. The unit price is fixed for the full term.",
                "5. Exit. There is no penalty for ending this agreement.",
                "6. Data protection. A signed BAA is annexed to this contract.",
                "7. Governing language. English.",
                ANNUAL_VALUE_CLAUSES["CT-HC-04"],
            ],
            True,
        ),
    }
    hashes: dict[str, str] = {}
    for contract_id, (lines, annex) in specs.items():
        hashes[contract_id] = write_pdf(directory / f"{contract_id}.pdf", _pages(contract_id, lines, annex))
    return hashes


def seed_raw(root: Path, load_date: date) -> dict[str, str]:
    csv_path = root / "prices.csv"
    write_price_csv(csv_path, load_date)
    return write_contract_pdfs(root / "pdfs")
