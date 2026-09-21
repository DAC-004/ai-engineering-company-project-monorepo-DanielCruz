"""Load and validate the supplied HealthCore monthly sales file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from shared.sales_forecast.constants import (
    EXPECTED_COLUMNS,
    EXPECTED_RAW_ROWS,
    RAW_END_MONTH,
    RAW_START_MONTH,
    REGION_VALUE,
)
from shared.sales_forecast.exceptions import DatasetValidationError


def _normalize_empty_cells(frame: pd.DataFrame) -> pd.DataFrame:
    """Treat blank and whitespace-only cells as missing before training."""
    cleaned = frame.copy()
    for column in cleaned.columns:
        if cleaned[column].dtype == object or str(cleaned[column].dtype) == "string":
            text = cleaned[column].astype("string").str.strip()
            cleaned[column] = text.mask(text.eq(""), other=pd.NA)
    return cleaned


def load_sales_csv(path: str | Path) -> pd.DataFrame:
    """Read `data/raw/healthcore_sales.csv` without altering numeric values."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DatasetValidationError(f"Sales dataset not found: {csv_path}")
    raw = pd.read_csv(csv_path)
    return _normalize_empty_cells(raw)


def validate_sales_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Confirm the file matches the HealthCore aggregated monthly contract.

    The check is read-only: values are parsed, not rewritten. Failures stop
    training instead of silently filling or simulating rows.
    """
    if list(frame.columns) != list(EXPECTED_COLUMNS):
        raise DatasetValidationError(
            f"Expected columns {list(EXPECTED_COLUMNS)}, got {list(frame.columns)}"
        )

    validated = frame.copy()
    try:
        validated["month"] = pd.to_datetime(validated["month"], format="%Y-%m-%d", errors="raise")
        validated["revenue_usd"] = pd.to_numeric(validated["revenue_usd"], errors="raise")
        validated["visits_count"] = pd.to_numeric(validated["visits_count"], errors="raise")
        validated["avg_revenue_per_visit_usd"] = pd.to_numeric(
            validated["avg_revenue_per_visit_usd"], errors="raise"
        )
        validated["region"] = validated["region"].astype("string")
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError(f"Could not parse HealthCore sales columns: {exc}") from exc

    if validated.isna().any().any():
        raise DatasetValidationError("Null or empty values remain after empty-cell handling.")

    if len(validated) != EXPECTED_RAW_ROWS:
        raise DatasetValidationError(
            f"Expected {EXPECTED_RAW_ROWS} monthly rows, got {len(validated)}"
        )

    validated = validated.sort_values("month", kind="mergesort").reset_index(drop=True)
    months = validated["month"].dt.date
    if months.nunique() != len(validated):
        raise DatasetValidationError("Duplicate months are present.")
    if months.min() != RAW_START_MONTH or months.max() != RAW_END_MONTH:
        raise DatasetValidationError(
            f"Expected month range {RAW_START_MONTH} through {RAW_END_MONTH}, "
            f"got {months.min()} through {months.max()}"
        )

    expected_months = pd.date_range(RAW_START_MONTH, RAW_END_MONTH, freq="MS")
    observed_months = pd.to_datetime(validated["month"]).reset_index(drop=True)
    if not observed_months.to_numpy().tolist() == expected_months.to_numpy().tolist():
        raise DatasetValidationError("The month series is not a continuous first-of-month range.")

    if not validated["region"].eq(REGION_VALUE).all():
        raise DatasetValidationError(
            f"Expected only {REGION_VALUE!r} region rows; US/UK rows are not in this dataset."
        )

    if not (validated["revenue_usd"] > 0).all():
        raise DatasetValidationError("revenue_usd must be strictly positive.")
    if not (validated["visits_count"] > 0).all():
        raise DatasetValidationError("visits_count must be strictly positive.")
    if not (validated["avg_revenue_per_visit_usd"] > 0).all():
        raise DatasetValidationError("avg_revenue_per_visit_usd must be strictly positive.")

    return validated


def load_and_validate_sales_csv(path: str | Path) -> pd.DataFrame:
    """Load the supplied file and validate it against the HealthCore contract."""
    return validate_sales_frame(load_sales_csv(path))
