"""Build a leakage-aware forecasting feature table for USDA commodities.

The modeling grain is one row per State, commodity, and feature year. The
target is the next calendar year's production for the same State/commodity
pair. Rows with non-consecutive target years are excluded so the model learns a
true one-year-ahead forecasting task.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"State", "Year", "commodity", "total_production"}

CATEGORICAL_FEATURES = ["State", "commodity"]

NUMERIC_FEATURES = [
    "Year",
    "total_production",
    "production_lag_1",
    "production_lag_2",
    "production_lag_3",
    "rolling_3_mean",
    "rolling_5_mean",
    "yoy_pct_change",
    "state_share_of_commodity",
    "production_rank_in_commodity_year",
    "years_observed_so_far",
    "expanding_mean_to_date",
]

TARGET_COLUMN = "target_next_year_production"


def load_dashboard_data(input_path: str | Path) -> pd.DataFrame:
    """Load and validate the dashboard-ready USDA production CSV."""
    path = Path(input_path)
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} is missing required columns: {missing_cols}")

    df = df.loc[:, ["State", "Year", "commodity", "total_production"]].copy()
    df["State"] = df["State"].astype(str).str.strip()
    df["commodity"] = df["commodity"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["total_production"] = pd.to_numeric(df["total_production"], errors="coerce")

    df = df.dropna(subset=["State", "commodity", "Year", "total_production"])
    df = df[df["total_production"] > 0].copy()
    df["Year"] = df["Year"].astype(int)

    return df.sort_values(["State", "commodity", "Year"]).reset_index(drop=True)


def build_forecasting_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Create features and next-year targets from annual production data."""
    data = df.sort_values(["State", "commodity", "Year"]).copy()
    group = data.groupby(["State", "commodity"], sort=False)

    data["production_lag_1"] = group["total_production"].shift(1)
    data["production_lag_2"] = group["total_production"].shift(2)
    data["production_lag_3"] = group["total_production"].shift(3)

    data["rolling_3_mean"] = group["total_production"].transform(
        lambda values: values.rolling(window=3, min_periods=1).mean()
    )
    data["rolling_5_mean"] = group["total_production"].transform(
        lambda values: values.rolling(window=5, min_periods=1).mean()
    )
    data["expanding_mean_to_date"] = group["total_production"].transform(
        lambda values: values.expanding(min_periods=1).mean()
    )
    data["years_observed_so_far"] = group.cumcount() + 1

    data["yoy_pct_change"] = (
        (data["total_production"] - data["production_lag_1"])
        / data["production_lag_1"].replace(0, np.nan)
    )

    commodity_year_total = data.groupby(["commodity", "Year"])["total_production"].transform("sum")
    data["state_share_of_commodity"] = data["total_production"] / commodity_year_total.replace(0, np.nan)
    data["production_rank_in_commodity_year"] = data.groupby(["commodity", "Year"])[
        "total_production"
    ].rank(method="dense", ascending=False)

    data["target_year"] = group["Year"].shift(-1)
    data[TARGET_COLUMN] = group["total_production"].shift(-1)

    modeling = data[data["target_year"] == data["Year"] + 1].copy()
    modeling["target_year"] = modeling["target_year"].astype(int)

    modeling = modeling.replace([np.inf, -np.inf], np.nan)
    ordered_columns = (
        ["State", "commodity", "Year", "target_year", TARGET_COLUMN]
        + NUMERIC_FEATURES
    )
    ordered_columns = list(dict.fromkeys(ordered_columns))

    return modeling.loc[:, ordered_columns].sort_values(
        ["target_year", "commodity", "State"]
    ).reset_index(drop=True)


def build_forward_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build features for the latest observed year per State/commodity.

    Applies the same lag, rolling, rank, and share engineering as
    build_forecasting_frame but returns the most recent row per group.
    No target column is included because the next-year observation does not
    yet exist.
    """
    data = df.sort_values(["State", "commodity", "Year"]).copy()
    grp = data.groupby(["State", "commodity"], sort=False)

    data["production_lag_1"] = grp["total_production"].shift(1)
    data["production_lag_2"] = grp["total_production"].shift(2)
    data["production_lag_3"] = grp["total_production"].shift(3)
    data["rolling_3_mean"] = grp["total_production"].transform(
        lambda v: v.rolling(window=3, min_periods=1).mean()
    )
    data["rolling_5_mean"] = grp["total_production"].transform(
        lambda v: v.rolling(window=5, min_periods=1).mean()
    )
    data["expanding_mean_to_date"] = grp["total_production"].transform(
        lambda v: v.expanding(min_periods=1).mean()
    )
    data["years_observed_so_far"] = grp.cumcount() + 1
    data["yoy_pct_change"] = (
        (data["total_production"] - data["production_lag_1"])
        / data["production_lag_1"].replace(0, np.nan)
    )
    commodity_year_total = (
        data.groupby(["commodity", "Year"])["total_production"].transform("sum")
    )
    data["state_share_of_commodity"] = (
        data["total_production"] / commodity_year_total.replace(0, np.nan)
    )
    data["production_rank_in_commodity_year"] = data.groupby(
        ["commodity", "Year"]
    )["total_production"].rank(method="dense", ascending=False)

    latest = (
        data.groupby(["State", "commodity"], sort=False)
        .last()
        .reset_index()
    )
    latest["forecast_year"] = latest["Year"] + 1
    latest = latest.replace([np.inf, -np.inf], np.nan)

    keep = (
        ["State", "commodity", "Year", "forecast_year", "total_production"]
        + NUMERIC_FEATURES
    )
    keep = list(dict.fromkeys(keep))
    return latest[[c for c in keep if c in latest.columns]].reset_index(drop=True)


def write_feature_dataset(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Build and write the forecasting feature table."""
    df = load_dashboard_data(input_path)
    features = build_forecasting_frame(df)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output, index=False)
    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build USDA forecasting features.")
    parser.add_argument(
        "--input",
        default="SQL/USDA_production_2023.csv",
        help="Dashboard-ready annual production CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/forecasting_features.csv",
        help="Output feature table path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = write_feature_dataset(args.input, args.output)
    print(f"Wrote {len(features):,} forecasting rows to {args.output}")
    print(
        f"Target years: {features['target_year'].min()}-"
        f"{features['target_year'].max()}"
    )


if __name__ == "__main__":
    main()
