"""Train baseline, Random Forest, and XGBoost forecasting models.

The script writes:
- data/processed/forecasting_features.csv
- models/model_metrics.json       — metrics + interval coverage per model
- models/feature_importance.csv
- models/test_predictions.csv     — backtest rows with prediction intervals
- models/random_forest.joblib     — fitted pipeline for forward forecasting
- models/xgboost.joblib           — fitted pipeline (when xgboost is installed)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    from xgboost import XGBRegressor
except ModuleNotFoundError:  # pragma: no cover - documented runtime dependency
    XGBRegressor = None

from build_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    write_feature_dataset,
)
from evaluate_model import (
    check_interval_coverage,
    compute_residual_intervals,
    compute_rf_intervals,
    metrics_by_group,
    regression_metrics,
)


def make_preprocessor() -> ColumnTransformer:
    """Create preprocessing for numeric and categorical features."""
    try:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # scikit-learn < 1.2
        encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)

    return ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            ("cat", encoder, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def with_log_target(regressor: Pipeline) -> TransformedTargetRegressor:
    """Wrap a regressor so it learns log production and predicts production."""
    return TransformedTargetRegressor(
        regressor=regressor,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def build_models(random_state: int) -> dict[str, TransformedTargetRegressor]:
    """Construct the ML model pipelines."""
    models: dict[str, TransformedTargetRegressor] = {
        "random_forest": with_log_target(
            Pipeline(
                steps=[
                    ("preprocess", make_preprocessor()),
                    (
                        "model",
                        RandomForestRegressor(
                            n_estimators=350,
                            min_samples_leaf=2,
                            max_features="sqrt",
                            random_state=random_state,
                            n_jobs=-1,
                        ),
                    ),
                ]
            )
        )
    }

    if XGBRegressor is not None:
        models["xgboost"] = with_log_target(
            Pipeline(
                steps=[
                    ("preprocess", make_preprocessor()),
                    (
                        "model",
                        XGBRegressor(
                            n_estimators=500,
                            learning_rate=0.04,
                            max_depth=4,
                            subsample=0.85,
                            colsample_bytree=0.85,
                            objective="reg:squarederror",
                            eval_metric="rmse",
                            random_state=random_state,
                            n_jobs=4,
                        ),
                    ),
                ]
            )
        )

    return models


def clean_feature_name(name: str) -> str:
    """Make sklearn-transformed feature names easier to read."""
    return name.replace("num__", "").replace("cat__", "")


def extract_feature_importance(
    model_name: str,
    estimator: TransformedTargetRegressor,
) -> pd.DataFrame:
    """Extract feature importances from tree-based models."""
    pipeline = estimator.regressor_
    transformed_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    feature_names = [clean_feature_name(name) for name in transformed_names]
    estimator = pipeline.named_steps["model"]

    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return pd.DataFrame(columns=["model", "feature", "importance"])

    return (
        pd.DataFrame(
            {
                "model": model_name,
                "feature": feature_names,
                "importance": np.asarray(importances, dtype=float),
            }
        )
        .sort_values(["model", "importance"], ascending=[True, False])
        .reset_index(drop=True)
    )


def split_train_test(
    features: pd.DataFrame,
    train_end_year: int,
    test_start_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use a time-based split on target_year to avoid future leakage."""
    train = features[features["target_year"] <= train_end_year].copy()
    test = features[features["target_year"] >= test_start_year].copy()

    if train.empty:
        raise ValueError("Training split is empty. Lower --train-end-year.")
    if test.empty:
        raise ValueError("Test split is empty. Lower --test-start-year.")

    return train, test


def _add_intervals(
    frame: pd.DataFrame,
    model_name: str,
    fitted_pipeline: TransformedTargetRegressor | None,
    x_test: pd.DataFrame,
) -> pd.DataFrame:
    """Attach prediction interval columns to a prediction frame.

    Random Forest uses tree-ensemble quantiles (no calibration data needed).
    All other models use symmetric Gaussian intervals from test-set residuals.
    """
    pred = frame["prediction"].to_numpy()
    actual = frame[TARGET_COLUMN].to_numpy()

    if model_name == "random_forest" and fitted_pipeline is not None:
        lo80, hi80, lo95, hi95 = compute_rf_intervals(fitted_pipeline, x_test)
        method = "rf_quantile"
    else:
        lo80, hi80, lo95, hi95 = compute_residual_intervals(pred, actual)
        method = "residual_normal"

    return frame.assign(
        pi_80_lower=lo80,
        pi_80_upper=hi80,
        pi_95_lower=lo95,
        pi_95_upper=hi95,
        interval_method=method,
    )


def evaluate_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    """Build overall and per-commodity metrics from long prediction rows."""
    metrics: dict[str, Any] = {"overall": {}, "by_commodity": {}}
    for model_name, model_df in predictions.groupby("model"):
        metrics["overall"][model_name] = regression_metrics(
            model_df[TARGET_COLUMN],
            model_df["prediction"],
        )
        metrics["by_commodity"][model_name] = metrics_by_group(
            model_df,
            TARGET_COLUMN,
            "prediction",
            "commodity",
        )
    return metrics


def train_and_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    """Train models, write artifacts, and return metrics metadata."""
    features = write_feature_dataset(args.input, args.features_output)
    train, test = split_train_test(features, args.train_end_year, args.test_start_year)

    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    x_train = train[feature_columns]
    y_train = train[TARGET_COLUMN]
    x_test = test[feature_columns]

    output_dir = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prediction_frames: list[pd.DataFrame] = []

    # Baseline models — no fitting, residual-based intervals
    baseline_predictions = {
        "baseline_previous_year": test["total_production"],
        "baseline_rolling_3_year": test["rolling_3_mean"].fillna(test["total_production"]),
    }
    for model_name, prediction in baseline_predictions.items():
        frame = test.loc[
            :, ["State", "commodity", "Year", "target_year", TARGET_COLUMN]
        ].assign(model=model_name, prediction=np.asarray(prediction, dtype=float))
        prediction_frames.append(_add_intervals(frame, model_name, None, x_test))

    importance_frames: list[pd.DataFrame] = []
    fitted_pipelines: dict[str, TransformedTargetRegressor] = {}

    for model_name, pipeline in build_models(args.random_state).items():
        pipeline.fit(x_train, y_train)
        fitted_pipelines[model_name] = pipeline

        prediction = pipeline.predict(x_test)
        frame = test.loc[
            :, ["State", "commodity", "Year", "target_year", TARGET_COLUMN]
        ].assign(model=model_name, prediction=prediction)
        prediction_frames.append(_add_intervals(frame, model_name, pipeline, x_test))
        importance_frames.append(extract_feature_importance(model_name, pipeline))

        joblib.dump(pipeline, output_dir / f"{model_name}.joblib")

    predictions = pd.concat(prediction_frames, ignore_index=True)
    metrics = evaluate_predictions(predictions)

    # Empirical coverage check per model
    coverage: dict[str, Any] = {}
    for model_name, model_df in predictions.groupby("model"):
        coverage[model_name] = check_interval_coverage(
            model_df[TARGET_COLUMN].to_numpy(),
            model_df["pi_80_lower"].to_numpy(),
            model_df["pi_80_upper"].to_numpy(),
            model_df["pi_95_lower"].to_numpy(),
            model_df["pi_95_upper"].to_numpy(),
        )

    best_model = min(
        metrics["overall"],
        key=lambda m: metrics["overall"][m]["mae"],
    )
    best_model_by_rmse = min(
        metrics["overall"],
        key=lambda m: metrics["overall"][m]["rmse"],
    )
    ml_model_names = [m for m in metrics["overall"] if not m.startswith("baseline_")]
    best_ml_model_by_mae = min(
        ml_model_names, key=lambda m: metrics["overall"][m]["mae"]
    )
    best_ml_model_by_rmse = min(
        ml_model_names, key=lambda m: metrics["overall"][m]["rmse"]
    )

    predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    if importance_frames:
        pd.concat(importance_frames, ignore_index=True).to_csv(
            output_dir / "feature_importance.csv", index=False
        )

    metadata: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": args.input,
        "feature_output_path": args.features_output,
        "train_end_year": args.train_end_year,
        "test_start_year": args.test_start_year,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "target": TARGET_COLUMN,
        "features": feature_columns,
        "models_trained": sorted(set(predictions["model"])),
        "best_model_by_mae": best_model,
        "best_model_by_rmse": best_model_by_rmse,
        "best_ml_model_by_mae": best_ml_model_by_mae,
        "best_ml_model_by_rmse": best_ml_model_by_rmse,
        "metrics": metrics,
        "interval_coverage": coverage,
    }

    metrics_path = output_dir / "model_metrics.json"
    metrics_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train USDA forecasting models.")
    parser.add_argument("--input", default="SQL/USDA_production_2023.csv")
    parser.add_argument("--features-output", default="data/processed/forecasting_features.csv")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--train-end-year", type=int, default=2018)
    parser.add_argument("--test-start-year", type=int, default=2019)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    metadata = train_and_evaluate(parse_args())
    best = metadata["best_model_by_mae"]
    best_metrics = metadata["metrics"]["overall"][best]
    best_ml = metadata["best_ml_model_by_rmse"]
    best_ml_metrics = metadata["metrics"]["overall"][best_ml]
    print(f"Trained models: {', '.join(metadata['models_trained'])}")
    print(f"Train rows: {metadata['train_rows']:,}; test rows: {metadata['test_rows']:,}")
    print(
        f"Best by MAE: {best} | MAE={best_metrics['mae']:.2f} | "
        f"RMSE={best_metrics['rmse']:.2f} | R2={best_metrics['r2']:.3f}"
    )
    print(
        f"Best ML by RMSE: {best_ml} | MAE={best_ml_metrics['mae']:.2f} | "
        f"RMSE={best_ml_metrics['rmse']:.2f} | R2={best_ml_metrics['r2']:.3f}"
    )
    print("\nInterval coverage (empirical vs nominal):")
    for model_name, cov in metadata["interval_coverage"].items():
        print(f"  {model_name}: 80%→{cov['coverage_80_pct']}%  95%→{cov['coverage_95_pct']}%")


if __name__ == "__main__":
    main()
