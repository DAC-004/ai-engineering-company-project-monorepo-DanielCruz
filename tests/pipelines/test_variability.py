"""Training-only expanding-window variability must not use test or in-sample fit."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shared.sales_forecast.exceptions import VariabilityEstimationError
from shared.sales_forecast.features import add_causal_features, drop_feature_warmup
from shared.sales_forecast.load import load_and_validate_sales_csv
from shared.sales_forecast.split import model_ready_split
from shared.sales_forecast.variability import estimate_expanding_window_variability

REPO_ROOT = Path(__file__).resolve().parents[2]
SALES_CSV = REPO_ROOT / "data" / "raw" / "healthcore_sales.csv"


def test_variability_rejects_test_period_rows() -> None:
    sales = load_and_validate_sales_csv(SALES_CSV)
    featured = drop_feature_warmup(add_causal_features(sales))
    with pytest.raises(VariabilityEstimationError, match="Test-period"):
        estimate_expanding_window_variability(featured)


def test_variability_rejects_insufficient_training_history() -> None:
    sales = load_and_validate_sales_csv(SALES_CSV)
    train, _test = model_ready_split(drop_feature_warmup(add_causal_features(sales)))
    too_short = train.iloc[:10].copy()
    with pytest.raises(VariabilityEstimationError, match="In-sample residuals are not used"):
        estimate_expanding_window_variability(too_short, min_train_rows=24)


def test_variability_uses_only_training_months_and_reports_residual_count() -> None:
    sales = load_and_validate_sales_csv(SALES_CSV)
    train, test = model_ready_split(drop_feature_warmup(add_causal_features(sales)))
    result = estimate_expanding_window_variability(train, min_train_rows=24)
    expected_residuals = len(train) - 24
    assert result.n_residuals == expected_residuals
    assert result.n_residuals >= 8
    assert pd.Timestamp(result.first_validation_month) >= train["month"].iloc[24]
    assert pd.Timestamp(result.last_validation_month) == train["month"].max()
    assert pd.Timestamp(result.last_validation_month) < test["month"].min()
    assert result.residual_std >= 0
    assert "expanding-window" in result.method
