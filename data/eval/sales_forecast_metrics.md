# HealthCore sales forecast metrics

## Evaluation protocol

Rolling one-step-ahead historical evaluation on 2024-2025. Each test month uses information available before that month. Actuals from completed earlier test months may appear only as lagged or rolling inputs to a later test month. This is not a single 24-month-ahead forecast made at the end of 2023.

## Split

- Raw train: 96 rows, 2016-01-01 through 2023-12-01
- Raw test: 24 rows, 2024-01-01 through 2025-12-01
- Model-ready train: 84 rows, 2017-01-01 through 2023-12-01
- Model-ready test: 24 rows, 2024-01-01 through 2025-12-01

## Test-set metrics

- **MSE:** 44044808895.079613 USD²
- **RMSE as percent of average monthly revenue:** 7.2940% (This percentage is RMSE / average monthly revenue * 100. It is not MSE. MSE remains in USD squared.)
- **Normalized ranking Gini:** 0.893662

### PSI (train versus test population shift)

- **Value:** 6.596563
- **Input:** `visits_count` only
- **Assigned:** 96 of 96 train rows and 24 of 24 test rows
- **Pre-epsilon shares:** train 1.000000, test 1.000000
- **Empty test bins / test values above train max:** 5 / 3
- **Formula:** (test_share - train_share) * ln(test_share / train_share), summed over bins
- **Binning:** 10 quantile bins from training visits_count only; the same edges are applied to the test population
- **Zero protection:** bin proportions below 1e-06 are replaced with 1e-06 before the log term; bins are never refit on test
- **Interpretation:** large shift (industry convention: PSI > 0.25)
- **Population:** consolidated monthly visits_count, chronological train versus test
- **Not measured:** US versus UK visit mix; the supplied dataset contains only consolidated rows and no regional records were fabricated

### K2 Score (assignment name, undefined formula)

- **Label:** D'Agostino-Pearson K2 residual-normality statistic
- **Statistic:** 0.376737
- **p-value:** 0.828309
- **Test residuals used:** 24
- **Meaning:** evaluates whether the test residual distribution significantly departs from normality. This is not a forecast-accuracy metric and is not R² or Kolmogorov-Smirnov.

## Variability range

- **Label:** empirical residual variability range, not a confidence or prediction interval
- **Method:** chronological expanding-window walk-forward inside the training period: fit on the first i model-ready training months, predict month i+1, for i from 24 to n-1; residual_std is the sample standard deviation of finite out-of-sample residuals
- **Training-only out-of-sample residuals:** 60
- **Residual std:** 142376.37 USD
- **Half-width (±1.96 σ):** 279057.69 USD
- **Validation months:** 2019-01-01 through 2023-12-01

## Why low MSE alone is not enough

MSE reports squared dollar error but does not show whether the model ranks seasonal months correctly (Gini), whether consolidated visit volume shifted between train and test (PSI), or whether test residuals depart from normality (K2). Finance also cannot read USD² as a percentage without a separately labeled RMSE translation.
