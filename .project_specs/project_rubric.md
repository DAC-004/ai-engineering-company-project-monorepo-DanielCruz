# Project Rubric: Sales Forecasting with a Regression Model

**Repository (student's fork of the monorepo):** https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz.git

This rubric is for auditing a submitted implementation against the project requirements. For each item, check the evidence in the code, README, PR description, and outputs, then mark Pass, Fail, or Not Verifiable.

## How to Use This Rubric

1. Work through each section in order.
2. For every criterion, locate the specific file, function, or output that proves it.
3. Record a verdict: Pass, Fail, or Not Verifiable (evidence missing or ambiguous).
4. A project cannot be marked overall Pass if any Critical item fails.

---

## 1. Data Source and Integrity (Critical)

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 1.1 | Dataset loaded from the correct path: `data/raw/<company>_sales.csv` in the monorepo, or `content/contexts/sales-forecasting/<company>/<company>_sales.csv` in the reference repo | Data loading code, file path used |
| 1.2 | Dataset is the one provided, not generated or simulated | Compare row count, date range, and values against the original CSV |
| 1.3 | Column names and dataset format match `CONTEXT-company.md` | Column list in code vs column list in CONTEXT file |
| 1.4 | Implementation reflects the company's specific seasonality and growth pattern described in `CONTEXT-company.md`, not a generic template | Read CONTEXT file, check that feature engineering or commentary references actual seasonality |
| 1.5 | No alterations to the dataset that break its seasonality or growth pattern | Diff or spot-check transformed data against raw data |

## 2. Data Preparation

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 2.1 | Null or empty values are handled before training | Data cleaning step in code |
| 2.2 | Variables that need scaling are scaled | Scaler usage (e.g. StandardScaler, MinMaxScaler) applied to the correct columns |

## 3. Train/Test Split (Critical)

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 3.1 | Training set uses exactly the first 8 years of data | Date range check on training set |
| 3.2 | Test set uses exactly the 2 most recent years of data | Date range check on test set |
| 3.3 | No overlap or leakage between training and test sets | Confirm no shared rows or dates between the two sets |
| 3.4 | Model is never trained or fit on any test-year data | Trace the `.fit()` call and confirm it only receives training data |
| 3.5 | Unit test exists in `tests/pipelines/` validating the 8-year/2-year split rule and absence of data leakage | Locate the test file, confirm it runs and passes |
| 3.6 | The split unit test passes correctly | Run the test suite |

## 4. Model Training

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 4.1 | Model is either XGBoost or Random Forest, trained with scikit-learn | Model import and instantiation |
| 4.2 | The choice of algorithm is explicitly justified in code comments or README | Look for a written rationale, not just the model name |
| 4.3 | Justification references relevant criteria (data size, need for explainability, time available), not just "it performed better" | Read the justification text |
| 4.4 | Random seed (`random_state` or `seed`) is fixed for reproducibility | Check model instantiation and any train/test split randomness |

## 5. Evaluation Metrics (Critical)

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 5.1 | MSE is calculated on the test set | Metric computation code |
| 5.2 | PSI (Population Stability Index) is calculated on the test set | Metric computation code |
| 5.3 | Gini is calculated on the test set | Metric computation code |
| 5.4 | K2 Score is calculated on the test set | Metric computation code |
| 5.5 | All four metrics are computed on the test set, not the training set | Confirm the data passed into each metric function is the test set |
| 5.6 | README or code comments explain what each metric measures | Read the explanation for each metric |
| 5.7 | README or code comments explain why a low MSE alone is not sufficient | Read the explanation |

## 6. Visualization (Critical)

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 6.1 | A visualization is generated showing the model's prediction | Presence of a chart/plot output |
| 6.2 | The visualization includes a variability range around the prediction, not just a single point estimate | Confirm the chart shows a band, interval, or error range |
| 6.3 | The visualization compares the prediction against the real data from the 2 test years | Confirm actual test-year values are plotted alongside predictions |

## 7. Submission Process

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 7.1 | Changes are committed with clear, descriptive commit messages | Git log |
| 7.2 | Branch is pushed to the student's own fork of the monorepo at `https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz.git` | Git remote/branch check |
| 7.3 | Pull Request is opened against `main` on that same fork | PR target branch and repository URL |
| 7.4 | PR description briefly explains which algorithm was chosen and why | PR description text |
| 7.5 | PR description includes the metrics obtained on the test set | PR description text |

## 8. Environment and Tooling

| # | Criterion | Evidence to Check | Verdict |
|---|-----------|-------------------|---------|
| 8.1 | Dependencies were added with `uv add`, not `pip install` or `pipenv` | Check `pyproject.toml` and lockfile for `uv`-managed dependencies |
| 8.2 | Branch was created from `main` with a descriptive feature branch name | Git branch name and history |

---

## Overall Verdict

- **Pass**: All Critical items pass, and no more than minor gaps exist in non-critical sections.
- **Conditional Pass**: All Critical items pass, but one or more non-critical items need revision before merge.
- **Fail**: Any Critical item fails (Sections 1, 3, 5, or 6).

## Notes for the Auditing Agent

- Do not accept a generic implementation that ignores the company-specific `CONTEXT-company.md`. This is an explicit disqualifying condition per the project brief.
- Verify metrics are computed on held-out test data by tracing the actual variable passed into each metric function, not by trusting a comment or variable name.
- If the unit test for the split rule is missing entirely, mark 3.5 and 3.6 as Fail, not Not Verifiable.
- Flag any hardcoded or simulated data as a Critical failure under Section 1, even if the rest of the pipeline is correct.
