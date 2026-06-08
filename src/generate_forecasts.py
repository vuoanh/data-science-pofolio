"""Generate forward forecasts for the latest observed year per state/commodity.

The script loads trained ML pipelines and predicts next-year production for
each State/commodity pair using all data available through each pair's most
recent observation.

Important caveat: the ML models were trained on target years <= 2018, so these
are out-of-sample extrapolations beyond the backtest window. Treat them as
directional estimates rather than calibrated point forecasts.

Writes:
- models/latest_forecasts.csv
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from build_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_forward_features,
    load_dashboard_data,
)
from evaluate_model import compute_rf_intervals


MODEL_FILES = {
    "random_forest": "random_forest.joblib",
    "xgboost": "xgboost.joblib",
}


def safe_path_component(value: str) -> str:
    """Return the commodity directory name used by train_model.py."""
    return (
        value.strip()
        .lower()
        .replace("&", "and")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def _residual_intervals(
    prediction: np.ndarray,
    residuals: pd.Series,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute forward intervals from held-out residual spread."""
    pred = np.asarray(prediction, dtype=float)
    residual_std = float(np.std(residuals.to_numpy(dtype=float)))
    return (
        pred - 1.282 * residual_std,
        pred + 1.282 * residual_std,
        pred - 1.960 * residual_std,
        pred + 1.960 * residual_std,
    )


def _load_backtest_residuals(model_dir: Path) -> dict[tuple[str, str], pd.Series]:
    """Return residuals by (model, commodity) from models/test_predictions.csv."""
    predictions_path = model_dir / "test_predictions.csv"
    if not predictions_path.exists():
        return {}

    predictions = pd.read_csv(predictions_path)
    predictions["residual"] = (
        predictions["prediction"] - predictions["target_next_year_production"]
    )
    return {
        (model_name, commodity): model_df["residual"]
        for (model_name, commodity), model_df in predictions.groupby(["model", "commodity"])
    }


def _available_model_paths(model_dir: Path, commodities: list[str]) -> dict[str, dict[str, Path]]:
    """Return trained ML model paths by commodity."""
    by_commodity_dir = model_dir / "by_commodity"
    model_paths: dict[str, dict[str, Path]] = {}

    for commodity in commodities:
        commodity_dir = by_commodity_dir / safe_path_component(commodity)
        available = {
            model_name: commodity_dir / filename
            for model_name, filename in MODEL_FILES.items()
            if (commodity_dir / filename).exists()
        }
        if available:
            model_paths[commodity] = available

    if not model_paths:
        expected = ", ".join(
            str(by_commodity_dir / "<commodity>" / filename)
            for filename in MODEL_FILES.values()
        )
        raise FileNotFoundError(
            f"No commodity-specific ML pipelines found. Expected one of: {expected}. "
            "Run src/train_model.py first."
        )
    return model_paths


def _forecast_with_model(
    model_name: str,
    pipeline_path: Path,
    forward: pd.DataFrame,
    x_forward: pd.DataFrame,
    residuals_by_model: dict[tuple[str, str], pd.Series],
    generated_at: str,
) -> pd.DataFrame:
    commodity = str(forward["commodity"].iloc[0])
    pipeline = joblib.load(pipeline_path)
    predictions = pipeline.predict(x_forward)

    if model_name == "random_forest":
        lo80, hi80, lo95, hi95 = compute_rf_intervals(pipeline, x_forward)
        interval_method = "rf_quantile"
    else:
        residuals = residuals_by_model.get((model_name, commodity))
        if residuals is None or residuals.empty:
            raise ValueError(
                f"Backtest residuals for {model_name}/{commodity} not found in test_predictions.csv. "
                "Run src/train_model.py before generating forward forecasts."
            )
        lo80, hi80, lo95, hi95 = _residual_intervals(predictions, residuals)
        interval_method = "residual_normal"

    results = forward[
        ["State", "commodity", "Year", "forecast_year", "total_production"]
    ].copy().rename(
        columns={
            "Year": "latest_observed_year",
            "total_production": "latest_observed_production",
        }
    )
    results["model"] = model_name
    results["forecast_production"] = predictions
    results["pi_80_lower"] = np.maximum(lo80, 0)
    results["pi_80_upper"] = hi80
    results["pi_95_lower"] = np.maximum(lo95, 0)
    results["pi_95_upper"] = hi95
    results["interval_method"] = interval_method
    results["forecast_generated_at"] = generated_at
    return results


def generate_forward_forecasts(args: argparse.Namespace) -> pd.DataFrame:
    model_dir = Path(args.model_dir)
    residuals_by_model = _load_backtest_residuals(model_dir)
    df = load_dashboard_data(args.input)
    forward = build_forward_features(df)

    # Keep only pairs where the latest observed year is within 3 years of the
    # commodity's own maximum year. States that dropped out of production
    # decades ago produce meaningless forward forecasts.
    commodity_max_year = forward.groupby("commodity")["Year"].transform("max")
    forward = forward[forward["Year"] >= commodity_max_year - 3].copy()

    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    commodities = sorted(forward["commodity"].unique())
    model_paths = _available_model_paths(model_dir, commodities)
    generated_at = datetime.now(timezone.utc).isoformat()

    forecast_frames: list[pd.DataFrame] = []
    for commodity, commodity_model_paths in model_paths.items():
        commodity_forward = forward[forward["commodity"] == commodity].copy()
        x_forward = commodity_forward[feature_columns]
        for model_name, pipeline_path in commodity_model_paths.items():
            forecast_frames.append(
                _forecast_with_model(
                    model_name,
                    pipeline_path,
                    commodity_forward,
                    x_forward,
                    residuals_by_model,
                    generated_at,
                )
            )

    results = pd.concat(forecast_frames, ignore_index=True)
    results = results.sort_values(["model", "commodity", "State"]).reset_index(drop=True)

    output_path = model_dir / "latest_forecasts.csv"
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
    print(f"Generated {len(forecasts)} forward forecasts -> models/latest_forecasts.csv")
    summary = (
        forecasts.groupby(["model", "commodity"])[["latest_observed_year", "forecast_year"]]
        .first()
        .reset_index()
        .to_string(index=False)
    )
    print(summary)


if __name__ == "__main__":
    main()
