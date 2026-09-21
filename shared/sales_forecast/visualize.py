"""Test-period actual versus predicted plot with an empirical residual band."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from shared.sales_forecast.evaluation import LearningCurvePoint
from shared.sales_forecast.variability import ResidualVariability


def plot_actual_vs_predicted(
    test_frame: pd.DataFrame,
    predictions: pd.Series | list[float],
    variability: ResidualVariability,
    output_path: str | Path,
) -> Path:
    """Write the 2024-2025 comparison chart.

    The shaded band is prediction ± 1.96 * training-only expanding-window
    residual std. It is an empirical residual variability range, not a
    formal confidence interval or prediction interval.

    The plotted points are rolling one-step-ahead historical evaluations:
    each test month uses information available before that month, including
    actuals from completed earlier test months. This is not a single
    24-month-ahead forecast issued at the end of 2023.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    months = pd.to_datetime(test_frame["month"])
    actual = test_frame["revenue_usd"].to_numpy(dtype=float)
    predicted = pd.Series(predictions, index=test_frame.index).to_numpy(dtype=float)
    lower = predicted - variability.half_width
    upper = predicted + variability.half_width

    figure, axis = plt.subplots(figsize=(11, 6))
    axis.plot(months, actual, color="#1f4e79", marker="o", linewidth=2, label="Actual revenue")
    axis.plot(months, predicted, color="#c45911", marker="o", linewidth=2, label="Predicted revenue")
    axis.fill_between(
        months,
        lower,
        upper,
        color="#c45911",
        alpha=0.18,
        label=(
            f"Empirical residual range (±1.96 × train OOS residual std; "
            f"n={variability.n_residuals})"
        ),
    )
    axis.set_title("HealthCore monthly revenue: rolling one-step-ahead test evaluation")
    axis.set_xlabel("Test month")
    axis.set_ylabel("Revenue (USD)")
    axis.grid(True, alpha=0.3)
    axis.legend(loc="upper left")
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def plot_learning_curve(
    points: list[LearningCurvePoint],
    output_path: str | Path,
) -> Path:
    """Write training versus validation MAE and RMSE as history grows."""
    if not points:
        raise ValueError("Learning-curve plot requires at least one chronological point.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    train_sizes = [point.n_train_rows for point in points]
    train_mae = [point.train_mae_usd for point in points]
    val_mae = [point.val_mae_usd for point in points]
    train_rmse = [point.train_rmse_usd for point in points]
    val_rmse = [point.val_rmse_usd for point in points]

    figure, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(train_sizes, train_mae, color="#1f4e79", marker="o", linewidth=2, label="Training MAE")
    axes[0].plot(train_sizes, val_mae, color="#c45911", marker="o", linewidth=2, label="Validation MAE")
    axes[0].set_ylabel("MAE (USD)")
    axes[0].set_title("HealthCore revenue forecast learning curve")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="upper right")

    axes[1].plot(train_sizes, train_rmse, color="#1f4e79", marker="o", linewidth=2, label="Training RMSE")
    axes[1].plot(train_sizes, val_rmse, color="#c45911", marker="o", linewidth=2, label="Validation RMSE")
    axes[1].set_xlabel("Chronological training months (model-ready)")
    axes[1].set_ylabel("RMSE (USD)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="upper right")

    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination
