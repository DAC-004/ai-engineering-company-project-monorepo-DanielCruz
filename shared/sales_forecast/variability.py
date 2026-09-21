"""Training-only out-of-sample residual variability.

The shaded forecast band is an empirical residual range, not a formal
confidence interval or prediction interval. Residuals are collected with
an expanding-window walk-forward inside the training period so the band
is not estimated from in-sample fit on the same observations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from shared.sales_forecast.constants import (
    EXPANDING_MIN_TRAIN_ROWS,
    RANDOM_STATE,
    TEST_START_MONTH,
    TRAIN_END_MONTH,
    VARIABILITY_MIN_RESIDUALS,
    VARIABILITY_Z_SCORE,
)
from shared.sales_forecast.exceptions import VariabilityEstimationError
from shared.sales_forecast.features import feature_matrix, target_vector
from shared.sales_forecast.model import build_regressor, fit_regressor


@dataclass(frozen=True)
class ResidualVariability:
    """Empirical residual scale estimated inside the training period."""

    residual_std: float
    half_width: float
    n_residuals: int
    first_validation_month: str
    last_validation_month: str
    min_train_rows: int
    method: str


def estimate_expanding_window_variability(
    model_ready_train: pd.DataFrame,
    min_train_rows: int = EXPANDING_MIN_TRAIN_ROWS,
    random_state: int = RANDOM_STATE,
) -> ResidualVariability:
    """Estimate residual std from chronological expanding-window predictions.

    Procedure:
    1. Use only model-ready training rows (months through 2023-12).
    2. For each origin i from `min_train_rows` to n-1, fit on rows [0, i)
       and predict row i.
    3. Keep finite residuals only.
    4. residual_std is the sample standard deviation of those residuals.
    5. The plot band is prediction ± 1.96 * residual_std.

    Chronological order is preserved. A validation month is never used to
    train its own model, and no later training month is used either.
    Test-period targets are not used to estimate or calibrate the band.

    If the training history cannot produce enough finite out-of-sample
    residuals, this function raises instead of falling back to in-sample
    residuals.
    """
    ordered = model_ready_train.sort_values("month", kind="mergesort").reset_index(drop=True)
    if ordered.empty:
        raise VariabilityEstimationError("No model-ready training rows for variability estimation.")

    if (ordered["month"].dt.date >= TEST_START_MONTH).any():
        raise VariabilityEstimationError(
            "Test-period rows were passed to training-only variability estimation."
        )
    latest_train = ordered["month"].dt.date.max()
    if latest_train > TRAIN_END_MONTH:
        raise VariabilityEstimationError(
            f"Variability input includes months after the training end {TRAIN_END_MONTH}."
        )

    n_rows = len(ordered)
    if n_rows <= min_train_rows:
        raise VariabilityEstimationError(
            "Expanding-window variability needs more than "
            f"{min_train_rows} model-ready training rows; got {n_rows}. "
            "In-sample residuals are not used as a fallback."
        )

    features = feature_matrix(ordered).to_numpy(dtype=float)
    target = target_vector(ordered).to_numpy(dtype=float)
    residuals: list[float] = []
    validation_months: list[str] = []

    for origin in range(min_train_rows, n_rows):
        # Fit only on earlier training months; predict the next training month.
        model = build_regressor(random_state=random_state)
        fit_regressor(model, features[:origin], target[:origin])
        prediction = float(model.predict(features[origin : origin + 1])[0])
        residual = float(target[origin] - prediction)
        if np.isfinite(residual):
            residuals.append(residual)
            validation_months.append(ordered.iloc[origin]["month"].strftime("%Y-%m-%d"))

    if len(residuals) < VARIABILITY_MIN_RESIDUALS:
        raise VariabilityEstimationError(
            "Expanding-window estimation produced "
            f"{len(residuals)} finite training-only out-of-sample residuals; "
            f"need at least {VARIABILITY_MIN_RESIDUALS}. "
            "In-sample residuals are not used as a fallback."
        )

    residual_std = float(np.std(np.asarray(residuals, dtype=float), ddof=1))
    if not np.isfinite(residual_std) or residual_std < 0:
        raise VariabilityEstimationError("Residual standard deviation is not a finite non-negative number.")

    return ResidualVariability(
        residual_std=residual_std,
        half_width=VARIABILITY_Z_SCORE * residual_std,
        n_residuals=len(residuals),
        first_validation_month=validation_months[0],
        last_validation_month=validation_months[-1],
        min_train_rows=min_train_rows,
        method=(
            "chronological expanding-window walk-forward inside the training "
            f"period: fit on the first i model-ready training months, predict "
            f"month i+1, for i from {min_train_rows} to n-1; residual_std is "
            "the sample standard deviation of finite out-of-sample residuals"
        ),
    )
