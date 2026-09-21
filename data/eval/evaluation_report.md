# HealthCore monthly revenue forecast: formal evaluation

**Model:** existing `RandomForestRegressor` (`n_estimators=200`, `max_depth=6`, `min_samples_leaf=3`, `random_state=42`)  
**Series:** consolidated monthly `revenue_usd` from `data/raw/healthcore_sales.csv`  
**Scope:** this report evaluates the already-tuned 8-year / 2-year forecast. It does not replace that model.

Audience: technical lead (staging gate), Sandra (CEO, executive planning), Tom (Revenue Cycle, dollar-scale error), and Marcus (Clinical Operations, seasonal demand).

## 1. Diagnosis

The model is **overfitting**.

That is not a visual impression. Training error stays low while validation error stays materially higher, the gap does not close as chronological training history grows, and the same gap appears in every temporal fold and on the official 2024-2025 holdout.

| Evidence | Training error | Validation / holdout error | Pattern |
| --- | ---: | ---: | --- |
| Temporal CV mean MAE | 59,747.08 USD | 144,691.14 USD | 2.4x gap |
| Temporal CV mean RMSE | 75,045.88 USD | 171,939.19 USD | 2.3x gap |
| Official 8/2-year split MAE | 53,064.61 USD | 170,263.47 USD | 3.2x gap |
| Official 8/2-year split RMSE | 66,753.45 USD | 209,868.55 USD | 3.1x gap |
| Learning curve, 72 training months MAE | 48,387.43 USD | 177,282.17 USD | 3.7x gap |

Average monthly `revenue_usd` on the 120-month file is 2,877,266.33 USD. Relative to that baseline:

- official training MAE is 1.8% of average monthly revenue
- cross-validation MAE is 5.0%
- 2024-2025 holdout MAE is 5.9%
- 2024-2025 holdout RMSE is 7.3%

This is not underfitting. Underfitting would show high training and validation errors that converge. Training MAE remains in a 37k to 53k USD band after the first learning-curve point, so the forest is capturing the training window, including the documented July-August lows and October-December flu-season highs that Marcus already observes.

This is not a well-fitted model. A well-fitted model would show low training and validation errors that stay close. Here the validation miss is two to three times the training miss, and that gap is still present after 72 model-ready training months.

## 2. Learning-curve evidence

Artifact: `data/eval/learning_curve.png`

The curve uses expanding chronological prefixes inside 2016-2023 only. Each point trains on the first N model-ready months and validates on the next 12 months. Features are rebuilt from raw months through that point's last validation month, so later history cannot enter lag or rolling windows.

| Training months | Train end | Validation window | Train MAE (USD) | Val MAE (USD) | Train RMSE (USD) | Val RMSE (USD) |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 24 | 2018-12 | 2019-01 to 2019-12 | 42,749.38 | 179,270.77 | 51,229.17 | 200,533.62 |
| 30 | 2019-06 | 2019-07 to 2020-06 | 51,913.65 | 127,364.21 | 62,035.25 | 157,181.87 |
| 36 | 2019-12 | 2020-01 to 2020-12 | 46,920.85 | 120,160.81 | 57,406.56 | 142,824.64 |
| 42 | 2020-06 | 2020-07 to 2021-06 | 46,913.40 | 133,450.74 | 59,314.65 | 161,832.80 |
| 48 | 2020-12 | 2021-01 to 2021-12 | 36,885.63 | 147,561.69 | 47,944.04 | 180,309.98 |
| 54 | 2021-06 | 2021-07 to 2022-06 | 44,055.97 | 160,218.08 | 56,610.26 | 183,907.29 |
| 60 | 2021-12 | 2022-01 to 2022-12 | 46,635.53 | 141,865.30 | 60,714.76 | 170,565.17 |
| 66 | 2022-06 | 2022-07 to 2023-06 | 50,178.47 | 120,269.63 | 64,808.13 | 148,931.34 |
| 72 | 2022-12 | 2023-01 to 2023-12 | 48,387.43 | 177,282.17 | 61,487.32 | 200,880.17 |

Interpretation:

- Training MAE and RMSE stay low and nearly flat as history grows.
- Validation MAE and RMSE stay higher across the entire curve. They dip near 36 and 66 training months, then rise again. They never converge on the training band.
- The assignment's diagnostic for that pattern is overfitting: a persistent wide gap with low training error and materially higher validation error.

Adding earlier chronological months did not close the gap. That is why "collect more historical data" is not the first corrective action.

## 3. Temporal cross-validation evidence

Method: `sklearn.model_selection.TimeSeriesSplit` with 5 folds on the 84 model-ready training months (2017-01 through 2023-12). The splitter does not shuffle. Each fold trains only on earlier months and validates on later months.

Leakage control: each fold rebuilds causal `revenue_lag_*`, `visits_lag_*`, and rolling statistics from the raw 2016-2023 prefix that ends at that fold's last validation month. Later-fold actuals never enter an earlier fold's feature windows. Same-month `visits_count` and `avg_revenue_per_visit_usd` remain excluded because they reconstruct `revenue_usd`.

| Fold | Train window | Val window | Train n | Val n | Train MAE | Val MAE | Train RMSE | Val RMSE |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2017-01 to 2018-02 | 2018-03 to 2019-04 | 14 | 14 | 99,781.49 | 140,143.16 | 127,027.65 | 162,988.14 |
| 2 | 2017-01 to 2019-04 | 2019-05 to 2020-06 | 28 | 14 | 55,005.96 | 117,014.54 | 66,067.70 | 145,882.65 |
| 3 | 2017-01 to 2020-06 | 2020-07 to 2021-08 | 42 | 14 | 46,913.40 | 135,268.49 | 59,314.65 | 159,759.68 |
| 4 | 2017-01 to 2021-08 | 2021-09 to 2022-10 | 56 | 14 | 46,902.05 | 147,031.34 | 59,403.17 | 176,821.16 |
| 5 | 2017-01 to 2022-10 | 2022-11 to 2023-12 | 70 | 14 | 50,132.48 | 183,998.16 | 63,416.22 | 214,244.32 |

Selected cross-validation metric (MAE): **144,691.14 ± 24,627.14 USD**

Companion RMSE: **171,939.19 ± 26,081.43 USD**

Fold-mean training MAE is 59,747.08 ± 22,623.94 USD. Fold-mean training RMSE is 75,045.88 ± 29,198.15 USD.

## 4. How stable is performance when the training portion changes?

Performance is only moderately stable, and the instability has a direction.

Validation MAE ranges from 117,014.54 USD (fold 2) to 183,998.16 USD (fold 5). The standard deviation is 17% of the mean. Later folds, which sit in higher-revenue years created by the documented 2% to 6% annual growth, are worse than earlier folds.

The train versus validation gap is the stable part of the story. Every fold has a lower training error than its validation error. Fold 1 is the only fold with a higher training MAE (99,781.49 USD), and that fold has only 14 training rows. From fold 2 onward, training MAE settles near 47k to 55k USD while validation MAE stays above 117k USD.

The official 2024-2025 holdout continues the later-fold pattern: holdout MAE 170,263.47 USD and holdout RMSE 209,868.55 USD. That holdout is a rolling one-step-ahead evaluation, not a single 24-month-ahead forecast issued in December 2023. It is supporting evidence, not a substitute for the five-fold training-period CV.

## 5. MAE versus RMSE, and the primary metric

Both metrics are reported in USD, the same unit as `revenue_usd`.

- **MAE** is the average absolute monthly miss. If the cross-validation MAE is 144,691.14 USD, Tom can read that as: a typical validated month is off by about 145k USD, or about 5.0% of average monthly revenue.
- **RMSE** is the square root of mean squared error. It stays in USD, unlike the earlier project's MSE of 44,044,808,895.08 USD². RMSE penalizes larger misses more than MAE does.

On this evaluation, RMSE is consistently higher than MAE:

- CV: 171,939.19 versus 144,691.14 USD (ratio 1.19)
- official holdout: 209,868.55 versus 170,263.47 USD (ratio 1.23)

The ratio is moderate. Large misses exist, but RMSE is not being dominated by a single extreme month. That still matters for HealthCore. Sandra needs to tell a normal August low (about 12% to 18% below the annual average) from an atypical revenue drop that may warrant investigation. RMSE is the metric that rises faster when those atypical months are missed.

**Primary metric for this assignment: MAE.**

Tom asked for errors in business-interpretable terms. MAE answers in USD per month without a squared unit and without overweighting a few large residuals. RMSE remains mandatory complementary evidence, especially when the question is whether a large deviation is an ordinary seasonal swing or an atypical miss.

The supplied HealthCore context does not state whether overestimating sales is more costly than underestimating them. This report does not invent that policy. The documented need is to quantify monthly dollar error and to keep large atypical deviations visible. MAE and RMSE together do that. A directional cost rule would require an explicit statement from Sandra or Tom.

## 6. Corrective action

Increase regularization on the existing Random Forest before changing features or collecting more history:

1. Raise `min_samples_leaf` from 3 to 8.
2. Lower `max_depth` from 6 to 3.
3. Keep the same causal feature set, the same 8-year / 2-year split, and this same leakage-safe evaluation.
4. Re-run `scripts/evaluate_sales_forecast.py` and accept the change only if the train/validation MAE gap narrows without pushing both curves into a high-error underfitting band.

Why this action matches the diagnosis:

- The forest is already fitting the training window tightly. Training MAE is 36,885.63 to 53,064.61 USD once more than 24 model-ready months are available.
- `min_samples_leaf=3` on a 14-to-84-row monthly sample lets trees isolate very small local groups. That is enough capacity to memorize training-window residuals around the dominant `revenue_lag_12` signal (82.8% of the existing feature importance).
- Raising the leaf size and cutting depth forces more averaging and reduces that memorization. That is the direct response to a persistent low-train / high-validation gap.
- Adding more historical months is not the first action. The learning curve already grew the chronological training prefix from 24 to 72 months, and the gap did not close.
- Adding trees, deepening the forest, or expanding the feature set would increase capacity. That is the underfitting remedy, and this model is not underfitting.

After regularization, the already-documented visit-volume shift (PSI 6.60 on `visits_count` between 2016-2023 and 2024-2025) should be watched. Later CV folds are worse, so some of the remaining error may be growth-regime change rather than remaining overfit. That monitoring question comes after the capacity of the current forest is reduced. It is not a reason to skip regularization.

## 7. Answers required by the ticket

1. **Fit:** the model is overfitting.
2. **Stability:** validation MAE is 144,691.14 ± 24,627.14 USD across five chronological folds. Later, higher-revenue windows are worse, but the train/validation gap is present in every fold.
3. **Action:** regularize the existing Random Forest by setting `min_samples_leaf=8` and `max_depth=3`, then repeat this evaluation. Do not add complexity, and do not treat additional early history as the first fix.

## 8. Reproducibility

```text
uv run python scripts/train_sales_forecast.py
uv run python scripts/evaluate_sales_forecast.py
uv run pytest tests/pipelines
```

Numeric source for this report: `data/eval/evaluation_metrics.json`.
