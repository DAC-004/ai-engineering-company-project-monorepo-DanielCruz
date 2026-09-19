# Build Plan: HealthCore Sales Forecasting Regression Model

## 1. Objective and scope

Build a reproducible regression pipeline that forecasts HealthCore's monthly consolidated revenue and demonstrates whether the historical data is sufficient for Finance's feasibility question. The implementation must use the provided ten-year dataset, train only on the first eight years, evaluate only on the final two years, and produce an uncertainty-aware visualization alongside business-readable metric explanations.

**In scope**

- Data loading and validation for `data/raw/healthcore_sales.csv`.
- HealthCore-specific time, lag, rolling, and seasonal feature engineering.
- Chronological 2016–2023 training / 2024–2025 test split.
- Scikit-learn Random Forest regression with fixed seed.
- MSE, PSI, Gini, and K2 Score calculated from held-out test data.
- Prediction variability range and actual-vs-predicted chart.
- Automated split/leakage tests and documentation suitable for the PR.

**Out of scope**

- Generating, imputing, or simulating replacement sales data.
- Patient-level data or any clinical identifiers.
- Random shuffling or cross-validation that mixes future observations into training.
- Production dashboard deployment.

## 2. Context-derived data contract

Read and enforce the HealthCore context before coding. The source contains 120 monthly `consolidated` rows from `2016-01-01` through `2025-12-01` with exactly these columns:

- `month`: parse as a datetime and retain month-start semantics.
- `revenue_usd`: positive regression target.
- `visits_count`: monthly visits feature.
- `avg_revenue_per_visit_usd`: monthly value feature.
- `region`: expected to be `consolidated` for the modeling row.

Validate that there are no missing months, no nulls after cleaning, positive revenue, and no unexpected columns/region values. Preserve the source values and document the observed 2–6% alternating annual growth and the July–August trough / October–December peak; do not flatten or overwrite that pattern.

## 3. Planned repository changes

```text
scripts/sales_forecasting.py                 # executable end-to-end pipeline
src/sales_forecasting/                         # importable pipeline components
  __init__.py
  data.py                                      # loading, validation, chronological split
  features.py                                 # causal feature engineering
  model.py                                    # model construction and fit/predict
  metrics.py                                  # MSE, PSI, Gini, K2 Score implementations
  visualization.py                            # uncertainty-band plot
  reporting.py                                # JSON/Markdown result output

tests/pipelines/test_sales_forecasting_split.py  # required 8/2-year/leakage tests
tests/pipelines/test_sales_forecasting_metrics.py # metric/test-set coverage
outputs/sales_forecast_healthcore.png          # generated visualization (ignored if appropriate)
outputs/sales_forecast_healthcore.json         # reproducible metric report
README.md or docs/sales-forecasting.md        # algorithm, metric, and run documentation
pyproject.toml / uv.lock                       # uv-managed dependencies
```

If the repository's existing package layout differs, keep the same responsibilities and adapt paths rather than introducing duplicate implementations.

## 4. Implementation sequence

### Phase 1 — Environment and data validation

1. Start from `main` on a descriptive feature branch such as `feature/healthcore-sales-forecast`.
2. Confirm/create the project environment using `uv`; add dependencies with `uv add` only (at minimum pandas, numpy, scikit-learn, matplotlib, pytest; add xgboost only if the model decision changes).
3. Load only `data/raw/healthcore_sales.csv`; fail with a clear error if it is absent instead of falling back to generated data.
4. Parse and sort by `month`, validate the exact schema, monthly continuity, 120-row count, positive target, and `consolidated` region.
5. Handle null/empty values before training using an explicit validation or documented training-only imputation policy. Do not impute test values from future information.

### Phase 2 — Causal features and chronological split

1. Create calendar features (`year`, month number, month sine/cosine, quarter) to represent recurring seasonality.
2. Create causal lag features (`revenue_lag_1`, `revenue_lag_12`, and visit/revenue-per-visit lags where useful) and rolling statistics using `shift(1)` before rolling, so the current target and future rows can never leak into a feature.
3. Encode the known HealthCore pattern in documentation/comments: annual growth and summer/flu-season effects are modeled through calendar and lag features, not by changing source values.
4. Split by explicit date boundaries: training `2016-01` through `2023-12` (96 rows) and test `2024-01` through `2025-12` (24 rows). Assert exact boundaries, row counts, disjoint dates, and that `.fit()` receives training rows only.
5. Drop rows made unusable by lag construction consistently and document how the split-count assertions account for them; never backfill from future rows.
6. Scale only features for which scaling is appropriate. Keep the scaler in a pipeline fit on training data only, and transform test data with that already-fitted scaler.

### Phase 3 — Model training decision

Use `RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1, min_samples_leaf=2)` (or a similarly documented fixed configuration). The rationale must be written in code comments and project documentation:

- The dataset is small (120 monthly observations), so a tree ensemble is practical without extensive tuning.
- Random Forest captures nonlinear interactions among calendar, visits, and lag features without requiring strong linear assumptions.
- It is easier for Finance and leadership to explain than sequential boosting, and feature importance gives an interpretable supporting signal.
- The available project time favors a stable, reproducible baseline over extensive XGBoost tuning; this is a stakeholder-driven choice, not an unsupported claim that it is universally more accurate.

Fit once on training features/target only. Persist the model/scaler or expose a callable pipeline so tests can inspect the fit inputs.

### Phase 4 — Held-out evaluation and metric definitions

Generate predictions for the test set only and compute all four required metrics from held-out test observations. Report raw values and sufficient denominators/definitions for reproduction:

- **MSE:** mean squared error of `y_test` and `y_pred`; also report RMSE and MSE relative to average monthly test revenue for Finance.
- **PSI:** population stability index comparing the training reference distribution to the corresponding test distribution for selected numeric predictors (and report the aggregation rule). Use fixed training-derived bins, epsilon protection for zero proportions, and never use test values to define bins.
- **Gini:** regression-compatible normalized discrimination score derived from test actual/predicted ordering (document the exact formula, such as `2 * AUC - 1` after ranking/threshold definition, or a clearly justified concordance formulation). Do not present a classification Gini without explaining the adaptation.
- **K2 Score:** implement and document the selected regression K2 formula and its inputs; calculate it on `y_test`/`y_pred` only. If the project has an existing K2 convention, reuse it; otherwise state the convention prominently so the metric is auditable.

Add assertions or tests that each metric function receives test arrays/data, not training arrays. Explain why low MSE alone is insufficient: it can hide seasonal bias, distribution shift, ranking failures, or unstable performance on peak/trough months.

### Phase 5 — Visualization and reporting

1. Plot the 24 test months with actual revenue, point predictions, and a visible variability band (for example, per-tree prediction quantiles from the fitted forest, such as 10th–90th percentile).
2. Ensure the band is derived from model variability or a documented residual/bootstrap method, not an arbitrary fixed percentage.
3. Label the chart with HealthCore, USD units, train/test boundary, and the July–August / October–December seasonal context where useful.
4. Write a machine-readable metric report and a concise Markdown summary containing the algorithm rationale, data boundaries, metric definitions/results, limitations, and the visualization path.

### Phase 6 — Tests and quality gates

Required tests under `tests/pipelines/`:

- Exact 8-year / 2-year date and row-count split.
- No overlap between train and test dates and no test date in training features.
- Model fit receives no test-year data.
- Causal lag/rolling features do not use current/future target values.
- Schema/null/continuity validation for the provided HealthCore CSV.
- All four metric functions execute and are wired to held-out test arrays.
- Visualization includes actuals, predictions, and a nonzero variability interval.

Run the focused tests, then the full test suite, and record the commands/results in the PR notes. Use deterministic seeds throughout.

## 5. Acceptance checklist mapped to the rubric

- **Data integrity (1.1–1.5):** source path, unchanged provided CSV, exact context schema, HealthCore seasonality/growth references, and no destructive transformations are evidenced in code/tests.
- **Preparation (2.1–2.2):** null handling and training-fitted scaling are explicit.
- **Split (3.1–3.6):** date boundaries, leakage assertions, and passing tests prove the exact 8/2 rule.
- **Model (4.1–4.4):** scikit-learn Random Forest, stakeholder-specific rationale, and `random_state=42` are documented.
- **Metrics (5.1–5.7):** MSE, PSI, Gini, and K2 use test data; definitions and the MSE limitation are documented.
- **Visualization (6.1–6.3):** actuals, predictions, and a model-derived uncertainty band cover both test years.
- **Submission/tooling (7.1–7.5, 8.1–8.2):** descriptive commits, fork/main PR workflow, metric results in PR description, uv-managed dependencies, and a branch created from `main` are completed before submission.

## 6. Risks and mitigations

- **Ambiguous Gini/K2 definitions:** choose, implement, and document formulas before reporting results; add unit tests with known toy inputs.
- **Small time series:** avoid claiming production readiness; report seasonal and peak/trough limitations and use the two-year holdout honestly.
- **Lag feature availability:** use only historical rows and explicit missing-feature handling; never leak test targets through imputation or rolling windows.
- **PSI interpretation:** the dataset is consolidated, so do not invent a US/UK mix. Report PSI for available predictor distributions and note this limitation.
- **Reproducibility:** pin dependencies through `uv.lock`, fix all seeds, preserve source data, and save the exact metric/report configuration.

## 7. Definition of done

The work is complete only when the pipeline runs from the repository root using the documented `uv run` command, all focused and full tests pass, the generated chart visibly contains an uncertainty range over actual 2024–2025 values, all rubric-critical evidence is present, and the PR description includes the chosen algorithm, rationale, and held-out metric results.
