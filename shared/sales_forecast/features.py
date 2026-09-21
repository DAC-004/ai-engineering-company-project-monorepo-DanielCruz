"""Causal calendar, lag, and rolling features for monthly revenue.

Every derived value for month t uses only information available before t.
Same-month `visits_count` and `avg_revenue_per_visit_usd` are excluded
because `avg * visits` reconstructs the current target.
"""

from __future__ import annotations

import pandas as pd

from shared.sales_forecast.constants import (
    FEATURE_COLUMNS,
    FLU_HIGH_MONTHS,
    SUMMER_LOW_MONTHS,
    TARGET_COLUMN,
)


def add_causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, and calendar columns without dropping warmup rows.

    Rolling statistics are computed on `shift(1)` so the current target never
    enters the window. Lag-1 and lag-12 likewise read only earlier months.
    """
    featured = frame.sort_values("month", kind="mergesort").reset_index(drop=True).copy()
    month_num = featured["month"].dt.month
    featured["year"] = featured["month"].dt.year.astype(int)
    featured["month_num"] = month_num.astype(int)
    featured["quarter"] = featured["month"].dt.quarter.astype(int)
    featured["is_summer_low"] = month_num.isin(SUMMER_LOW_MONTHS).astype(int)
    featured["is_flu_high"] = month_num.isin(FLU_HIGH_MONTHS).astype(int)

    prior_revenue = featured[TARGET_COLUMN].shift(1)
    prior_visits = featured["visits_count"].shift(1)
    featured["revenue_lag_1"] = prior_revenue
    featured["revenue_lag_12"] = featured[TARGET_COLUMN].shift(12)
    featured["visits_lag_1"] = prior_visits
    featured["visits_lag_12"] = featured["visits_count"].shift(12)

    # shift(1) first so rolling windows never include the current row.
    featured["revenue_roll_mean_3"] = prior_revenue.rolling(window=3, min_periods=3).mean()
    featured["revenue_roll_std_3"] = prior_revenue.rolling(window=3, min_periods=3).std()
    featured["revenue_roll_mean_12"] = prior_revenue.rolling(window=12, min_periods=12).mean()
    featured["revenue_roll_std_12"] = prior_revenue.rolling(window=12, min_periods=12).std()
    return featured


def drop_feature_warmup(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove rows that do not yet have a complete causal feature vector."""
    return frame.dropna(subset=list(FEATURE_COLUMNS)).reset_index(drop=True)


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the model input columns in a stable order."""
    return frame.loc[:, list(FEATURE_COLUMNS)].copy()


def target_vector(frame: pd.DataFrame) -> pd.Series:
    """Return the revenue target aligned to `frame`."""
    return frame[TARGET_COLUMN].astype(float).copy()
