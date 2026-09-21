"""Leakage-safe temporal evaluation for the existing HealthCore forecast.

Cross-validation and the learning curve run only on the 2016-2023 training
period. They reuse the already-tuned Random Forest and the causal feature
functions; they do not retune or replace the model.

Feature tables are rebuilt for every fold and every learning-curve window
from the raw prefix that ends at that window's last validation month.
That keeps later-fold actuals out of earlier lag and rolling windows even
though the feature formulas themselves are already causal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from shared.sales_forecast.constants import (
    LEARNING_CURVE_MIN_TRAIN_ROWS,
    LEARNING_CURVE_STEP_MONTHS,
    LEARNING_CURVE_VAL_MONTHS,
    TARGET_COLUMN,
    TEMPORAL_CV_N_SPLITS,
    TEST_START_MONTH,
)
from shared.sales_forecast.exceptions import DatasetValidationError
from shared.sales_forecast.features import (
    add_causal_features,
    drop_feature_warmup,
    feature_matrix,
    target_vector,
)
from shared.sales_forecast.metrics import mean_absolute_error_usd, root_mean_squared_error_usd
from shared.sales_forecast.model import build_regressor, fit_regressor


@dataclass(frozen=True)
class TemporalFoldSplit:
    """One chronological TimeSeriesSplit fold with an explicit feature prefix."""

    fold_id: int
    n_splits: int
    train_positions: tuple[int, ...]
    val_positions: tuple[int, ...]
    train_months: tuple[pd.Timestamp, ...]
    val_months: tuple[pd.Timestamp, ...]
    feature_source_months: tuple[pd.Timestamp, ...]
    feature_source_end: pd.Timestamp
    splitter_name: str
    shuffled: bool


@dataclass(frozen=True)
class FoldMetricResult:
    """Train and validation MAE/RMSE for one temporal fold."""

    fold_id: int
    n_train_rows: int
    n_val_rows: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    feature_source_end: str
    train_mae_usd: float
    train_rmse_usd: float
    val_mae_usd: float
    val_rmse_usd: float


@dataclass(frozen=True)
class LearningCurvePoint:
    """One expanding-history point on the leakage-safe learning curve."""

    n_train_rows: int
    n_val_rows: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    feature_source_end: str
    train_mae_usd: float
    train_rmse_usd: float
    val_mae_usd: float
    val_rmse_usd: float


def chronological_model_ready_training_months(raw_train: pd.DataFrame) -> pd.Series:
    """Return model-ready training months in chronological order.

    Warmup is determined from the full 8-year training prefix only, never
    from 2024-2025 holdout months. The returned months are the rows that
    TimeSeriesSplit is allowed to place into train or validation.
    """
    ordered = _require_training_period(raw_train)
    ready = drop_feature_warmup(add_causal_features(ordered))
    if ready.empty:
        raise DatasetValidationError("No model-ready training months after causal warmup.")
    return ready["month"].reset_index(drop=True)


def build_leakage_safe_temporal_folds(
    raw_train: pd.DataFrame,
    n_splits: int = TEMPORAL_CV_N_SPLITS,
) -> list[TemporalFoldSplit]:
    """Build TimeSeriesSplit folds without shuffling or future-fold features.

    `TimeSeriesSplit` has no shuffle parameter and expands the training
    prefix forward. For each fold, the feature source is the raw training
    months from the series start through that fold's last validation month.
    Later-fold months are therefore absent from earlier lag and rolling
    windows.
    """
    if n_splits < 5:
        raise DatasetValidationError("Temporal cross-validation requires at least 5 folds.")

    ordered_raw = _require_training_period(raw_train)
    ready_months = chronological_model_ready_training_months(ordered_raw)
    splitter = TimeSeriesSplit(n_splits=n_splits)
    splits: list[TemporalFoldSplit] = []

    # Positions are 0..n-1 on the already-sorted model-ready month list.
    # TimeSeriesSplit iterates that sequence; it does not permute it.
    for fold_id, (train_pos, val_pos) in enumerate(splitter.split(ready_months), start=1):
        if train_pos.size == 0 or val_pos.size == 0:
            raise DatasetValidationError(f"Fold {fold_id} produced an empty train or validation set.")
        if np.any(np.diff(train_pos) <= 0) or np.any(np.diff(val_pos) <= 0):
            raise DatasetValidationError(f"Fold {fold_id} is not strictly increasing.")
        if train_pos.max() >= val_pos.min():
            raise DatasetValidationError(
                f"Fold {fold_id} places a training position at or after validation."
            )

        train_months = tuple(pd.Timestamp(value) for value in ready_months.iloc[train_pos])
        val_months = tuple(pd.Timestamp(value) for value in ready_months.iloc[val_pos])
        feature_source_end = max(val_months)
        feature_source = ordered_raw.loc[ordered_raw["month"] <= feature_source_end, "month"]
        splits.append(
            TemporalFoldSplit(
                fold_id=fold_id,
                n_splits=n_splits,
                train_positions=tuple(int(index) for index in train_pos),
                val_positions=tuple(int(index) for index in val_pos),
                train_months=train_months,
                val_months=val_months,
                feature_source_months=tuple(pd.Timestamp(value) for value in feature_source),
                feature_source_end=feature_source_end,
                splitter_name=type(splitter).__name__,
                shuffled=False,
            )
        )

    assert_temporal_folds_are_chronological(splits)
    return splits


def iter_leakage_safe_temporal_folds(
    raw_train: pd.DataFrame,
    n_splits: int = TEMPORAL_CV_N_SPLITS,
) -> Iterator[TemporalFoldSplit]:
    """Yield the leakage-safe temporal folds in fold-id order."""
    yield from build_leakage_safe_temporal_folds(raw_train, n_splits=n_splits)


def assert_temporal_folds_are_chronological(folds: list[TemporalFoldSplit]) -> None:
    """Fail if any fold shuffles time or trains on a future month."""
    if len(folds) < 5:
        raise DatasetValidationError("Expected at least 5 temporal folds.")

    previous_val_end_position = -1
    for fold in folds:
        if fold.shuffled:
            raise DatasetValidationError(f"Fold {fold.fold_id} was marked as shuffled.")
        if fold.train_positions != tuple(sorted(fold.train_positions)):
            raise DatasetValidationError(f"Fold {fold.fold_id} training positions are not sorted.")
        if fold.val_positions != tuple(sorted(fold.val_positions)):
            raise DatasetValidationError(f"Fold {fold.fold_id} validation positions are not sorted.")
        if max(fold.train_positions) >= min(fold.val_positions):
            raise DatasetValidationError(
                f"Fold {fold.fold_id} has a training index at or after validation."
            )
        if max(fold.train_months) >= min(fold.val_months):
            raise DatasetValidationError(
                f"Fold {fold.fold_id} has a training month at or after validation."
            )
        if fold.feature_source_end != max(fold.val_months):
            raise DatasetValidationError(
                f"Fold {fold.fold_id} feature prefix does not end at the last validation month."
            )
        if max(fold.feature_source_months) != fold.feature_source_end:
            raise DatasetValidationError(
                f"Fold {fold.fold_id} feature source includes a month after validation."
            )
        if min(fold.val_positions) <= previous_val_end_position:
            raise DatasetValidationError(
                f"Fold {fold.fold_id} validation starts at or before a previous fold."
            )
        previous_val_end_position = max(fold.val_positions)

    for fold in folds:
        future_val_months = {
            month
            for later_fold in folds
            if later_fold.fold_id > fold.fold_id
            for month in later_fold.val_months
            if month > fold.feature_source_end
        }
        leaked = future_val_months.intersection(fold.feature_source_months)
        if leaked:
            raise DatasetValidationError(
                f"Fold {fold.fold_id} feature prefix includes later-fold months: {sorted(leaked)}"
            )


def materialize_fold_frames(
    raw_train: pd.DataFrame,
    fold: TemporalFoldSplit,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rebuild causal features from only this fold's raw prefix."""
    ordered_raw = _require_training_period(raw_train)
    prefix = ordered_raw.loc[ordered_raw["month"] <= fold.feature_source_end].copy()
    if prefix.empty:
        raise DatasetValidationError(f"Fold {fold.fold_id} has an empty feature prefix.")
    if prefix["month"].max() != fold.feature_source_end:
        raise DatasetValidationError(
            f"Fold {fold.fold_id} prefix end {prefix['month'].max()} != {fold.feature_source_end}"
        )

    ready = drop_feature_warmup(add_causal_features(prefix))
    train_ready = ready.loc[ready["month"].isin(fold.train_months)].copy()
    val_ready = ready.loc[ready["month"].isin(fold.val_months)].copy()
    if len(train_ready) != len(fold.train_months) or len(val_ready) != len(fold.val_months):
        raise DatasetValidationError(
            f"Fold {fold.fold_id} lost rows while rebuilding prefix features."
        )
    _assert_ready_features_use_only_prior_prefix_rows(prefix, train_ready)
    _assert_ready_features_use_only_prior_prefix_rows(prefix, val_ready)
    return train_ready.reset_index(drop=True), val_ready.reset_index(drop=True)


def score_temporal_fold(raw_train: pd.DataFrame, fold: TemporalFoldSplit) -> FoldMetricResult:
    """Fit the existing regressor on one fold and score MAE/RMSE in USD."""
    train_ready, val_ready = materialize_fold_frames(raw_train, fold)
    train_metrics, val_metrics = _fit_and_score(train_ready, val_ready)
    return FoldMetricResult(
        fold_id=fold.fold_id,
        n_train_rows=len(train_ready),
        n_val_rows=len(val_ready),
        train_start=_as_iso_month(train_ready["month"].min()),
        train_end=_as_iso_month(train_ready["month"].max()),
        val_start=_as_iso_month(val_ready["month"].min()),
        val_end=_as_iso_month(val_ready["month"].max()),
        feature_source_end=_as_iso_month(fold.feature_source_end),
        train_mae_usd=train_metrics["mae_usd"],
        train_rmse_usd=train_metrics["rmse_usd"],
        val_mae_usd=val_metrics["mae_usd"],
        val_rmse_usd=val_metrics["rmse_usd"],
    )


def evaluate_temporal_cv(
    raw_train: pd.DataFrame,
    n_splits: int = TEMPORAL_CV_N_SPLITS,
) -> list[FoldMetricResult]:
    """Score every leakage-safe temporal fold in chronological order."""
    return [
        score_temporal_fold(raw_train, fold)
        for fold in build_leakage_safe_temporal_folds(raw_train, n_splits=n_splits)
    ]


def summarize_fold_metric(values: list[float]) -> dict[str, float]:
    """Return sample mean and standard deviation for a fold-level metric."""
    array = np.asarray(values, dtype=float)
    if array.size < 2:
        raise DatasetValidationError("Mean ± standard deviation requires at least two fold scores.")
    return {
        "mean": float(array.mean()),
        "std": float(array.std(ddof=1)),
        "n_folds": float(array.size),
    }


def build_learning_curve_points(
    raw_train: pd.DataFrame,
    min_train_rows: int = LEARNING_CURVE_MIN_TRAIN_ROWS,
    val_months: int = LEARNING_CURVE_VAL_MONTHS,
    step_months: int = LEARNING_CURVE_STEP_MONTHS,
) -> list[LearningCurvePoint]:
    """Score expanding chronological training prefixes against the next year.

    Each point trains on the first N model-ready training months and
    validates on the following `val_months` months, still inside 2016-2023.
    Features are rebuilt from raw months through that point's last
    validation month so later history cannot enter the window.
    """
    ordered_raw = _require_training_period(raw_train)
    ready_months = chronological_model_ready_training_months(ordered_raw)
    n_ready = len(ready_months)
    last_train_end = n_ready - val_months
    if last_train_end < min_train_rows:
        raise DatasetValidationError(
            "Learning curve needs more training history than the validation horizon."
        )

    points: list[LearningCurvePoint] = []
    for train_end in range(min_train_rows, last_train_end + 1, step_months):
        train_month_values = tuple(pd.Timestamp(value) for value in ready_months.iloc[:train_end])
        val_month_values = tuple(
            pd.Timestamp(value) for value in ready_months.iloc[train_end : train_end + val_months]
        )
        feature_source_end = max(val_month_values)
        prefix = ordered_raw.loc[ordered_raw["month"] <= feature_source_end].copy()
        ready = drop_feature_warmup(add_causal_features(prefix))
        train_ready = ready.loc[ready["month"].isin(train_month_values)].copy()
        val_ready = ready.loc[ready["month"].isin(val_month_values)].copy()
        if len(train_ready) != len(train_month_values) or len(val_ready) != len(val_month_values):
            raise DatasetValidationError("Learning-curve window lost rows after prefix rebuild.")
        _assert_ready_features_use_only_prior_prefix_rows(prefix, train_ready)
        _assert_ready_features_use_only_prior_prefix_rows(prefix, val_ready)
        if train_ready["month"].max() >= val_ready["month"].min():
            raise DatasetValidationError("Learning-curve training is not strictly before validation.")

        train_metrics, val_metrics = _fit_and_score(train_ready, val_ready)
        points.append(
            LearningCurvePoint(
                n_train_rows=len(train_ready),
                n_val_rows=len(val_ready),
                train_start=_as_iso_month(train_ready["month"].min()),
                train_end=_as_iso_month(train_ready["month"].max()),
                val_start=_as_iso_month(val_ready["month"].min()),
                val_end=_as_iso_month(val_ready["month"].max()),
                feature_source_end=_as_iso_month(feature_source_end),
                train_mae_usd=train_metrics["mae_usd"],
                train_rmse_usd=train_metrics["rmse_usd"],
                val_mae_usd=val_metrics["mae_usd"],
                val_rmse_usd=val_metrics["rmse_usd"],
            )
        )
    if len(points) < 3:
        raise DatasetValidationError("Learning curve produced too few chronological points.")
    return points


def score_official_train_and_holdout(
    raw_train: pd.DataFrame,
    raw_test: pd.DataFrame,
) -> dict[str, float | int | str]:
    """Score the existing 8-year fit against itself and the 2024-2025 holdout.

    Holdout features may use completed earlier holdout actuals only as lag
    or rolling history, matching the original rolling one-step-ahead
    protocol. The holdout is reported separately from temporal CV.
    """
    train = _require_training_period(raw_train)
    test = raw_test.sort_values("month", kind="mergesort").reset_index(drop=True)
    if test["month"].dt.date.min() < TEST_START_MONTH:
        raise DatasetValidationError("Holdout frame includes months before 2024-01.")

    combined = pd.concat([train, test], ignore_index=True).sort_values("month", kind="mergesort")
    ready = drop_feature_warmup(add_causal_features(combined))
    train_ready = ready.loc[ready["month"].isin(train["month"])].copy()
    test_ready = ready.loc[ready["month"].isin(test["month"])].copy()
    train_metrics, holdout_metrics = _fit_and_score(train_ready, test_ready)
    return {
        "n_train_rows": int(len(train_ready)),
        "n_holdout_rows": int(len(test_ready)),
        "train_start": _as_iso_month(train_ready["month"].min()),
        "train_end": _as_iso_month(train_ready["month"].max()),
        "holdout_start": _as_iso_month(test_ready["month"].min()),
        "holdout_end": _as_iso_month(test_ready["month"].max()),
        "train_mae_usd": train_metrics["mae_usd"],
        "train_rmse_usd": train_metrics["rmse_usd"],
        "holdout_mae_usd": holdout_metrics["mae_usd"],
        "holdout_rmse_usd": holdout_metrics["rmse_usd"],
    }


def _fit_and_score(
    train_ready: pd.DataFrame,
    eval_ready: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, float]]:
    """Fit the existing Random Forest and score both frames in USD."""
    train_features = feature_matrix(train_ready)
    eval_features = feature_matrix(eval_ready)
    train_target = target_vector(train_ready)
    eval_target = target_vector(eval_ready)
    model = build_regressor()
    fit_regressor(model, train_features, train_target)
    train_predicted = np.asarray(model.predict(train_features), dtype=float)
    eval_predicted = np.asarray(model.predict(eval_features), dtype=float)
    return (
        {
            "mae_usd": mean_absolute_error_usd(train_target, train_predicted),
            "rmse_usd": root_mean_squared_error_usd(train_target, train_predicted),
        },
        {
            "mae_usd": mean_absolute_error_usd(eval_target, eval_predicted),
            "rmse_usd": root_mean_squared_error_usd(eval_target, eval_predicted),
        },
    )


def _require_training_period(frame: pd.DataFrame) -> pd.DataFrame:
    """Reject any frame that includes the 2024-2025 holdout."""
    ordered = frame.sort_values("month", kind="mergesort").reset_index(drop=True)
    if ordered.empty:
        raise DatasetValidationError("Training frame is empty.")
    if (ordered["month"].dt.date >= TEST_START_MONTH).any():
        raise DatasetValidationError(
            "Temporal evaluation received 2024-2025 holdout rows. "
            "Cross-validation and the learning curve use 2016-2023 only."
        )
    return ordered


def _assert_ready_features_use_only_prior_prefix_rows(
    prefix: pd.DataFrame,
    ready: pd.DataFrame,
) -> None:
    """Prove each scored row's lags and rolling stats come from earlier prefix months."""
    history = prefix.sort_values("month", kind="mergesort").reset_index(drop=True)
    prefix_months = set(history["month"].tolist())
    for _, row in ready.iterrows():
        if row["month"] not in prefix_months:
            raise DatasetValidationError(
                f"Feature row {row['month']} is outside the raw prefix used to build it."
            )
        prior = history.loc[history["month"] < row["month"]]
        if prior.empty:
            raise DatasetValidationError(f"Row {row['month']} has no earlier prefix history.")
        if row["revenue_lag_1"] != prior.iloc[-1][TARGET_COLUMN]:
            raise DatasetValidationError(f"revenue_lag_1 for {row['month']} is not the prior prefix month.")
        last_three = prior.iloc[-3:][TARGET_COLUMN]
        last_twelve = prior.iloc[-12:][TARGET_COLUMN]
        if not np.isclose(row["revenue_roll_mean_3"], float(last_three.mean())):
            raise DatasetValidationError(f"revenue_roll_mean_3 for {row['month']} used a leaked window.")
        if not np.isclose(row["revenue_roll_mean_12"], float(last_twelve.mean())):
            raise DatasetValidationError(f"revenue_roll_mean_12 for {row['month']} used a leaked window.")
        if not np.isclose(row["revenue_lag_12"], float(last_twelve.iloc[0])):
            raise DatasetValidationError(f"revenue_lag_12 for {row['month']} is not the month 12 steps back.")


def _as_iso_month(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
