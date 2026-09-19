# HealthCore sales forecasting

The pipeline uses the provided `data/raw/healthcore_sales.csv` unchanged. It validates 120 monthly consolidated rows from 2016-01 through 2025-12, with HealthCore's alternating 2–6% annual growth, July–August trough, and October–December peak preserved.

## Split and leakage controls

2016-01 through 2023-12 (96 rows) are training data; 2024-01 through 2025-12 (24 rows) are held out. Features are computed chronologically with `shift(1)` before rolling. Historical warm-up rows are used only to make causal lag features available; no target from the current or future month enters a feature. The model is fitted only on pre-2024 rows.

## Model

`RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42)` was selected because the dataset is small, nonlinear calendar/visit interactions are plausible, and Finance benefits from a familiar, explainable ensemble. The fixed seed improves reproducibility; the choice is not a claim of universal superiority.

## Metrics and fixed formulas

- **MSE:** mean squared error between test revenue and test predictions, in USD².
- **PSI:** training-reference versus test-monitored distribution shift for revenue, using 10 training-derived quantile bins and epsilon `1e-6`: `sum((q-p)*ln(q/p))`. It is a stability diagnostic, not accuracy.
- **Regression Gini:** `1 - MAE(model) / MAE(median-baseline)` on the test set. Higher is better; it can be negative when the model is worse than baseline.
- **K2 Score:** squared Pearson correlation, `corr(y_test, prediction)^2`, on the test set. It measures association, not calibration.

A low MSE alone is insufficient because it can conceal seasonal bias, distribution shift, poor ranking/association, or unacceptable errors during summer troughs and flu-season peaks.

## Run

From the repository root, use `uv run python scripts/sales_forecasting.py`. Outputs are `outputs/sales_forecast_healthcore.json` and `outputs/sales_forecast_healthcore.png`. The chart contains actual revenue, point predictions, and the 10th–90th percentile range across individual forest trees.
