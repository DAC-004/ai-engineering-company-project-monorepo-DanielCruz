"""Required evaluation metrics with explicit, documented definitions.

MSE, normalized Gini, and D'Agostino-Pearson K2 use held-out test
predictions and targets. PSI is the required exception: it compares the
training and test `visits_count` populations and is a train-versus-test
shift metric, not a test-only accuracy score.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from shared.sales_forecast.constants import (
    K2_MIN_SAMPLE_SIZE,
    PSI_EPSILON,
    PSI_N_BINS,
)
from shared.sales_forecast.exceptions import MetricComputationError


def mean_squared_error_usd2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Test-set mean squared error in USD squared."""
    actual, predicted = _as_aligned_floats(y_true, y_pred)
    return float(np.mean((actual - predicted) ** 2))


def rmse_pct_of_average_monthly_revenue(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    average_monthly_revenue: float,
) -> float:
    """RMSE as a percent of average monthly revenue.

    This is not MSE. MSE is in USD² and cannot be divided by revenue in USD.
    """
    if average_monthly_revenue <= 0:
        raise MetricComputationError("Average monthly revenue must be positive.")
    mse = mean_squared_error_usd2(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    return float((rmse / average_monthly_revenue) * 100.0)


def _gini_coefficient(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Lorenz-style ranking Gini of `actual` ordered by `predicted`."""
    n = actual.size
    order = np.lexsort((np.arange(n), -predicted))
    ranked = actual[order]
    total = ranked.sum()
    if total == 0:
        raise MetricComputationError("Gini is undefined when actuals sum to 0.")
    return float(ranked.cumsum().sum() / total - (n + 1) / 2.0) / n


def normalized_gini(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Normalized ranking Gini on test actuals versus test predictions.

    Equals 1 when predictions rank months in the same order as actuals. This
    is not classification impurity. A high value means the model can separate
    a normal low-season month from an atypical drop.
    """
    actual, predicted = _as_aligned_floats(y_true, y_pred)
    denominator = _gini_coefficient(actual, actual)
    if denominator == 0:
        raise MetricComputationError("Normalized Gini is undefined when perfect-rank Gini is 0.")
    return float(_gini_coefficient(actual, predicted) / denominator)


def population_stability_index(
    train_visits: np.ndarray,
    test_visits: np.ndarray,
    n_bins: int = PSI_N_BINS,
    epsilon: float = PSI_EPSILON,
) -> dict[str, Any]:
    """Standard PSI of consolidated monthly `visits_count`, train versus test.

    Bin edges are estimated from the training population only and then applied
    to the test population. Zero proportions are replaced with `epsilon` before
    the log term so empty bins do not produce division-by-zero or log-of-zero.

    This measures distribution shift in consolidated monthly visit volume. It
    does not measure US versus UK visit mix: the supplied file has only
    consolidated rows.
    """
    train = np.asarray(train_visits, dtype=float)
    test = np.asarray(test_visits, dtype=float)
    train = train[np.isfinite(train)]
    test = test[np.isfinite(test)]
    if train.size == 0 or test.size == 0:
        raise MetricComputationError("PSI requires finite train and test visits_count values.")
    if n_bins < 2:
        raise MetricComputationError("PSI requires at least 2 bins.")

    quantiles = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.unique(np.quantile(train, quantiles, method="linear"))
    if edges.size < 2:
        raise MetricComputationError("Training visits_count did not produce usable PSI bins.")

    # Open the outer edges so test values outside the train range still score.
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    train_counts, _ = np.histogram(train, bins=edges)
    test_counts, _ = np.histogram(test, bins=edges)
    if int(train_counts.sum()) != int(train.size) or int(test_counts.sum()) != int(test.size):
        raise MetricComputationError(
            "PSI discarded observations: "
            f"train assigned {int(train_counts.sum())}/{int(train.size)}, "
            f"test assigned {int(test_counts.sum())}/{int(test.size)}."
        )
    train_share = train_counts / train_counts.sum()
    test_share = test_counts / test_counts.sum()
    train_share_sum = float(train_share.sum())
    test_share_sum = float(test_share.sum())
    if not np.isclose(train_share_sum, 1.0) or not np.isclose(test_share_sum, 1.0):
        raise MetricComputationError(
            "PSI proportions must sum to 1 before epsilon handling: "
            f"train={train_share_sum}, test={test_share_sum}."
        )

    # Documented zero-protection: replace proportions below epsilon, do not refit bins.
    train_adj = np.where(train_share < epsilon, epsilon, train_share)
    test_adj = np.where(test_share < epsilon, epsilon, test_share)
    bin_psi = (test_adj - train_adj) * np.log(test_adj / train_adj)
    value = float(np.sum(bin_psi))
    finite_internal_max = float(np.max(train))
    finite_internal_min = float(np.min(train))

    if value < 0.1:
        interpretation = "small shift (industry convention: PSI < 0.1)"
    elif value <= 0.25:
        interpretation = "moderate shift (industry convention: 0.1 <= PSI <= 0.25)"
    else:
        interpretation = "large shift (industry convention: PSI > 0.25)"

    return {
        "value": value,
        "n_bins_requested": n_bins,
        "n_bins_used": int(train_counts.size),
        "n_edges": int(edges.size),
        "epsilon": epsilon,
        "train_n": int(train.size),
        "test_n": int(test.size),
        "train_assigned": int(train_counts.sum()),
        "test_assigned": int(test_counts.sum()),
        "train_share_sum_before_epsilon": train_share_sum,
        "test_share_sum_before_epsilon": test_share_sum,
        "n_zero_train_bins": int(np.sum(train_counts == 0)),
        "n_zero_test_bins": int(np.sum(test_counts == 0)),
        "n_test_below_train_min": int(np.sum(test < finite_internal_min)),
        "n_test_above_train_max": int(np.sum(test > finite_internal_max)),
        "formula": "(test_share - train_share) * ln(test_share / train_share), summed over bins",
        "binning": (
            "10 quantile bins from training visits_count only; the same edges "
            "are applied to the test population"
        ),
        "zero_protection": (
            f"bin proportions below {epsilon} are replaced with {epsilon} "
            "before the log term; bins are never refit on test"
        ),
        "interpretation": interpretation,
        "population": (
            "consolidated monthly visits_count, chronological train versus test"
        ),
        "not_measured": (
            "US versus UK visit mix; the supplied dataset contains only "
            "consolidated rows and no regional records were fabricated"
        ),
    }


def dagostino_pearson_k2(residuals: np.ndarray) -> dict[str, Any]:
    """D'Agostino-Pearson K2 residual-normality statistic on test residuals.

    The assignment names this 'K2 Score' but does not define a formula. This
    implementation is not a forecast-accuracy metric, not R², and not the
    Kolmogorov-Smirnov statistic. It tests whether the test residual
    distribution significantly departs from normality.
    """
    values = np.asarray(residuals, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < K2_MIN_SAMPLE_SIZE:
        raise MetricComputationError(
            "D'Agostino-Pearson K2 requires at least "
            f"{K2_MIN_SAMPLE_SIZE} finite test residuals; got {values.size}."
        )
    statistic, p_value = stats.normaltest(values)
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "n_residuals": int(values.size),
        "label": "D'Agostino-Pearson K2 residual-normality statistic",
        "null_hypothesis": "test residuals are consistent with a normal distribution",
        "not_a_forecast_accuracy_metric": True,
    }


def _as_aligned_floats(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    if actual.shape != predicted.shape:
        raise MetricComputationError("Actual and predicted arrays must have the same shape.")
    if actual.size == 0:
        raise MetricComputationError("Metric arrays are empty.")
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise MetricComputationError("Metric arrays contain non-finite values.")
    return actual, predicted
