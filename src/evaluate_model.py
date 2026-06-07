"""Evaluation helpers for USDA production forecasting models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from sklearn.compose import TransformedTargetRegressor


def regression_metrics(y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray) -> dict[str, float]:
    """Return common regression metrics with safe MAPE handling."""
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    error = pred - truth

    nonzero = truth != 0
    if nonzero.any():
        mape = np.mean(np.abs(error[nonzero] / truth[nonzero])) * 100.0
    else:
        mape = np.nan

    ss_res = np.sum(error**2)
    ss_tot = np.sum((truth - np.mean(truth)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot != 0 else np.nan

    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mape_percent": float(mape) if not np.isnan(mape) else None,
        "r2": float(r2) if not np.isnan(r2) else None,
    }


def metrics_by_group(
    frame: pd.DataFrame,
    y_true_col: str,
    y_pred_col: str,
    group_col: str,
) -> dict[str, dict[str, float]]:
    """Compute regression metrics for each group in a prediction frame."""
    grouped_metrics: dict[str, dict[str, float]] = {}
    for group_value, group_df in frame.groupby(group_col):
        grouped_metrics[str(group_value)] = regression_metrics(
            group_df[y_true_col],
            group_df[y_pred_col],
        )
    return grouped_metrics


def compute_rf_intervals(
    fitted_pipeline: TransformedTargetRegressor,
    x_test: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute 80% and 95% prediction intervals from the RF tree ensemble.

    Individual trees were fit on log1p(y). Calling expm1 on each tree's output
    brings predictions back to the original production scale. Percentiles across
    all 350 trees give the interval bounds without requiring a separate
    calibration set.

    Returns (lower_80, upper_80, lower_95, upper_95).
    """
    inner = fitted_pipeline.regressor_
    x_transformed = inner.named_steps["preprocess"].transform(x_test)
    rf = inner.named_steps["model"]
    # shape: (n_estimators, n_samples) in original production scale
    tree_preds = np.vstack([
        np.expm1(tree.predict(x_transformed)) for tree in rf.estimators_
    ])
    lower_80 = np.percentile(tree_preds, 10, axis=0)
    upper_80 = np.percentile(tree_preds, 90, axis=0)
    lower_95 = np.percentile(tree_preds, 2.5, axis=0)
    upper_95 = np.percentile(tree_preds, 97.5, axis=0)
    return lower_80, upper_80, lower_95, upper_95


def compute_residual_intervals(
    prediction: np.ndarray,
    y_true: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute symmetric Gaussian prediction intervals from test-set residual std.

    Uses z = 1.282 for 80% and z = 1.960 for 95% coverage under a normality
    assumption. Returns (lower_80, upper_80, lower_95, upper_95).
    """
    pred = np.asarray(prediction, dtype=float)
    std = float(np.std(pred - np.asarray(y_true, dtype=float)))
    return (
        pred - 1.282 * std,
        pred + 1.282 * std,
        pred - 1.960 * std,
        pred + 1.960 * std,
    )


def check_interval_coverage(
    y_true: np.ndarray,
    lower_80: np.ndarray,
    upper_80: np.ndarray,
    lower_95: np.ndarray,
    upper_95: np.ndarray,
) -> dict[str, float]:
    """Return empirical coverage rates for 80% and 95% prediction intervals.

    Coverage should be close to the nominal rate; large deviations indicate the
    interval method is mis-calibrated for this dataset.
    """
    y = np.asarray(y_true, dtype=float)
    cov_80 = float(np.mean((y >= lower_80) & (y <= upper_80)))
    cov_95 = float(np.mean((y >= lower_95) & (y <= upper_95)))
    return {
        "coverage_80_pct": round(cov_80 * 100, 1),
        "coverage_95_pct": round(cov_95 * 100, 1),
    }
