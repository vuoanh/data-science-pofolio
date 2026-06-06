"""Train baseline, Random Forest, and XGBoost forecasting models.

The script writes:
- data/processed/forecasting_features.csv
- models/model_metrics.json
- models/feature_importance.csv
- models/test_predictions.csv
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from evaluate_model import metrics_by_group, regression_metrics


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

    prediction_frames: list[pd.DataFrame] = []

    baseline_predictions = {
        "baseline_previous_year": test["total_production"],
        "baseline_rolling_3_year": test["rolling_3_mean"].fillna(test["total_production"]),
    }
    for model_name, prediction in baseline_predictions.items():
        prediction_frames.append(
            test.loc[:, ["State", "commodity", "Year", "target_year", TARGET_COLUMN]].assign(
                model=model_name,
                prediction=np.asarray(prediction, dtype=float),
            )
        )

    importance_frames: list[pd.DataFrame] = []
    for model_name, pipeline in build_models(args.random_state).items():
        pipeline.fit(x_train, y_train)
        prediction = pipeline.predict(x_test)
        prediction_frames.append(
            test.loc[:, ["State", "commodity", "Year", "target_year", TARGET_COLUMN]].assign(
                model=model_name,
                prediction=prediction,
            )
        )
        importance_frames.append(extract_feature_importance(model_name, pipeline))

    predictions = pd.concat(prediction_frames, ignore_index=True)
    metrics = evaluate_predictions(predictions)
    best_model = min(
        metrics["overall"],
        key=lambda model_name: metrics["overall"][model_name]["mae"],
    )
    best_model_by_rmse = min(
        metrics["overall"],
        key=lambda model_name: metrics["overall"][model_name]["rmse"],
    )
    ml_model_names = [
        model_name
        for model_name in metrics["overall"]
        if not model_name.startswith("baseline_")
    ]
    best_ml_model_by_mae = min(
        ml_model_names,
        key=lambda model_name: metrics["overall"][model_name]["mae"],
    )
    best_ml_model_by_rmse = min(
        ml_model_names,
        key=lambda model_name: metrics["overall"][model_name]["rmse"],
    )

    output_dir = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    if importance_frames:
        pd.concat(importance_frames, ignore_index=True).to_csv(
            output_dir / "feature_importance.csv",
            index=False,
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
        "Best by MAE: "
        f"{best} | MAE={best_metrics['mae']:.2f} | "
        f"RMSE={best_metrics['rmse']:.2f} | R2={best_metrics['r2']:.3f}"
    )
    print(
        "Best ML by RMSE: "
        f"{best_ml} | MAE={best_ml_metrics['mae']:.2f} | "
        f"RMSE={best_ml_metrics['rmse']:.2f} | R2={best_ml_metrics['r2']:.3f}"
    )


if __name__ == "__main__":
    main()
