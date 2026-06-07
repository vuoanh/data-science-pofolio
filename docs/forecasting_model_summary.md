# Forecasting Model Summary

## Objective

Forecast next-year USDA commodity production for each `State` and `commodity`
pair using the dashboard-ready annual production dataset.

The modeling layer demonstrates a practical data science workflow:

- leakage-aware feature engineering
- time-based train/test split (no random splitting)
- comparison against meaningful baselines before claiming ML value
- Random Forest and XGBoost model training
- prediction intervals with empirical coverage checks
- model evaluation by overall error and commodity-level error
- feature importance review
- forward forecasts for the latest available year per state/commodity

## Data

Input dataset:

```text
SQL/USDA_production_2023.csv
```

Generated feature table:

```text
data/processed/forecasting_features.csv
```

Modeling grain:

```text
State + commodity + feature year
```

Target:

```text
target_next_year_production
```

Rows are included only when the next observed record is the next calendar year.
This avoids treating multi-year gaps as one-year-ahead forecasts.

## Features

The model uses:

- current annual production
- 1-, 2-, and 3-year production lags
- 3-year and 5-year rolling averages
- year-over-year percent change
- state share of national commodity production
- production rank within commodity/year
- years observed so far
- expanding historical mean
- state and commodity categorical features (one-hot encoded)

## Validation Design

The split is time-based:

```text
Train target years: <= 2018
Test target years:  >= 2019
```

This is intentionally not a random split. Random splitting would leak future
production patterns into training and overstate performance on the test set.

Training rows: 6,724
Test rows: 518

## Models Compared

| Model | Notes |
|---|---|
| Previous-year baseline | Predicts next year equals current year. |
| Rolling 3-year baseline | Predicts next year equals current 3-year rolling average. |
| Random Forest | 350-tree ensemble trained on log-transformed target. |
| XGBoost | Gradient boosting model trained on log-transformed target. |

## Overall Results

| Model | MAE | RMSE | MAPE | R² |
|---|---:|---:|---:|---:|
| Previous-year baseline | 53,547,189 | 145,148,329 | 14.48% | 0.999 |
| Rolling 3-year baseline | 91,395,960 | 253,803,495 | 14.18% | 0.998 |
| Random Forest | 97,540,339 | 300,300,565 | 15.88% | 0.997 |
| XGBoost | 121,203,239 | 579,835,466 | 12.52% | 0.990 |

## Interpretation

**The previous-year baseline is strongest by MAE and RMSE.** This is a useful
modeling finding: annual production is highly persistent, so a simple baseline
is hard to beat on aggregate. An ML model that claims to beat this baseline
without carefully decomposing the error by commodity and time period is likely
overstating its value.

**Random Forest is the strongest ML model** by MAE and RMSE but does not beat
the persistence baseline on this split. The top features confirm why: current
production, 3-year rolling mean, 5-year rolling mean, and previous-year
production dominate importance. The model is mostly learning persistence and
recent trend, which the baseline already captures directly.

**XGBoost produces the lowest MAPE** (12.5%) but the highest RMSE, indicating
it handles percentage-scale errors better on smaller commodities (Honey, Coffee)
while being less accurate on Milk's large absolute values. More commodity-
specific tuning would be needed before drawing conclusions.

The appropriate next step is **commodity-specific modeling**: a Milk-only or
Cheese-only model trained on only that commodity's state histories, with a
longer test window, would give a fairer picture of whether ML adds value over
the persistence baseline for high-volume commodities.

## Top Random Forest Features

The strongest features by mean decrease in impurity:

1. current production
2. 3-year rolling mean
3. 5-year rolling mean
4. previous-year production (lag 1)
5. expanding historical mean

This confirms the model is learning production persistence and recent trend.
Features like state share and production rank add marginal value beyond the
lag and rolling features.

## Prediction Intervals

Fitted models include prediction intervals stored alongside test predictions
in `models/test_predictions.csv`.

**Random Forest** uses tree-ensemble quantile intervals: each of the 350
trees predicts independently, and the 10th/90th percentile across trees gives
80% bounds while the 2.5th/97.5th percentile gives 95% bounds. This requires
no held-out calibration data.

**Baselines and XGBoost** use symmetric Gaussian intervals derived from
test-set residual standard deviation (z = 1.282 for 80%, z = 1.960 for 95%).
These are computed post-hoc on the same test rows.

### Empirical Coverage

| Model | Nominal 80% | Actual 80% | Nominal 95% | Actual 95% |
|---|---:|---:|---:|---:|
| Persistence baseline | 80% | 91.9% | 95% | 95.4% |
| Rolling 3-year baseline | 80% | 92.1% | 95% | 94.8% |
| Random Forest | 80% | 82.6% | 95% | 96.3% |
| XGBoost | 80% | 96.7% | 95% | 97.7% |

The Random Forest 80% interval is closest to nominal coverage (82.6% vs 80%),
which is expected for tree-quantile intervals. The baselines and XGBoost are
over-covered because their residual std is inflated by Milk's large absolute
errors. Both are conservative (wider than needed), meaning they are honest but
imprecise on lower-production commodities.

**Per-commodity interval width varies significantly.** Milk has small MAPE
(5%) but enormous absolute residuals, so its intervals are wide in absolute
terms. Honey has large MAPE (29%) and wide intervals in relative terms. A
commodity-specific interval calibration would tighten both.

## Forward Forecasts

`src/generate_forecasts.py` produces one-step-ahead forecasts from the
latest available observation for each eligible State/commodity pair. Pairs
where the latest observation is more than 3 years behind the commodity's own
maximum year are excluded (these represent states that have exited production).

```text
models/latest_forecasts.csv
```

| Column | Description |
|---|---|
| `latest_observed_year` | Most recent year with USDA data for this pair |
| `forecast_year` | `latest_observed_year + 1` |
| `forecast_production` | Random Forest point forecast |
| `pi_80_lower/upper` | 80% tree-quantile prediction interval |
| `pi_95_lower/upper` | 95% tree-quantile prediction interval |
| `forecast_generated_at` | UTC timestamp of this run |

**Important caveat:** the Random Forest was trained on target years ≤ 2018.
For pairs with a latest observed year of 2023, the forward forecast is a
5-year extrapolation beyond the test window. Treat these as directional
estimates, not calibrated predictions.

Current forward forecast summary (all commodities at 2023 → 2024):

| Commodity | States covered | Mean forecast |
|---|---:|---:|
| Cheese | 13 | ~$883M |
| Coffee | 1 | ~$25M |
| Honey | 39 | ~$3.2M |
| Milk | 48 | ~$4.7B |
| Yogurt | 2 | ~$552M |

## Dashboard: Model Validation Tab

The dashboard includes a **Model Validation** tab that makes the backtest
results interactive. Navigate to the tab and use the commodity checklist and
state dropdown from the global filters to explore.

**Actual vs Predicted chart:** aggregates production across selected states by
commodity and forecast year (2019–2023), showing actual (solid line) and
predicted (dashed line) for the selected model.

**Metric cards:** MAE, RMSE, MAPE, and R² computed on the filtered subset.
Switching from Milk-only to Honey-only reveals the stark difference between
absolute error (Milk dominates) and percentage error (Honey is harder to
forecast).

**Largest misses table:** top 20 rows by absolute error for the filtered
selection. Milk in high-production years (California, Wisconsin) typically
dominates this table.

## Artifacts

| File | Contents |
|---|---|
| `models/model_metrics.json` | Metrics, coverage rates, and training metadata |
| `models/feature_importance.csv` | RF and XGBoost feature importances |
| `models/test_predictions.csv` | Backtest rows with predictions and intervals |
| `models/random_forest.joblib` | Fitted RF pipeline (used by generate_forecasts.py) |
| `models/xgboost.joblib` | Fitted XGBoost pipeline |
| `models/latest_forecasts.csv` | Forward forecasts from latest observed year |

## Reproduce

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Train models and regenerate all backtest artifacts:

```bash
python src/train_model.py
```

Generate forward forecasts (requires trained model from step above):

```bash
python src/generate_forecasts.py
```

Build features only:

```bash
python src/build_features.py
```

## Next Improvements

- **Commodity-specific models**: train separate models per commodity to
  eliminate cross-commodity noise. A Milk-only model with per-state temporal
  cross-validation is the most promising path to beating the persistence
  baseline on a high-volume commodity.
- **SHAP values**: add a SHAP analysis to quantify each feature's marginal
  contribution per prediction, moving beyond global importance scores.
- **Calibrated intervals**: use isotonic regression or a dedicated calibration
  step to tighten Honey and Coffee intervals without widening Milk's.
- **Forward forecast dashboard tab**: surface `latest_forecasts.csv` in the
  dashboard with per-state commodity forecast bars for the next year.
