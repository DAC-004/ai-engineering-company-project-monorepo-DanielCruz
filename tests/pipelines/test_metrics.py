"""Focused tests for required metric definitions and sample rules."""

from __future__ import annotations

import numpy as np
import pytest

from shared.sales_forecast.exceptions import MetricComputationError
from shared.sales_forecast.metrics import (
    dagostino_pearson_k2,
    mean_absolute_error_usd,
    mean_squared_error_usd2,
    normalized_gini,
    population_stability_index,
    rmse_pct_of_average_monthly_revenue,
    root_mean_squared_error_usd,
)


def test_mse_and_rmse_percentage_are_distinct() -> None:
    actual = np.array([100.0, 200.0, 300.0])
    predicted = np.array([110.0, 190.0, 310.0])
    mse = mean_squared_error_usd2(actual, predicted)
    rmse_pct = rmse_pct_of_average_monthly_revenue(actual, predicted, average_monthly_revenue=200.0)
    assert mse == pytest.approx(100.0)
    assert rmse_pct == pytest.approx((10.0 / 200.0) * 100.0)
    assert mse != rmse_pct


def test_mae_and_rmse_are_in_usd_and_rmse_is_larger_when_errors_vary() -> None:
    actual = np.array([100.0, 200.0, 300.0])
    predicted = np.array([110.0, 190.0, 330.0])
    mae = mean_absolute_error_usd(actual, predicted)
    rmse = root_mean_squared_error_usd(actual, predicted)
    assert mae == pytest.approx((10.0 + 10.0 + 30.0) / 3.0)
    assert rmse == pytest.approx(((10.0**2 + 10.0**2 + 30.0**2) / 3.0) ** 0.5)
    assert rmse > mae


def test_normalized_gini_is_one_for_perfect_ranking() -> None:
    actual = np.array([1.0, 3.0, 2.0, 8.0])
    assert normalized_gini(actual, actual) == pytest.approx(1.0)


def test_psi_identical_distributions_is_near_zero() -> None:
    values = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    first = population_stability_index(values, values, n_bins=5, epsilon=1e-6)
    second = population_stability_index(values, values, n_bins=5, epsilon=1e-6)
    assert first["value"] == pytest.approx(0.0, abs=1e-12)
    assert first["value"] == second["value"]
    assert first["train_assigned"] == 10
    assert first["test_assigned"] == 10
    assert first["train_share_sum_before_epsilon"] == pytest.approx(1.0)
    assert first["test_share_sum_before_epsilon"] == pytest.approx(1.0)
    assert first["n_zero_test_bins"] == 0


def test_psi_shifted_distribution_is_positive() -> None:
    train = np.arange(1.0, 21.0)
    test = train + 15.0
    result = population_stability_index(train, test, n_bins=5, epsilon=1e-6)
    assert result["value"] > 0.1
    assert result["test_assigned"] == 20
    assert result["n_test_above_train_max"] > 0


def test_psi_zero_count_bins_remain_finite() -> None:
    train = np.arange(1.0, 11.0)
    test = np.array([1.0, 1.0, 1.0])
    result = population_stability_index(train, test, n_bins=5, epsilon=1e-6)
    assert np.isfinite(result["value"])
    assert result["n_zero_test_bins"] > 0
    assert result["test_assigned"] == 3
    assert result["test_share_sum_before_epsilon"] == pytest.approx(1.0)


def test_psi_out_of_training_range_values_are_assigned() -> None:
    train = np.arange(1.0, 11.0)
    test = np.array([0.0, 20.0, 25.0])
    result = population_stability_index(train, test, n_bins=5, epsilon=1e-6)
    assert result["test_assigned"] == 3
    assert result["n_test_below_train_min"] == 1
    assert result["n_test_above_train_max"] == 2
    assert result["train_assigned"] == 10


def test_psi_bins_come_from_train_only_and_use_epsilon() -> None:
    train = np.arange(1.0, 11.0)
    test = np.array([1.0, 1.0, 1.0, 20.0])
    result = population_stability_index(train, test, n_bins=5, epsilon=1e-6)
    assert result["train_n"] == 10
    assert result["test_n"] == 4
    assert result["train_assigned"] == 10
    assert result["test_assigned"] == 4
    assert result["epsilon"] == 1e-6
    assert np.isfinite(result["value"])
    assert "consolidated monthly visits_count" in result["population"]
    assert "US versus UK" in result["not_measured"]
    assert result["formula"].startswith("(test_share - train_share)")


def test_k2_rejects_undersized_residual_sample() -> None:
    with pytest.raises(MetricComputationError, match="at least 8"):
        dagostino_pearson_k2(np.arange(7, dtype=float))


def test_k2_returns_statistic_and_p_value_for_valid_sample() -> None:
    residuals = np.linspace(-3.0, 3.0, 24)
    result = dagostino_pearson_k2(residuals)
    assert result["n_residuals"] == 24
    assert np.isfinite(result["statistic"])
    assert 0.0 <= result["p_value"] <= 1.0
    assert result["not_a_forecast_accuracy_metric"] is True
