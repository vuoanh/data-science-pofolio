# Forecasting Model Summary

## Objective

Forecast next-year USDA commodity production for each `State` and `commodity`
pair using the dashboard-ready annual production dataset.

The modeling layer demonstrates a practical data science workflow:

- leakage-aware feature engineering
- time-based train/test split (no random splitting)
- comparison against meaningful baselines before claiming ML value
- commodity-specific Random Forest and XGBoost model training
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
| Random Forest | Commodity-specific 350-tree ensemble trained on log-transformed target. |
| XGBoost | Commodity-specific gradient boosting model trained on log-transformed target. |

## Overall Results

| Model | MAE | RMSE | MAPE | R² |
|---|---:|---:|---:|---:|
| Previous-year baseline | 53,547,189 | 145,148,329 | 14.48% | 0.999 |
| Rolling 3-year baseline | 91,395,960 | 253,803,495 | 14.18% | 0.998 |
| Random Forest | 95,637,996 | 299,652,379 | 13.07% | 0.997 |
| XGBoost | 91,818,392 | 288,924,673 | 12.78% | 0.998 |

## Interpretation

**The previous-year baseline is strongest by MAE and RMSE.** This is a useful
modeling finding: annual production is highly persistent, so a simple baseline
is hard to beat on aggregate. An ML model that claims to beat this baseline
without carefully decomposing the error by commodity and time period is likely
overstating its value.

**Commodity-specific XGBoost is now the strongest ML model** by MAE, RMSE,
and MAPE, but it still does not beat the persistence baseline on this split.
This is a stronger modeling design than the earlier global model because each
commodity gets its own fitted pipeline and residual pattern.

**Random Forest improved after the split** and remains useful because its
tree-quantile intervals are easy to explain. The top features still confirm
that current production, rolling means, and lagged production dominate model
behavior.

The important portfolio takeaway is that the project now demonstrates an
iterative modeling workflow: start with a global benchmark, identify
cross-commodity scale problems, then move to commodity-specific models while
still comparing against simple baselines.

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
| Persistence baseline | 80% | 90.2% | 95% | 93.8% |
| Rolling 3-year baseline | 80% | 88.6% | 95% | 92.9% |
| Random Forest | 80% | 76.8% | 95% | 90.5% |
| XGBoost | 80% | 90.2% | 95% | 92.9% |

The Random Forest intervals are now slightly under-covered after splitting
models by commodity, while XGBoost residual-normal intervals are still
conservative. This is a useful next diagnostic: commodity-specific models
improve point accuracy, but interval calibration still needs refinement.

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
| `model` | Forecasting model, currently Random Forest or XGBoost |
| `forecast_production` | Model point forecast |
| `pi_80_lower/upper` | 80% prediction interval |
| `pi_95_lower/upper` | 95% prediction interval |
| `forecast_generated_at` | UTC timestamp of this run |

**Important caveat:** the ML models were trained on target years ≤ 2018.
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
| `models/by_commodity/<commodity>/random_forest.joblib` | Commodity-specific RF pipeline |
| `models/by_commodity/<commodity>/xgboost.joblib` | Commodity-specific XGBoost pipeline |
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

- **Commodity-specific hyperparameter tuning**: tune Random Forest and XGBoost
  separately for Milk, Cheese, Honey, Coffee, and Yogurt instead of sharing one
  parameter set.
- **SHAP values**: add a SHAP analysis to quantify each feature's marginal
  contribution per prediction, moving beyond global importance scores.
- **Calibrated intervals**: use isotonic regression or a dedicated calibration
  step to tighten Honey and Coffee intervals without widening Milk's.
- **Forward forecast dashboard tab**: surface `latest_forecasts.csv` in the
  dashboard with per-state commodity forecast bars for the next year.
