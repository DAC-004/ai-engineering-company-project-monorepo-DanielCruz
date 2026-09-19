# Complete Pre-Submission Audit Report

**Project:** HealthCore Sales Forecasting with a Regression Model  
**Repository:** `DAC-004/ai-engineering-company-project-monorepo-DanielCruz`  
**Audit date:** 2026-09-18  
**Audited against:** `.project_specs/project_rubric.md`, `.project_specs/project_specs.md`, `.project_specs/CONTEXT-healthcore.en.md`

## Executive Summary

**Overall status: CONDITIONAL PASS — pull request creation is pending.**

The forecasting implementation satisfies the critical technical requirements: the provided HealthCore dataset is used, the chronological 8-year/2-year split is enforced, the model is a reproducible scikit-learn Random Forest, all four required metrics are computed on held-out data, and the visualization includes actuals, predictions, and a variability band.

Repository preparation is complete: dependencies were added with `uv`, `uv.lock` was generated, a descriptive feature branch was created, changes were committed, and the branch was pushed to the student's fork. The only remaining submission action is opening the pull request against `main` and confirming its description contains the algorithm rationale and held-out metrics.

## Implementation Evidence

| Area | Evidence |
|---|---|
| Source dataset | `data/raw/healthcore_sales.csv` |
| Context | `.project_specs/CONTEXT-healthcore.en.md` |
| Pipeline | `src/sales_forecasting/pipeline.py` |
| Runner | `scripts/sales_forecasting.py` |
| Tests | `tests/pipelines/test_sales_forecasting.py` |
| Documentation | `docs/sales-forecasting.md` |
| Dependencies | `pyproject.toml`, `uv.lock` |
| Visualization | `outputs/sales_forecast_healthcore.png` |
| Metric report | `outputs/sales_forecast_healthcore.json` |

## Validation Results

### Test suite

Command:

```text
uv run pytest tests/pipelines/test_sales_forecasting.py -q
```

Result:

```text
3 passed
```

### Generated held-out metrics

The model was trained on 2016–2023 and evaluated on 2024–2025:

```json
{
  "mse": 26769688048.831696,
  "psi": 7.841622521445575,
  "gini": 0.532473414367855,
  "k2_score": 0.85372691401095
}
```

Metrics are generated in `outputs/sales_forecast_healthcore.json`.

## Detailed Rubric Audit

### 1. Data Source and Integrity — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 1.1 Correct dataset path | **PASS** | The pipeline loads `data/raw/healthcore_sales.csv`. |
| 1.2 Provided dataset, not generated | **PASS** | The supplied CSV is used; no simulation or fallback generation exists. |
| 1.3 Schema matches context | **PASS** | The loader validates `month`, `revenue_usd`, `visits_count`, `avg_revenue_per_visit_usd`, and `region`. |
| 1.4 Company-specific behavior | **PASS** | Documentation and feature engineering address HealthCore's alternating 2–6% growth, July–August trough, and October–December peak. |
| 1.5 No destructive alterations | **PASS** | Raw source values are preserved; transformations create causal features only. |

### 2. Data Preparation — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 2.1 Null/empty values handled | **PASS** | Source nulls are rejected; lag-created missing values are filled using training-only medians. |
| 2.2 Variables requiring scaling handled | **PASS** | Scaling is not required for the selected tree-based Random Forest; this choice is documented. |

### 3. Train/Test Split — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 3.1 First eight years for training | **PASS** | January 2016 through December 2023, exactly 96 rows. |
| 3.2 Most recent two years for testing | **PASS** | January 2024 through December 2025, exactly 24 rows. |
| 3.3 No overlap or leakage | **PASS** | Chronological date filtering and disjoint-date assertions are implemented. |
| 3.4 No test-year training | **PASS** | `.fit()` receives only rows before January 2024. |
| 3.5 Split unit test exists | **PASS** | `tests/pipelines/test_sales_forecasting.py` validates dates, counts, and disjointness. |
| 3.6 Split unit test passes | **PASS** | Focused test run completed with `3 passed`. |

### 4. Model Training — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 4.1 Approved algorithm | **PASS** | Uses scikit-learn `RandomForestRegressor`. |
| 4.2 Algorithm choice justified | **PASS** | Rationale is documented in `docs/sales-forecasting.md`. |
| 4.3 Relevant selection criteria | **PASS** | Rationale covers small data size, nonlinear interactions, explainability, and available tuning time. |
| 4.4 Reproducibility seed | **PASS** | `random_state=42` is fixed. |

### 5. Evaluation Metrics — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 5.1 MSE | **PASS** | Calculated from held-out `y_test` and predictions. |
| 5.2 PSI | **PASS** | Training is the reference distribution and test is the monitored distribution; bins are training-derived. |
| 5.3 Gini | **PASS** | A deterministic regression Gini convention is documented and calculated on test data. |
| 5.4 K2 Score | **PASS** | A deterministic squared-correlation K2 convention is documented and calculated on test data. |
| 5.5 Test-only metrics | **PASS** | Evaluation arrays are drawn from the held-out test split. |
| 5.6 Metric explanations | **PASS** | Definitions and interpretation are documented. |
| 5.7 MSE limitation | **PASS** | Documentation explains that MSE alone can hide seasonal bias, distribution shift, association/ranking problems, and peak/trough errors. |

### 6. Visualization — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 6.1 Prediction visualization | **PASS** | `outputs/sales_forecast_healthcore.png` is generated by the runner. |
| 6.2 Variability range | **PASS** | The chart includes a 10th–90th percentile range from individual Random Forest trees. |
| 6.3 Actual test-year comparison | **PASS** | Actual and predicted revenue are plotted for all test months in 2024–2025. |

### 7. Submission Process — CONDITIONAL PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 7.1 Descriptive commits | **PASS** | Commit `eab4c30` is titled `feat: add HealthCore sales forecasting pipeline`. |
| 7.2 Branch pushed to student fork | **PASS** | `feature/sales-forecast-model` was pushed to the configured fork remote. |
| 7.3 Pull request against fork `main` | **PENDING** | The branch is ready and GitHub supplied the PR creation URL, but the PR was not created during this session. |
| 7.4 PR explains algorithm choice | **READY** | Prepared PR text explains the Random Forest selection and rationale. |
| 7.5 PR includes test metrics | **READY** | Prepared PR text includes MSE, PSI, Gini, and K2 Score. |

### 8. Environment and Tooling — PASS

| Criterion | Verdict | Evidence / rationale |
|---|---|---|
| 8.1 `uv` dependency management | **PASS** | Dependencies were added with `uv add`; `pyproject.toml` and `uv.lock` are present. |
| 8.2 Descriptive feature branch from main | **PASS** | Branch `feature/sales-forecast-model` was created and pushed. |

## Submission Readiness Checklist

- [x] Provided dataset exists at `data/raw/healthcore_sales.csv`.
- [x] Dataset schema and date range are validated.
- [x] HealthCore seasonality and growth context are documented.
- [x] Training period is exactly 2016–2023.
- [x] Test period is exactly 2024–2025.
- [x] Train/test leakage checks exist.
- [x] Split tests pass.
- [x] Random Forest is used with `random_state=42`.
- [x] Algorithm rationale is documented.
- [x] MSE, PSI, Gini, and K2 Score are calculated on test data.
- [x] Metric formulas and limitations are documented.
- [x] Prediction variability visualization is generated.
- [x] Dependencies were added with `uv`.
- [x] `uv.lock` is present.
- [x] Descriptive feature branch exists.
- [x] Changes are committed.
- [x] Branch is pushed to the fork.
- [ ] Pull request is opened against the fork's `main` branch.
- [ ] Pull request description contains algorithm rationale and held-out metrics.

## Prepared Pull Request Information

**PR title:**

```text
feat: add HealthCore sales forecasting model
```

**PR URL:**

```text
https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz/pull/new/feature/sales-forecast-model
```

**Recommended PR summary:**

```text
## Summary
- Add a leakage-safe HealthCore monthly revenue forecasting pipeline.
- Train a Random Forest on 2016–2023 and evaluate on held-out 2024–2025 data.
- Add causal seasonal/lag features, tests, documentation, and prediction-interval visualization.

## Algorithm
RandomForestRegressor was selected because the dataset is small, nonlinear seasonal interactions are plausible, and the ensemble is easier for Finance to explain than sequential boosting. random_state=42 ensures reproducibility.

## Held-out test metrics
- MSE: 26,769,688,048.83 USD²
- PSI: 7.8416 (verified; training reference → test monitored; elevated by growth-driven concentration in upper bins and zero lower-bin test counts)
- Regression Gini: 0.5325
- K2 Score: 0.8537

Tests: `uv run pytest tests/pipelines/test_sales_forecasting.py -q` — 3 passed.
```

## Final Audit Verdict

**CONDITIONAL PASS.**

The implementation and repository are technically ready for submission. The only outstanding rubric item is the actual GitHub pull request. Open the PR using the URL above, target the repository's `main` branch, paste the prepared description, and verify that the metrics and algorithm rationale are visible in the PR body. After that action, the project should satisfy the complete pre-submission rubric.
