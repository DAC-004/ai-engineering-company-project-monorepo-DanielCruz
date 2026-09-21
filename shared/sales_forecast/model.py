"""Random Forest regressor construction and fitting.

Tree-based models do not require feature scaling: split selection is
invariant to monotonic rescaling of individual columns. No scaler is
applied.
"""

from __future__ import annotations

from sklearn.ensemble import RandomForestRegressor

from shared.sales_forecast.constants import (
    MAX_DEPTH,
    MIN_SAMPLES_LEAF,
    N_ESTIMATORS,
    RANDOM_STATE,
)


def build_regressor(random_state: int = RANDOM_STATE) -> RandomForestRegressor:
    """Return a reproducible Random Forest with conservative defaults.

    Random Forest is selected over XGBoost because the training sample is
    small (tens of monthly rows after lag warmup), Sandra and Tom need an
    explainable error story rather than sequential boosting, and the
    available tuning budget is limited. Averaged trees are the assignment's
    stated starting point for explainability.
    """
    return RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        random_state=random_state,
        n_jobs=1,
    )


def fit_regressor(
    model: RandomForestRegressor,
    features,
    target,
) -> RandomForestRegressor:
    """Fit on training rows only."""
    model.fit(features, target)
    return model
