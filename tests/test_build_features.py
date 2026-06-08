"""Tests for the leakage-aware feature engineering in build_features.py.

These tests pin the contracts that protect the forecasting task from data
leakage: the consecutive-year target guard, correct lag/rolling values, and the
"latest eligible row" behavior used for forward forecasts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from build_features import (
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    build_forecasting_frame,
    build_forward_features,
    load_dashboard_data,
)


# ---------------------------------------------------------------------------
# load_dashboard_data
# ---------------------------------------------------------------------------


def _write_csv(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "production.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_load_dashboard_data_loads_clean_numeric(tmp_path):
    """Already-cleaned numeric production values load as floats.

    The dashboard CSV is produced by the SQL layer, which strips comma
    formatting upstream. This function therefore expects clean numbers.
    """
    path = _write_csv(
        tmp_path,
        [{"State": "IOWA", "Year": 2020, "commodity": "Milk", "total_production": 1234567}],
    )
    df = load_dashboard_data(path)
    assert df.loc[0, "total_production"] == pytest.approx(1_234_567.0)


def test_load_dashboard_data_coerces_and_drops_non_numeric(tmp_path):
    """Non-numeric production strings are coerced to NaN and dropped.

    This is the defensive contract: if upstream cleaning ever fails to strip
    comma formatting, those rows are excluded rather than crashing arithmetic.
    """
    path = _write_csv(
        tmp_path,
        [
            {"State": "IOWA", "Year": 2020, "commodity": "Milk", "total_production": 500},
            {"State": "OHIO", "Year": 2020, "commodity": "Milk", "total_production": "1,234,567"},
        ],
    )
    df = load_dashboard_data(path)
    assert list(df["State"]) == ["IOWA"]


def test_load_dashboard_data_drops_nonpositive_production(tmp_path):
    """Rows with zero or missing production are excluded."""
    path = _write_csv(
        tmp_path,
        [
            {"State": "IOWA", "Year": 2020, "commodity": "Milk", "total_production": 100},
            {"State": "OHIO", "Year": 2020, "commodity": "Milk", "total_production": 0},
            {"State": "TEXAS", "Year": 2020, "commodity": "Milk", "total_production": ""},
        ],
    )
    df = load_dashboard_data(path)
    assert list(df["State"]) == ["IOWA"]


def test_load_dashboard_data_requires_columns(tmp_path):
    """A missing required column raises a clear ValueError."""
    path = _write_csv(tmp_path, [{"State": "IOWA", "Year": 2020, "commodity": "Milk"}])
    with pytest.raises(ValueError, match="missing required columns"):
        load_dashboard_data(path)


# ---------------------------------------------------------------------------
# build_forecasting_frame — leakage guard + feature correctness
# ---------------------------------------------------------------------------


def test_target_is_strictly_next_year(consecutive_series):
    """Every training row's target_year must equal Year + 1 (no leakage)."""
    frame = build_forecasting_frame(consecutive_series)
    assert (frame["target_year"] == frame["Year"] + 1).all()


def test_multi_year_gap_is_excluded(gapped_series):
    """A row whose next observation skips years must not become a target.

    The 2016 Cheese row has no 2017 follow-up, so only the consecutive
    2019->2020 pair survives as a one-year-ahead example.
    """
    frame = build_forecasting_frame(gapped_series)
    assert list(frame["Year"]) == [2019]
    assert list(frame["target_year"]) == [2020]
    assert frame.loc[0, TARGET_COLUMN] == 250


def test_target_value_matches_next_year_production(consecutive_series):
    """The target equals the following year's actual production."""
    frame = build_forecasting_frame(consecutive_series).set_index("Year")
    # 2015->2016 target is 200, ..., 2018->2019 target is 500
    assert frame.loc[2015, TARGET_COLUMN] == 200
    assert frame.loc[2018, TARGET_COLUMN] == 500


def test_lag_features_are_correct(consecutive_series):
    """Lag 1/2/3 reference prior years within the same pair."""
    frame = build_forecasting_frame(consecutive_series).set_index("Year")
    # At feature year 2018 (production 400): lag1=300, lag2=200, lag3=100
    assert frame.loc[2018, "production_lag_1"] == 300
    assert frame.loc[2018, "production_lag_2"] == 200
    assert frame.loc[2018, "production_lag_3"] == 100


def test_rolling_mean_is_correct(consecutive_series):
    """3-year rolling mean averages the current and two prior years."""
    frame = build_forecasting_frame(consecutive_series).set_index("Year")
    # 2017 window = mean(100, 200, 300) = 200
    assert frame.loc[2017, "rolling_3_mean"] == pytest.approx(200.0)


def test_no_infinite_values_in_features(consecutive_series):
    """yoy_pct_change and shares never leak inf into the feature matrix."""
    frame = build_forecasting_frame(consecutive_series)
    numeric = frame[NUMERIC_FEATURES].to_numpy(dtype=float)
    assert not np.isinf(numeric).any()


# ---------------------------------------------------------------------------
# build_forward_features — latest row per pair, no target
# ---------------------------------------------------------------------------


def test_forward_features_take_latest_row_per_pair(two_pair_frame):
    """Exactly one forward row per State/commodity, at its latest year."""
    forward = build_forward_features(two_pair_frame)
    latest_by_state = forward.set_index("State")["Year"].to_dict()
    assert latest_by_state == {"IOWA": 2023, "TEXAS": 2011}


def test_forward_forecast_year_is_next_year(two_pair_frame):
    """forecast_year is always the year after the latest observation."""
    forward = build_forward_features(two_pair_frame)
    assert (forward["forecast_year"] == forward["Year"] + 1).all()


def test_forward_features_have_no_target_column(two_pair_frame):
    """Forward rows must not carry a target (the future is unknown)."""
    forward = build_forward_features(two_pair_frame)
    assert TARGET_COLUMN not in forward.columns
