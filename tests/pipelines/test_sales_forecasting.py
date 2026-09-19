import numpy as np
from src.sales_forecasting.pipeline import load_data, split_data, build_features, metric_psi, metric_gini, metric_k2

def test_exact_eight_two_split_and_no_overlap():
    train, test = split_data(load_data())
    assert len(train) == 96 and len(test) == 24
    assert train.month.max().year == 2023 and test.month.min().year == 2024
    assert set(train.month).isdisjoint(set(test.month))

def test_features_are_causal():
    df = load_data(); features = build_features(df)
    row = features.iloc[20]
    assert row.revenue_lag_1 == df.iloc[19].revenue_usd
    assert row.revenue_lag_12 == df.iloc[8].revenue_usd
    assert np.isclose(row.revenue_roll_3, np.mean(df.iloc[17:20].revenue_usd))

def test_metrics_are_defined_on_test_arrays():
    y = np.array([1., 2., 3., 4.]); p = np.array([1., 2.5, 2.5, 4.])
    assert metric_psi(y, p) >= 0
    assert np.isfinite(metric_gini(y, p))
    assert 0 <= metric_k2(y, p) <= 1
