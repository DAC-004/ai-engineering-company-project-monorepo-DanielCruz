"""Fixed configuration for the HealthCore monthly revenue forecast.

Seeds, split boundaries, and metric conventions are centralized so the
training script and tests use the same values.
"""

from __future__ import annotations

from datetime import date

# Dataset generation and model fitting use the same documented seed.
RANDOM_STATE = 42

EXPECTED_COLUMNS = (
    "month",
    "revenue_usd",
    "visits_count",
    "avg_revenue_per_visit_usd",
    "region",
)

TARGET_COLUMN = "revenue_usd"
PSI_COLUMN = "visits_count"
REGION_VALUE = "consolidated"

RAW_START_MONTH = date(2016, 1, 1)
RAW_END_MONTH = date(2025, 12, 1)
TRAIN_START_MONTH = date(2016, 1, 1)
TRAIN_END_MONTH = date(2023, 12, 1)
TEST_START_MONTH = date(2024, 1, 1)
TEST_END_MONTH = date(2025, 12, 1)

EXPECTED_RAW_ROWS = 120
EXPECTED_TRAIN_ROWS = 96
EXPECTED_TEST_ROWS = 24

# Calendar flags follow the documented HealthCore seasonality windows.
SUMMER_LOW_MONTHS = (7, 8)
FLU_HIGH_MONTHS = (10, 11, 12)

FEATURE_COLUMNS = (
    "year",
    "month_num",
    "quarter",
    "is_summer_low",
    "is_flu_high",
    "revenue_lag_1",
    "revenue_lag_12",
    "revenue_roll_mean_3",
    "revenue_roll_std_3",
    "revenue_roll_mean_12",
    "revenue_roll_std_12",
    "visits_lag_1",
    "visits_lag_12",
)

# Random Forest defaults: small monthly sample, limited tuning, explainability.
N_ESTIMATORS = 200
MAX_DEPTH = 6
MIN_SAMPLES_LEAF = 3

# PSI: 10 training-only quantile bins; epsilon avoids 0 * log(0).
PSI_N_BINS = 10
PSI_EPSILON = 1e-6

# scipy.stats.normaltest requires n >= 8.
K2_MIN_SAMPLE_SIZE = 8

# Expanding-window OOS residuals need enough history to fit a first model.
# 24 model-ready training months leaves 60 OOS residuals on this dataset.
EXPANDING_MIN_TRAIN_ROWS = 24
VARIABILITY_MIN_RESIDUALS = 8
VARIABILITY_Z_SCORE = 1.96
