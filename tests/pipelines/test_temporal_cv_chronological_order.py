"""Prove temporal CV keeps chronological order and fold-boundary features safe."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

from shared.sales_forecast.constants import TARGET_COLUMN, TEMPORAL_CV_N_SPLITS, TEST_START_MONTH
from shared.sales_forecast.evaluation import (
    assert_temporal_folds_are_chronological,
    build_leakage_safe_temporal_folds,
    chronological_model_ready_training_months,
    iter_leakage_safe_temporal_folds,
    materialize_fold_frames,
)
from shared.sales_forecast.load import load_and_validate_sales_csv
from shared.sales_forecast.split import chronological_raw_split

REPO_ROOT = Path(__file__).resolve().parents[2]
SALES_CSV = REPO_ROOT / "data" / "raw" / "healthcore_sales.csv"


@pytest.fixture(scope="module")
def raw_train() -> pd.DataFrame:
    sales = load_and_validate_sales_csv(SALES_CSV)
    train, _test = chronological_raw_split(sales)
    return train


def test_temporal_cv_uses_at_least_five_unshuffled_timeseries_splits(
    raw_train: pd.DataFrame,
) -> None:
    folds = build_leakage_safe_temporal_folds(raw_train)
    assert len(folds) >= 5
    assert len(folds) == TEMPORAL_CV_N_SPLITS
    assert all(fold.splitter_name == TimeSeriesSplit.__name__ for fold in folds)
    assert all(fold.shuffled is False for fold in folds)
    assert_temporal_folds_are_chronological(folds)


def test_each_fold_trains_only_on_earlier_months(raw_train: pd.DataFrame) -> None:
    for fold in iter_leakage_safe_temporal_folds(raw_train):
        assert fold.train_positions == tuple(sorted(fold.train_positions))
        assert fold.val_positions == tuple(sorted(fold.val_positions))
        assert max(fold.train_positions) < min(fold.val_positions)
        assert max(fold.train_months) < min(fold.val_months)
        assert list(fold.train_months) == sorted(fold.train_months)
        assert list(fold.val_months) == sorted(fold.val_months)


def test_no_later_fold_index_appears_in_an_earlier_training_portion(
    raw_train: pd.DataFrame,
) -> None:
    folds = build_leakage_safe_temporal_folds(raw_train)
    for earlier in folds:
        later_val_positions = {
            position
            for later in folds
            if later.fold_id > earlier.fold_id
            for position in later.val_positions
        }
        leaked_positions = later_val_positions.intersection(earlier.train_positions)
        assert not leaked_positions
        assert min(earlier.val_positions) > max(earlier.train_positions)


def test_fold_construction_does_not_shuffle_the_series(raw_train: pd.DataFrame) -> None:
    ready_months = chronological_model_ready_training_months(raw_train)
    folds = build_leakage_safe_temporal_folds(raw_train)
    all_val_positions = [position for fold in folds for position in fold.val_positions]
    assert all_val_positions == sorted(all_val_positions)
    assert all_val_positions == list(range(min(all_val_positions), max(all_val_positions) + 1))
    reconstructed_val_months = [month for fold in folds for month in fold.val_months]
    assert reconstructed_val_months == sorted(reconstructed_val_months)
    assert list(ready_months) == sorted(ready_months)
    assert raw_train["month"].is_monotonic_increasing


def test_later_fold_months_do_not_enter_earlier_feature_windows(
    raw_train: pd.DataFrame,
) -> None:
    folds = build_leakage_safe_temporal_folds(raw_train)
    for fold in folds:
        later_val_months = {
            month
            for later in folds
            if later.fold_id > fold.fold_id
            for month in later.val_months
            if month > fold.feature_source_end
        }
        assert later_val_months.isdisjoint(fold.feature_source_months)
        assert fold.feature_source_end == max(fold.val_months)
        assert max(fold.feature_source_months) == fold.feature_source_end
        assert fold.feature_source_end < pd.Timestamp(TEST_START_MONTH)


def test_validation_features_use_only_information_available_at_prediction_time(
    raw_train: pd.DataFrame,
) -> None:
    folds = build_leakage_safe_temporal_folds(raw_train)
    history = raw_train.sort_values("month", kind="mergesort").reset_index(drop=True)
    for fold in folds:
        _train_ready, val_ready = materialize_fold_frames(raw_train, fold)
        prefix = history.loc[history["month"] <= fold.feature_source_end]
        later = history.loc[history["month"] > fold.feature_source_end]
        assert later.empty or later["month"].min() > fold.feature_source_end
        for _, row in val_ready.iterrows():
            prior = prefix.loc[prefix["month"] < row["month"]]
            assert not prior.empty
            assert row["revenue_lag_1"] == pytest.approx(float(prior.iloc[-1][TARGET_COLUMN]))
            assert row["revenue_lag_12"] == pytest.approx(float(prior.iloc[-12][TARGET_COLUMN]))
            assert row["revenue_roll_mean_3"] == pytest.approx(
                float(prior.iloc[-3:][TARGET_COLUMN].mean())
            )
            assert row[TARGET_COLUMN] != pytest.approx(float(row["revenue_lag_1"]))
