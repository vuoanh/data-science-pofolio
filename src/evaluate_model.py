"""Evaluation helpers for USDA production forecasting models."""

from __future__ import annotations

import numpy as np
import pandas as pd


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
