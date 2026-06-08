"""Shared fixtures for the forecasting test suite.

The fixtures build small, hand-verifiable production frames so each test can
assert exact feature values rather than relying on the full USDA dataset.
"""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def consecutive_series() -> pd.DataFrame:
    """One State/commodity pair with five consecutive years.

    Production rises by a fixed 100 each year so lag, rolling, and target
    values are easy to compute by hand.
    """
    return pd.DataFrame(
        {
            "State": ["IOWA"] * 5,
            "commodity": ["Milk"] * 5,
            "Year": [2015, 2016, 2017, 2018, 2019],
            "total_production": [100, 200, 300, 400, 500],
        }
    )


@pytest.fixture
def gapped_series() -> pd.DataFrame:
    """One pair with a multi-year gap between 2016 and 2019.

    The 2016 row has no 2017 follow-up, so it must NOT become a one-year-ahead
    training example. Only the consecutive 2019->2020 pair is a valid target.
    """
    return pd.DataFrame(
        {
            "State": ["OHIO"] * 3,
            "commodity": ["Cheese"] * 3,
            "Year": [2016, 2019, 2020],
            "total_production": [100, 200, 250],
        }
    )


@pytest.fixture
def two_pair_frame() -> pd.DataFrame:
    """Two State/commodity pairs with differing latest years.

    Used to check that forward features take the latest row per group and that
    the recency filter can distinguish an active pair from a stale one.
    """
    return pd.DataFrame(
        {
            "State": ["IOWA", "IOWA", "IOWA", "TEXAS", "TEXAS"],
            "commodity": ["Milk", "Milk", "Milk", "Milk", "Milk"],
            "Year": [2021, 2022, 2023, 2010, 2011],
            "total_production": [300, 400, 500, 70, 80],
        }
    )
