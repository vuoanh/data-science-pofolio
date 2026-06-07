"""Generate forward forecasts for the latest observed year per state/commodity.

The script loads the trained Random Forest pipeline and predicts next-year
production for each State/commodity pair using all data available through each
pair's most recent observation.

Important caveat: the Random Forest was trained on target years ≤ 2018, so
these are out-of-sample extrapolations beyond the backtest window. Treat them
as directional estimates rather than calibrated point forecasts.

Writes:
- models/latest_forecasts.csv
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from build_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_forward_features, load_dashboard_data
from evaluate_model import compute_rf_intervals


def generate_forward_forecasts(args: argparse.Namespace) -> pd.DataFrame:
    pipeline_path = Path(args.model_dir) / "random_forest.joblib"
    if not pipeline_path.exists():
        raise FileNotFoundError(
            f"Trained pipeline not found at {pipeline_path}. "
            "Run src/train_model.py first."
        )

    pipeline = joblib.load(pipeline_path)
    df = load_dashboard_data(args.input)
    forward = build_forward_features(df)

    # Keep only pairs where the latest observed year is within 3 years of the
    # commodity's own maximum year. States that dropped out of production
    # decades ago produce meaningless forward forecasts.
    commodity_max_year = forward.groupby("commodity")["Year"].transform("max")
    forward = forward[forward["Year"] >= commodity_max_year - 3].copy()

    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    x_forward = forward[feature_columns]

    predictions = pipeline.predict(x_forward)
    lo80, hi80, lo95, hi95 = compute_rf_intervals(pipeline, x_forward)

    results = forward[
        ["State", "commodity", "Year", "forecast_year", "total_production"]
    ].copy().rename(
        columns={
            "Year": "latest_observed_year",
            "total_production": "latest_observed_production",
        }
    )
    results["model"] = "random_forest"
    results["forecast_production"] = predictions
    results["pi_80_lower"] = lo80
    results["pi_80_upper"] = hi80
    results["pi_95_lower"] = lo95
    results["pi_95_upper"] = hi95
    results["interval_method"] = "rf_quantile"
    results["forecast_generated_at"] = datetime.now(timezone.utc).isoformat()

    output_path = Path(args.model_dir) / "latest_forecasts.csv"
    results.to_csv(output_path, index=False)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate USDA forward forecasts.")
    parser.add_argument("--input", default="SQL/USDA_production_2023.csv")
    parser.add_argument("--model-dir", default="models")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    forecasts = generate_forward_forecasts(args)
    print(f"Generated {len(forecasts)} forward forecasts → models/latest_forecasts.csv")
    summary = (
        forecasts.groupby("commodity")[["latest_observed_year", "forecast_year"]]
        .first()
        .reset_index()
        .to_string(index=False)
    )
    print(summary)


if __name__ == "__main__":
    main()
