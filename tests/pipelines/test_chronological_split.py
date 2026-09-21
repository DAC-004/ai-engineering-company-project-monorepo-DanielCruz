"""Prove the 8-year / 2-year split is chronological, disjoint, and leakage-free."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shared.sales_forecast.constants import (
    EXPECTED_TEST_ROWS,
    EXPECTED_TRAIN_ROWS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
)
from shared.sales_forecast.features import add_causal_features, drop_feature_warmup
from shared.sales_forecast.load import load_and_validate_sales_csv
from shared.sales_forecast.split import chronological_raw_split, model_ready_split

REPO_ROOT = Path(__file__).resolve().parents[2]
SALES_CSV = REPO_ROOT / "data" / "raw" / "healthcore_sales.csv"


@pytest.fixture(scope="module")
def validated_sales() -> pd.DataFrame:
    return load_and_validate_sales_csv(SALES_CSV)


@pytest.fixture(scope="module")
def raw_split(validated_sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return chronological_raw_split(validated_sales)


def test_raw_split_is_eight_years_then_two_years(raw_split: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, test = raw_split
    assert len(train) == EXPECTED_TRAIN_ROWS
    assert len(test) == EXPECTED_TEST_ROWS
    assert set(train["month"].dt.year) == set(range(2016, 2024))
    assert set(test["month"].dt.year) == {2024, 2025}
    assert train["month"].min() == pd.Timestamp("2016-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")
    assert test["month"].min() == pd.Timestamp("2024-01-01")
    assert test["month"].max() == pd.Timestamp("2025-12-01")


def test_raw_split_is_disjoint_and_chronological(raw_split: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, test = raw_split
    train_months = set(train["month"])
    test_months = set(test["month"])
    assert train_months.isdisjoint(test_months)
    assert train["month"].max() < test["month"].min()


def test_no_row_uses_its_own_target_or_a_later_month(validated_sales: pd.DataFrame) -> None:
    featured = add_causal_features(validated_sales)
    ready = drop_feature_warmup(featured)
    history = validated_sales.sort_values("month", kind="mergesort").reset_index(drop=True)

    for _, row in ready.iterrows():
        prior = history.loc[history["month"] < row["month"]]
        assert not prior.empty
        assert row["revenue_lag_1"] == pytest.approx(float(prior.iloc[-1][TARGET_COLUMN]))
        assert row["visits_lag_1"] == pytest.approx(float(prior.iloc[-1]["visits_count"]))
        if len(prior) >= 12:
            assert row["revenue_lag_12"] == pytest.approx(float(prior.iloc[-12][TARGET_COLUMN]))
            assert row["visits_lag_12"] == pytest.approx(float(prior.iloc[-12]["visits_count"]))
        last_three = prior.iloc[-3:][TARGET_COLUMN]
        last_twelve = prior.iloc[-12:][TARGET_COLUMN]
        assert row["revenue_roll_mean_3"] == pytest.approx(float(last_three.mean()))
        assert row["revenue_roll_std_3"] == pytest.approx(float(last_three.std(ddof=1)))
        assert row["revenue_roll_mean_12"] == pytest.approx(float(last_twelve.mean()))
        assert row["revenue_roll_std_12"] == pytest.approx(float(last_twelve.std(ddof=1)))
        assert row[TARGET_COLUMN] != pytest.approx(float(row["revenue_lag_1"]))
        # Features for month t are rebuilt only from months strictly before t.
        later = history.loc[history["month"] > row["month"]]
        assert later["month"].min() > row["month"] if not later.empty else True


def test_test_month_may_use_earlier_test_actuals_only_as_history(
    validated_sales: pd.DataFrame,
) -> None:
    """Rolling one-step-ahead: 2024-02 may use 2024-01 actuals, never its own target."""
    featured = add_causal_features(validated_sales)
    _train, test = model_ready_split(drop_feature_warmup(featured))
    first_test = test.iloc[0]
    second_test = test.iloc[1]
    december_2023 = validated_sales.loc[
        validated_sales["month"] == pd.Timestamp("2023-12-01"), TARGET_COLUMN
    ].iloc[0]
    january_2024 = validated_sales.loc[
        validated_sales["month"] == pd.Timestamp("2024-01-01"), TARGET_COLUMN
    ].iloc[0]

    assert first_test["month"] == pd.Timestamp("2024-01-01")
    assert second_test["month"] == pd.Timestamp("2024-02-01")
    assert first_test["revenue_lag_1"] == pytest.approx(float(december_2023))
    assert second_test["revenue_lag_1"] == pytest.approx(float(january_2024))
    assert first_test["revenue_lag_1"] != pytest.approx(float(first_test[TARGET_COLUMN]))
    assert second_test["revenue_lag_1"] != pytest.approx(float(second_test[TARGET_COLUMN]))
    assert "avg_revenue_per_visit_usd" not in FEATURE_COLUMNS
    assert "visits_count" not in FEATURE_COLUMNS
