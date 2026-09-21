# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

## Incident analysis (HealthCore)

```bash
# From repository root (or from scripts/ with a relative CSV path):
python scripts/analyze.py scripts/incidents-healthcore.csv
```

- `analyze.py` — CLI entrypoint (shared logic in `shared/incident_analyzer/`)
- `incidents-healthcore.csv` — HealthCore 100-row assignment dataset (company equivalent of `incidents-COMPANY.csv`)

The authoritative local copy of the instructor dataset and CONTEXT live under `.project_specs/` (gitignored). Keep `scripts/incidents-healthcore.csv` identical to that official file for runnable submission layout. Never print or export `patient_id` values.

## Sales forecasting (HealthCore)

```bash
# From repository root:
uv run python scripts/train_sales_forecast.py
uv run pytest tests/pipelines -q
```

- `train_sales_forecast.py` — validates `data/raw/healthcore_sales.csv`, trains Random Forest, writes test-set metrics and the actual-versus-predicted plot
- Shared logic: `shared/sales_forecast/`

### Algorithm

Random Forest is used instead of XGBoost because the monthly sample is small, Sandra and Tom need an explainable error story, and the tuning budget is limited. Averaged trees are the assignment starting point.

No feature scaling is applied. Tree split selection does not depend on comparable feature magnitudes.

### Evaluation protocol

This is a **rolling one-step-ahead historical evaluation** of 2024-2025. Each test month may use information that would have been available before that month, including actuals from completed earlier test months as lagged or rolling inputs. It is **not** a single 24-month-ahead forecast made at the end of 2023.

### Metrics

- **MSE** is calculated on held-out test predictions and targets, in USD².
- **RMSE as a percent of average monthly revenue** is a separately labeled translation. It is not MSE. USD² cannot be divided by USD.
- **Normalized ranking Gini** uses test actuals versus test predictions. It is not classification impurity.
- **PSI** compares training-period `visits_count` with test-period `visits_count`. Bin edges come from train only. This is a train-versus-test population-shift metric for consolidated monthly visit volume. It does **not** measure US versus UK visit mix; the file contains only consolidated rows and no regional records were fabricated.
- **K2 Score** is the assignment name. No formula was provided. The implementation is the **D'Agostino-Pearson K2 residual-normality statistic** on test residuals, reported with its p-value. It is not a forecast-accuracy metric and is not R² or Kolmogorov-Smirnov.

Low MSE alone is not enough: it ignores ranking quality, visit-volume shift, residual shape, and is not a finance-readable unit.

### Variability range

The shaded band is an **empirical residual variability range**, not a formal confidence interval or prediction interval. Residual scale is estimated with a chronological expanding-window walk-forward inside the training period only. Test-period targets are not used. In-sample training residuals are not used.

> _Spanish version: [README.es.md](./README.es.md)._
