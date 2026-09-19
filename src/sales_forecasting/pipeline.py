"""Leakage-safe HealthCore revenue forecasting pipeline."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error

EXPECTED_COLUMNS = ["month", "revenue_usd", "visits_count", "avg_revenue_per_visit_usd", "region"]
TRAIN_START, TEST_START, TEST_END = pd.Timestamp("2016-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-01")


def load_data(path="data/raw/healthcore_sales.csv"):
    df = pd.read_csv(path)
    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected schema: {list(df.columns)}")
    df["month"] = pd.to_datetime(df["month"], errors="raise")
    df = df.sort_values("month").reset_index(drop=True)
    if len(df) != 120 or df["month"].min() != TRAIN_START or df["month"].max() != TEST_END:
        raise ValueError("Expected 120 monthly rows from 2016-01 through 2025-12")
    if df["month"].isna().any() or df.isna().any().any() or (df["revenue_usd"] <= 0).any():
        raise ValueError("Null values and non-positive revenue are not allowed")
    if set(df["region"]) != {"consolidated"}:
        raise ValueError("Expected only consolidated rows")
    expected = pd.date_range(TRAIN_START, TEST_END, freq="MS")
    if not df["month"].equals(pd.Series(expected, name="month")):
        raise ValueError("Missing or duplicate months")
    return df


def split_data(df):
    train = df[df.month < TEST_START].copy()
    test = df[df.month >= TEST_START].copy()
    assert len(train) == 96 and len(test) == 24
    assert set(train.month).isdisjoint(set(test.month))
    return train, test


def build_features(df):
    """Build causal features; lag values use only rows before the current month."""
    out = df.copy()
    out["year"] = out.month.dt.year
    out["month_num"] = out.month.dt.month
    out["month_sin"] = np.sin(2 * np.pi * out.month_num / 12)
    out["month_cos"] = np.cos(2 * np.pi * out.month_num / 12)
    out["quarter"] = out.month.dt.quarter
    out["revenue_lag_1"] = out.revenue_usd.shift(1)
    out["revenue_lag_12"] = out.revenue_usd.shift(12)
    out["revenue_roll_3"] = out.revenue_usd.shift(1).rolling(3).mean()
    # Features are computed over the full chronological source for historical warm-up;
    # the target row itself and all future rows are excluded.
    return out


def metric_psi(reference, monitored, bins=10, epsilon=1e-6):
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2: return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    a, _ = np.histogram(reference, edges); b, _ = np.histogram(monitored, edges)
    p, q = a / len(reference), b / len(monitored)
    p, q = np.maximum(p, epsilon), np.maximum(q, epsilon)
    return float(np.sum((q - p) * np.log(q / p)))


def metric_gini(y_true, y_pred):
    """Regression Gini = 1 - normalized absolute error, range (-inf,1]."""
    baseline = np.mean(np.abs(y_true - np.median(y_true)))
    return float(1 - np.mean(np.abs(y_true - y_pred)) / baseline) if baseline else 0.0


def metric_k2(y_true, y_pred):
    """K2 is squared correlation (R2-style explained variance) on test data."""
    if np.std(y_true) == 0 or np.std(y_pred) == 0: return 0.0
    return float(np.corrcoef(y_true, y_pred)[0, 1] ** 2)


def train_and_evaluate(df):
    train, test = split_data(df)
    all_rows = build_features(df)
    feature_cols = ["visits_count", "avg_revenue_per_visit_usd", "year", "month_num", "month_sin", "month_cos", "quarter", "revenue_lag_1", "revenue_lag_12", "revenue_roll_3"]
    # Preserve all 96 training rows: missing initial lag/rolling values are filled
    # with medians computed from training rows only (never from test/future data).
    train_f = all_rows[all_rows.month < TEST_START].copy()
    test_f = all_rows[all_rows.month >= TEST_START].copy()
    fill_values = train_f[feature_cols].median(numeric_only=True)
    train_f[feature_cols] = train_f[feature_cols].fillna(fill_values)
    test_f[feature_cols] = test_f[feature_cols].fillna(fill_values)
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1, min_samples_leaf=2)
    model.fit(train_f[feature_cols], train_f.revenue_usd)
    pred = model.predict(test_f[feature_cols])
    tree_pred = np.stack([tree.predict(test_f[feature_cols]) for tree in model.estimators_])
    metrics = {"mse": float(mean_squared_error(test_f.revenue_usd, pred)), "psi": metric_psi(train_f.revenue_usd, test_f.revenue_usd), "gini": metric_gini(test_f.revenue_usd.to_numpy(), pred), "k2_score": metric_k2(test_f.revenue_usd.to_numpy(), pred)}
    return {"model": model, "train": train_f, "test": test_f, "predictions": pred, "lower": np.quantile(tree_pred, .1, axis=0), "upper": np.quantile(tree_pred, .9, axis=0), "metrics": metrics}
