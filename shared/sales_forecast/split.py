"""Chronological 8-year / 2-year split with no mixing of observations."""

from __future__ import annotations

from datetime import date

import pandas as pd

from shared.sales_forecast.constants import (
    EXPECTED_TEST_ROWS,
    EXPECTED_TRAIN_ROWS,
    TEST_END_MONTH,
    TEST_START_MONTH,
    TRAIN_END_MONTH,
    TRAIN_START_MONTH,
)
from shared.sales_forecast.exceptions import DatasetValidationError


def chronological_raw_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the raw dated series into 2016-2023 train and 2024-2025 test.

    The split is defined on calendar year before feature warmup is dropped so
    the 96/24 row contract can be tested independently of lag availability.
    """
    ordered = frame.sort_values("month", kind="mergesort").reset_index(drop=True)
    months = ordered["month"].dt.date
    train = ordered.loc[(months >= TRAIN_START_MONTH) & (months <= TRAIN_END_MONTH)].copy()
    test = ordered.loc[(months >= TEST_START_MONTH) & (months <= TEST_END_MONTH)].copy()
    assert_valid_raw_split(train, test)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def model_ready_split(featured: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the same calendar cut to rows that already have causal features."""
    ordered = featured.sort_values("month", kind="mergesort").reset_index(drop=True)
    months = ordered["month"].dt.date
    train = ordered.loc[(months >= TRAIN_START_MONTH) & (months <= TRAIN_END_MONTH)].copy()
    test = ordered.loc[(months >= TEST_START_MONTH) & (months <= TEST_END_MONTH)].copy()
    if train.empty or test.empty:
        raise DatasetValidationError("Model-ready split produced an empty train or test set.")
    _assert_disjoint_and_ordered(train, test)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def assert_valid_raw_split(train: pd.DataFrame, test: pd.DataFrame) -> None:
    """Prove the raw split is 8 years / 2 years, disjoint, and chronological."""
    if len(train) != EXPECTED_TRAIN_ROWS:
        raise DatasetValidationError(f"Expected {EXPECTED_TRAIN_ROWS} train rows, got {len(train)}")
    if len(test) != EXPECTED_TEST_ROWS:
        raise DatasetValidationError(f"Expected {EXPECTED_TEST_ROWS} test rows, got {len(test)}")

    train_years = set(train["month"].dt.year.tolist())
    test_years = set(test["month"].dt.year.tolist())
    if train_years != set(range(2016, 2024)):
        raise DatasetValidationError(f"Train years must be 2016-2023, got {sorted(train_years)}")
    if test_years != {2024, 2025}:
        raise DatasetValidationError(f"Test years must be 2024-2025, got {sorted(test_years)}")

    _assert_disjoint_and_ordered(train, test)


def _assert_disjoint_and_ordered(train: pd.DataFrame, test: pd.DataFrame) -> None:
    train_months = set(train["month"].dt.date.tolist())
    test_months = set(test["month"].dt.date.tolist())
    overlap = train_months & test_months
    if overlap:
        raise DatasetValidationError(f"Train and test share months: {sorted(overlap)}")

    latest_train: date = max(train_months)
    earliest_test: date = min(test_months)
    if latest_train >= earliest_test:
        raise DatasetValidationError(
            f"Train is not strictly before test: max train {latest_train}, min test {earliest_test}"
        )
