# `data/eval` folder

This folder is for **evaluation and validation**: evaluation datasets, golden sets, experiment results, metrics, and artifacts used to measure quality for models, RAG, agents, or pipelines.

- **Main purpose**: centralize evaluation inputs and outputs so improvements stay measurable across project milestones.
- **Recommendation**: document each evaluation set (what it measures, how it was built, success criteria) and avoid sensitive data; use synthetic or anonymized data when needed.

## Sales forecast artifacts

- `sales_forecast_actual_vs_predicted.png` — 2024-2025 actuals, rolling one-step-ahead predictions, and the empirical residual variability range
- `sales_forecast_metrics.md` / `sales_forecast_metrics.json` — test-set MSE, Gini, K2, and train-versus-test PSI

The shaded band is an empirical residual range from training-only expanding-window residuals. It is not a formal confidence or prediction interval.

> _Spanish version: [README.es.md](./README.es.md)._
