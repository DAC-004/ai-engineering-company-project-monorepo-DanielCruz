#!/usr/bin/env python3
"""Formally evaluate the existing HealthCore monthly revenue forecast.

This script does not replace or retune the Random Forest. It scores the
already-specified model with leakage-safe temporal cross-validation and a
chronological learning curve, then writes MAE/RMSE artifacts for the
technical report.

Usage (from repository root):
    uv run python scripts/evaluate_sales_forecast.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.sales_forecast.constants import (  # noqa: E402
    RANDOM_STATE,
    TARGET_COLUMN,
    TEMPORAL_CV_N_SPLITS,
)
from shared.sales_forecast.evaluation import (  # noqa: E402
    build_learning_curve_points,
    evaluate_temporal_cv,
    score_official_train_and_holdout,
    summarize_fold_metric,
)
from shared.sales_forecast.load import load_and_validate_sales_csv  # noqa: E402
from shared.sales_forecast.split import chronological_raw_split  # noqa: E402
from shared.sales_forecast.visualize import plot_learning_curve  # noqa: E402

DEFAULT_DATA_PATH = REPO_ROOT / "data" / "raw" / "healthcore_sales.csv"
DEFAULT_CURVE_PATH = REPO_ROOT / "data" / "eval" / "learning_curve.png"
DEFAULT_METRICS_JSON = REPO_ROOT / "data" / "eval" / "evaluation_metrics.json"


def run_evaluation(
    data_path: Path = DEFAULT_DATA_PATH,
    curve_path: Path = DEFAULT_CURVE_PATH,
    metrics_json_path: Path = DEFAULT_METRICS_JSON,
) -> dict:
    """Run temporal CV and the learning curve, then persist numeric artifacts."""
    sales = load_and_validate_sales_csv(data_path)
    raw_train, raw_test = chronological_raw_split(sales)
    fold_results = evaluate_temporal_cv(raw_train, n_splits=TEMPORAL_CV_N_SPLITS)
    curve_points = build_learning_curve_points(raw_train)
    official = score_official_train_and_holdout(raw_train, raw_test)
    plot_learning_curve(curve_points, curve_path)

    val_mae = summarize_fold_metric([fold.val_mae_usd for fold in fold_results])
    val_rmse = summarize_fold_metric([fold.val_rmse_usd for fold in fold_results])
    train_mae = summarize_fold_metric([fold.train_mae_usd for fold in fold_results])
    train_rmse = summarize_fold_metric([fold.train_rmse_usd for fold in fold_results])
    average_monthly_revenue = float(sales[TARGET_COLUMN].mean())

    report = {
        "algorithm": "RandomForestRegressor",
        "random_state": RANDOM_STATE,
        "primary_metric": "MAE",
        "primary_metric_units": "USD",
        "evaluation_scope": (
            "Temporal cross-validation and the learning curve use the 2016-2023 "
            "training period only. The 2024-2025 holdout is scored separately "
            "with the original rolling one-step-ahead protocol."
        ),
        "dataset": {
            "path": str(data_path.as_posix()),
            "raw_rows": int(len(sales)),
            "raw_train_rows": int(len(raw_train)),
            "raw_test_rows": int(len(raw_test)),
            "average_monthly_revenue_usd": average_monthly_revenue,
        },
        "temporal_cv": {
            "method": "TimeSeriesSplit",
            "n_splits": TEMPORAL_CV_N_SPLITS,
            "shuffled": False,
            "feature_rule": (
                "Each fold rebuilds causal lags and rolling statistics from raw "
                "training months through that fold's last validation month."
            ),
            "folds": [
                {
                    "fold_id": fold.fold_id,
                    "n_train_rows": fold.n_train_rows,
                    "n_val_rows": fold.n_val_rows,
                    "train_start": fold.train_start,
                    "train_end": fold.train_end,
                    "val_start": fold.val_start,
                    "val_end": fold.val_end,
                    "feature_source_end": fold.feature_source_end,
                    "train_mae_usd": fold.train_mae_usd,
                    "train_rmse_usd": fold.train_rmse_usd,
                    "val_mae_usd": fold.val_mae_usd,
                    "val_rmse_usd": fold.val_rmse_usd,
                }
                for fold in fold_results
            ],
            "val_mae_usd": val_mae,
            "val_rmse_usd": val_rmse,
            "train_mae_usd": train_mae,
            "train_rmse_usd": train_rmse,
            "selected_metric": {
                "name": "MAE",
                "mean_usd": val_mae["mean"],
                "std_usd": val_mae["std"],
                "mean_plus_minus_std": f"{val_mae['mean']:.2f} ± {val_mae['std']:.2f} USD",
            },
        },
        "official_8_2_split": official,
        "learning_curve": {
            "image": str(curve_path.as_posix()),
            "points": [
                {
                    "n_train_rows": point.n_train_rows,
                    "n_val_rows": point.n_val_rows,
                    "train_start": point.train_start,
                    "train_end": point.train_end,
                    "val_start": point.val_start,
                    "val_end": point.val_end,
                    "feature_source_end": point.feature_source_end,
                    "train_mae_usd": point.train_mae_usd,
                    "train_rmse_usd": point.train_rmse_usd,
                    "val_mae_usd": point.val_mae_usd,
                    "val_rmse_usd": point.val_rmse_usd,
                }
                for point in curve_points
            ],
        },
        "artifacts": {
            "learning_curve": str(curve_path.as_posix()),
            "metrics_json": str(metrics_json_path.as_posix()),
        },
    }
    metrics_json_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    try:
        report = run_evaluation()
    except Exception as exc:  # noqa: BLE001 — CLI must surface domain errors cleanly
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    cv = report["temporal_cv"]
    official = report["official_8_2_split"]
    print("HealthCore sales forecast evaluation")
    print(f"Temporal CV: {cv['method']} with {cv['n_splits']} folds, shuffled={cv['shuffled']}")
    print(f"Selected metric MAE: {cv['selected_metric']['mean_plus_minus_std']}")
    print(
        "Official 8/2-year split: "
        f"train MAE {official['train_mae_usd']:.2f} USD, "
        f"train RMSE {official['train_rmse_usd']:.2f} USD, "
        f"holdout MAE {official['holdout_mae_usd']:.2f} USD, "
        f"holdout RMSE {official['holdout_rmse_usd']:.2f} USD"
    )
    print(f"Learning curve: {report['artifacts']['learning_curve']}")
    print(f"Metrics: {report['artifacts']['metrics_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
