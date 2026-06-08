"""Tests for the metric and prediction-interval helpers in evaluate_model.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from evaluate_model import (
    check_interval_coverage,
    compute_residual_intervals,
    compute_rf_intervals,
    metrics_by_group,
    regression_metrics,
)


# ---------------------------------------------------------------------------
# regression_metrics
# ---------------------------------------------------------------------------


def test_perfect_prediction_metrics():
    """Identical predictions give zero error and R2 of 1."""
    y = np.array([10.0, 20.0, 30.0])
    result = regression_metrics(y, y)
    assert result["mae"] == 0.0
    assert result["rmse"] == 0.0
    assert result["mape_percent"] == 0.0
    assert result["r2"] == 1.0


def test_known_error_metrics():
    """MAE and RMSE match a hand-computed constant-offset case."""
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 300.0])  # errors: +10, -10, 0
    result = regression_metrics(y_true, y_pred)
    assert result["mae"] == pytest.approx(20.0 / 3.0)
    assert result["rmse"] == pytest.approx(np.sqrt(200.0 / 3.0))


def test_mape_is_none_when_all_truth_zero():
    """MAPE is undefined (None) if every true value is zero."""
    result = regression_metrics(np.zeros(3), np.array([1.0, 2.0, 3.0]))
    assert result["mape_percent"] is None


def test_metrics_by_group_splits_by_commodity():
    """Each group gets its own metric dict."""
    frame = pd.DataFrame(
        {
            "commodity": ["Milk", "Milk", "Honey"],
            "y": [100.0, 200.0, 10.0],
            "pred": [100.0, 200.0, 12.0],
        }
    )
    grouped = metrics_by_group(frame, "y", "pred", "commodity")
    assert set(grouped) == {"Milk", "Honey"}
    assert grouped["Milk"]["mae"] == 0.0


# ---------------------------------------------------------------------------
# compute_residual_intervals
# ---------------------------------------------------------------------------


def test_residual_intervals_widen_with_confidence():
    """The 95% interval is strictly wider than the 80% interval."""
    pred = np.array([100.0, 200.0, 300.0])
    y_true = np.array([110.0, 180.0, 330.0])
    lo80, hi80, lo95, hi95 = compute_residual_intervals(pred, y_true)
    assert (hi95 - lo95 > hi80 - lo80).all()


def test_residual_intervals_centered_on_prediction():
    """Symmetric Gaussian bounds are centered on the point prediction."""
    pred = np.array([100.0, 200.0])
    y_true = np.array([90.0, 220.0])
    lo80, hi80, lo95, hi95 = compute_residual_intervals(pred, y_true)
    np.testing.assert_allclose((lo80 + hi80) / 2, pred)
    np.testing.assert_allclose((lo95 + hi95) / 2, pred)


def test_residual_interval_uses_expected_z_multiplier():
    """80% half-width equals 1.282 * residual std."""
    pred = np.array([0.0, 0.0, 0.0, 0.0])
    y_true = np.array([1.0, -1.0, 1.0, -1.0])  # residual std = 1.0
    lo80, hi80, _, _ = compute_residual_intervals(pred, y_true)
    assert (hi80 - pred) == pytest.approx(1.282)


# ---------------------------------------------------------------------------
# check_interval_coverage
# ---------------------------------------------------------------------------


def test_full_coverage_when_all_points_inside():
    """All points within bounds gives 100% empirical coverage."""
    y = np.array([5.0, 5.0, 5.0])
    lower = np.zeros(3)
    upper = np.full(3, 10.0)
    cov = check_interval_coverage(y, lower, upper, lower, upper)
    assert cov["coverage_80_pct"] == 100.0
    assert cov["coverage_95_pct"] == 100.0


def test_partial_coverage_counts_inclusive_bounds():
    """Points exactly on the bound count as covered; outside points do not."""
    y = np.array([0.0, 5.0, 20.0])  # first on lower bound, last outside
    lower = np.zeros(3)
    upper = np.full(3, 10.0)
    cov = check_interval_coverage(y, lower, upper, lower, upper)
    assert cov["coverage_80_pct"] == pytest.approx(66.7, abs=0.1)


# ---------------------------------------------------------------------------
# compute_rf_intervals — uses a tiny fitted pipeline
# ---------------------------------------------------------------------------


def _tiny_rf_pipeline() -> tuple[TransformedTargetRegressor, pd.DataFrame]:
    """Fit a small log-target RF on synthetic data, mirroring train_model.py."""
    x = pd.DataFrame(
        {
            "lag": np.linspace(10, 200, 24),
            "commodity": ["Milk"] * 24,
        }
    )
    y = x["lag"].to_numpy() * 1.1
    preprocess = ColumnTransformer(
        transformers=[
            ("num", "passthrough", ["lag"]),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["commodity"]),
        ]
    )
    pipeline = TransformedTargetRegressor(
        regressor=Pipeline(
            steps=[
                ("preprocess", preprocess),
                ("model", RandomForestRegressor(n_estimators=5, random_state=0)),
            ]
        ),
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )
    pipeline.fit(x, y)
    return pipeline, x


def test_rf_intervals_shape_and_ordering():
    """RF intervals return one bound per row with lower <= upper, 95% >= 80%."""
    pipeline, x = _tiny_rf_pipeline()
    lo80, hi80, lo95, hi95 = compute_rf_intervals(pipeline, x)
    assert lo80.shape == hi80.shape == (len(x),)
    assert (lo80 <= hi80).all()
    # 95% band spans at least as wide as the 80% band
    assert ((hi95 - lo95) >= (hi80 - lo80) - 1e-9).all()
