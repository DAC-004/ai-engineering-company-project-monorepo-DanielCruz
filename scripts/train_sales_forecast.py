#!/usr/bin/env python3
"""Train and evaluate the HealthCore monthly revenue forecast.

Algorithm choice: Random Forest (scikit-learn).
- Data size: 96 raw training months, fewer after lag-12 warmup.
- Explainability: Sandra (CEO) and Tom (Revenue Cycle) need a readable
  error story, not sequential boosting.
- Tuning budget: limited; averaged trees are the assignment starting point.
- Scaling: none. Tree splits are invariant to feature magnitude, so a
  scaler would be a meaningless transformation.

Evaluation protocol: rolling one-step-ahead historical evaluation.
Each test month may use information available before that month, including
actuals from completed earlier test months as lagged inputs. This is not a
single 24-month-ahead forecast made at the end of 2023.

Usage (from repository root):
    uv run python scripts/train_sales_forecast.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.sales_forecast.constants import (  # noqa: E402
    FEATURE_COLUMNS,
    PSI_COLUMN,
    RANDOM_STATE,
    TARGET_COLUMN,
)
from shared.sales_forecast.features import (  # noqa: E402
    add_causal_features,
    drop_feature_warmup,
    feature_matrix,
    target_vector,
)
from shared.sales_forecast.load import load_and_validate_sales_csv  # noqa: E402
from shared.sales_forecast.metrics import (  # noqa: E402
    dagostino_pearson_k2,
    mean_squared_error_usd2,
    normalized_gini,
    population_stability_index,
    rmse_pct_of_average_monthly_revenue,
)
from shared.sales_forecast.model import build_regressor, fit_regressor  # noqa: E402
from shared.sales_forecast.split import chronological_raw_split, model_ready_split  # noqa: E402
from shared.sales_forecast.variability import estimate_expanding_window_variability  # noqa: E402
from shared.sales_forecast.visualize import plot_actual_vs_predicted  # noqa: E402

DEFAULT_DATA_PATH = REPO_ROOT / "data" / "raw" / "healthcore_sales.csv"
DEFAULT_PLOT_PATH = REPO_ROOT / "data" / "eval" / "sales_forecast_actual_vs_predicted.png"
DEFAULT_METRICS_JSON = REPO_ROOT / "data" / "eval" / "sales_forecast_metrics.json"
DEFAULT_METRICS_MD = REPO_ROOT / "data" / "eval" / "sales_forecast_metrics.md"


def _set_global_seeds(seed: int = RANDOM_STATE) -> None:
    random.seed(seed)
    np.random.seed(seed)


def run_training(
    data_path: Path = DEFAULT_DATA_PATH,
    plot_path: Path = DEFAULT_PLOT_PATH,
    metrics_json_path: Path = DEFAULT_METRICS_JSON,
    metrics_md_path: Path = DEFAULT_METRICS_MD,
) -> dict:
    """Validate, train, evaluate, and write forecast artifacts."""
    _set_global_seeds()
    sales = load_and_validate_sales_csv(data_path)
    raw_train, raw_test = chronological_raw_split(sales)
    featured = add_causal_features(sales)
    model_ready = drop_feature_warmup(featured)
    model_train, model_test = model_ready_split(model_ready)

    train_features = feature_matrix(model_train)
    train_target = target_vector(model_train)
    test_features = feature_matrix(model_test)
    test_target = target_vector(model_test)

    model = build_regressor()
    fit_regressor(model, train_features, train_target)
    predictions = np.asarray(model.predict(test_features), dtype=float)
    test_residuals = test_target.to_numpy(dtype=float) - predictions

    variability = estimate_expanding_window_variability(model_train)
    average_monthly_revenue = float(sales[TARGET_COLUMN].mean())
    mse = mean_squared_error_usd2(test_target, predictions)
    rmse_pct = rmse_pct_of_average_monthly_revenue(
        test_target, predictions, average_monthly_revenue
    )
    gini = normalized_gini(test_target, predictions)
    psi = population_stability_index(raw_train[PSI_COLUMN], raw_test[PSI_COLUMN])
    k2 = dagostino_pearson_k2(test_residuals)

    importances = {
        name: float(value)
        for name, value in zip(FEATURE_COLUMNS, model.feature_importances_, strict=True)
    }
    plot_actual_vs_predicted(model_test, predictions, variability, plot_path)

    report = {
        "algorithm": "RandomForestRegressor",
        "algorithm_justification": (
            "Small monthly sample, stakeholder need for explainability, and "
            "limited tuning time. Random Forest averages independent trees and "
            "is the assignment starting point; XGBoost was not selected."
        ),
        "scaling": (
            "No feature scaling. Random Forest split selection does not depend "
            "on comparable feature magnitudes."
        ),
        "random_state": RANDOM_STATE,
        "evaluation_protocol": (
            "Rolling one-step-ahead historical evaluation on 2024-2025. "
            "Each test month uses information available before that month. "
            "Actuals from completed earlier test months may appear only as "
            "lagged or rolling inputs to a later test month. This is not a "
            "single 24-month-ahead forecast made at the end of 2023."
        ),
        "dataset": {
            "path": str(data_path.as_posix()),
            "raw_rows": int(len(sales)),
            "raw_train_rows": int(len(raw_train)),
            "raw_test_rows": int(len(raw_test)),
            "raw_train_start": raw_train["month"].min().strftime("%Y-%m-%d"),
            "raw_train_end": raw_train["month"].max().strftime("%Y-%m-%d"),
            "raw_test_start": raw_test["month"].min().strftime("%Y-%m-%d"),
            "raw_test_end": raw_test["month"].max().strftime("%Y-%m-%d"),
            "model_ready_train_rows": int(len(model_train)),
            "model_ready_test_rows": int(len(model_test)),
            "model_ready_train_start": model_train["month"].min().strftime("%Y-%m-%d"),
            "model_ready_train_end": model_train["month"].max().strftime("%Y-%m-%d"),
            "model_ready_test_start": model_test["month"].min().strftime("%Y-%m-%d"),
            "model_ready_test_end": model_test["month"].max().strftime("%Y-%m-%d"),
            "average_monthly_revenue_usd": average_monthly_revenue,
        },
        "features": {
            "columns": list(FEATURE_COLUMNS),
            "causal_rule": (
                "Lags and rolling statistics use only earlier months. "
                "Same-month visits_count and avg_revenue_per_visit_usd are excluded."
            ),
            "importances": importances,
        },
        "variability": {
            "label": "empirical residual variability range, not a confidence or prediction interval",
            "method": variability.method,
            "residual_std_usd": variability.residual_std,
            "half_width_usd": variability.half_width,
            "n_residuals": variability.n_residuals,
            "first_validation_month": variability.first_validation_month,
            "last_validation_month": variability.last_validation_month,
            "min_train_rows": variability.min_train_rows,
            "test_targets_used": False,
        },
        "metrics": {
            "evaluation_note": (
                "MSE, normalized Gini, and D'Agostino-Pearson K2 use held-out "
                "test predictions and targets. PSI compares training versus "
                "test visits_count populations and is not a test-only accuracy metric."
            ),
            "mse_usd2": mse,
            "rmse_pct_of_average_monthly_revenue": rmse_pct,
            "rmse_pct_note": (
                "This percentage is RMSE / average monthly revenue * 100. "
                "It is not MSE. MSE remains in USD squared."
            ),
            "normalized_gini": gini,
            "psi": psi,
            "k2": k2,
        },
        "artifacts": {
            "plot": str(plot_path.as_posix()),
            "metrics_json": str(metrics_json_path.as_posix()),
            "metrics_md": str(metrics_md_path.as_posix()),
        },
    }
    _write_metric_files(report, metrics_json_path, metrics_md_path)
    return report


def _write_metric_files(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    metrics = report["metrics"]
    variability = report["variability"]
    dataset = report["dataset"]
    k2 = metrics["k2"]
    psi = metrics["psi"]
    markdown = f"""# HealthCore sales forecast metrics

## Evaluation protocol

{report["evaluation_protocol"]}

## Split

- Raw train: {dataset["raw_train_rows"]} rows, {dataset["raw_train_start"]} through {dataset["raw_train_end"]}
- Raw test: {dataset["raw_test_rows"]} rows, {dataset["raw_test_start"]} through {dataset["raw_test_end"]}
- Model-ready train: {dataset["model_ready_train_rows"]} rows, {dataset["model_ready_train_start"]} through {dataset["model_ready_train_end"]}
- Model-ready test: {dataset["model_ready_test_rows"]} rows, {dataset["model_ready_test_start"]} through {dataset["model_ready_test_end"]}

## Test-set metrics

- **MSE:** {metrics["mse_usd2"]:.6f} USD²
- **RMSE as percent of average monthly revenue:** {metrics["rmse_pct_of_average_monthly_revenue"]:.4f}% ({metrics["rmse_pct_note"]})
- **Normalized ranking Gini:** {metrics["normalized_gini"]:.6f}

### PSI (train versus test population shift)

- **Value:** {psi["value"]:.6f}
- **Input:** `{PSI_COLUMN}` only
- **Assigned:** {psi["train_assigned"]} of {psi["train_n"]} train rows and {psi["test_assigned"]} of {psi["test_n"]} test rows
- **Pre-epsilon shares:** train {psi["train_share_sum_before_epsilon"]:.6f}, test {psi["test_share_sum_before_epsilon"]:.6f}
- **Empty test bins / test values above train max:** {psi["n_zero_test_bins"]} / {psi["n_test_above_train_max"]}
- **Formula:** {psi["formula"]}
- **Binning:** {psi["binning"]}
- **Zero protection:** {psi["zero_protection"]}
- **Interpretation:** {psi["interpretation"]}
- **Population:** {psi["population"]}
- **Not measured:** {psi["not_measured"]}

### K2 Score (assignment name, undefined formula)

- **Label:** {k2["label"]}
- **Statistic:** {k2["statistic"]:.6f}
- **p-value:** {k2["p_value"]:.6g}
- **Test residuals used:** {k2["n_residuals"]}
- **Meaning:** evaluates whether the test residual distribution significantly departs from normality. This is not a forecast-accuracy metric and is not R² or Kolmogorov-Smirnov.

## Variability range

- **Label:** {variability["label"]}
- **Method:** {variability["method"]}
- **Training-only out-of-sample residuals:** {variability["n_residuals"]}
- **Residual std:** {variability["residual_std_usd"]:.2f} USD
- **Half-width (±1.96 σ):** {variability["half_width_usd"]:.2f} USD
- **Validation months:** {variability["first_validation_month"]} through {variability["last_validation_month"]}

## Why low MSE alone is not enough

MSE reports squared dollar error but does not show whether the model ranks seasonal months correctly (Gini), whether consolidated visit volume shifted between train and test (PSI), or whether test residuals depart from normality (K2). Finance also cannot read USD² as a percentage without a separately labeled RMSE translation.
"""
    markdown_path.write_text(markdown, encoding="utf-8")


def main() -> int:
    try:
        report = run_training()
    except Exception as exc:  # noqa: BLE001 — CLI must surface domain errors cleanly
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    metrics = report["metrics"]
    print("HealthCore sales forecast")
    print(f"Algorithm: {report['algorithm']}")
    print(f"Evaluation: {report['evaluation_protocol']}")
    print(
        f"Raw split: {report['dataset']['raw_train_rows']} train / "
        f"{report['dataset']['raw_test_rows']} test"
    )
    print(
        f"Model-ready split: {report['dataset']['model_ready_train_rows']} train / "
        f"{report['dataset']['model_ready_test_rows']} test"
    )
    print(f"MSE (USD^2): {metrics['mse_usd2']:.6f}")
    print(
        f"RMSE % of average monthly revenue: "
        f"{metrics['rmse_pct_of_average_monthly_revenue']:.4f}"
    )
    print(f"Normalized Gini: {metrics['normalized_gini']:.6f}")
    print(f"PSI (visits_count train vs test): {metrics['psi']['value']:.6f}")
    print(
        f"D'Agostino-Pearson K2: {metrics['k2']['statistic']:.6f} "
        f"(p={metrics['k2']['p_value']:.6g})"
    )
    print(
        f"Variability residuals: {report['variability']['n_residuals']} "
        f"training-only out-of-sample"
    )
    print(f"Plot: {report['artifacts']['plot']}")
    print(f"Metrics: {report['artifacts']['metrics_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
