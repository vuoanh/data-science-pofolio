"""Tests for the pure helpers in generate_forecasts.py.

The full forecast run loads trained joblib pipelines from disk, so these tests
target the deterministic building blocks: filesystem-safe naming, the
residual-interval math, and the commodity recency filter that drops states
which exited production long ago.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from generate_forecasts import _residual_intervals, safe_path_component


# ---------------------------------------------------------------------------
# safe_path_component
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Milk", "milk"),
        ("  Cheese  ", "cheese"),
        ("Coffee & Tea", "coffee_and_tea"),
        ("Goat/Sheep", "goat_sheep"),
        ("New York", "new_york"),
    ],
)
def test_safe_path_component(raw, expected):
    """Commodity names map to stable lowercase directory names."""
    assert safe_path_component(raw) == expected


def test_safe_path_component_matches_train_model():
    """The directory name must match what train_model.py wrote on disk."""
    from train_model import safe_path_component as train_safe

    for name in ["Milk", "Coffee & Tea", "Goat/Sheep"]:
        assert safe_path_component(name) == train_safe(name)


# ---------------------------------------------------------------------------
# _residual_intervals
# ---------------------------------------------------------------------------


def test_residual_intervals_widen_with_confidence():
    """95% forward interval is wider than the 80% interval."""
    pred = np.array([100.0, 200.0])
    residuals = pd.Series([10.0, -10.0, 5.0, -5.0])
    lo80, hi80, lo95, hi95 = _residual_intervals(pred, residuals)
    assert (hi95 - lo95 > hi80 - lo80).all()


def test_residual_intervals_centered_on_forecast():
    """Bounds are symmetric around the point forecast."""
    pred = np.array([500.0])
    residuals = pd.Series([1.0, -1.0, 2.0, -2.0])
    lo80, hi80, lo95, hi95 = _residual_intervals(pred, residuals)
    assert (lo80 + hi80) / 2 == pytest.approx(500.0)
    assert (lo95 + hi95) / 2 == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Recency filter (mirrors generate_forward_forecasts)
# ---------------------------------------------------------------------------


def test_recency_filter_drops_stale_pairs():
    """Pairs more than 3 years behind the commodity max year are excluded."""
    forward = pd.DataFrame(
        {
            "State": ["IOWA", "TEXAS", "OHIO"],
            "commodity": ["Milk", "Milk", "Milk"],
            "Year": [2023, 2011, 2021],  # commodity max year = 2023
        }
    )
    commodity_max_year = forward.groupby("commodity")["Year"].transform("max")
    kept = forward[forward["Year"] >= commodity_max_year - 3]
    # 2023 and 2021 survive (within 3 years of 2023); 2011 is dropped.
    assert set(kept["State"]) == {"IOWA", "OHIO"}
