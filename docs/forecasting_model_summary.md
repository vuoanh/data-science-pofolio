# Forecasting Model Summary

## Objective

Forecast next-year USDA commodity production for each `State` and `commodity`
pair using the dashboard-ready annual production dataset.

The modeling layer is designed to show practical data science workflow:

- leakage-aware feature engineering
- time-based train/test split
- baseline comparison
- Random Forest and XGBoost model training
- model evaluation by overall error and commodity-level error
- feature importance review

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
- state and commodity categorical features

## Validation Design

The split is time-based:

```text
Train target years: <= 2018
Test target years: >= 2019
```

This is intentionally not a random split. Random splitting would leak future
patterns into training and overstate performance.

Training rows: 6,724  
Test rows: 518

The refreshed USDA bulk dataset includes coffee observations through 2023, so
coffee now appears in the test-period commodity metrics.

## Models Compared

| Model | Notes |
|---|---|
| Previous-year baseline | Predicts next year equals current year. |
| Rolling 3-year baseline | Predicts next year equals current 3-year rolling average. |
| Random Forest | Tree ensemble trained on log-transformed target. |
| XGBoost | Gradient boosting model trained on log-transformed target. |

## Overall Results

| Model | MAE | RMSE | MAPE | R2 |
|---|---:|---:|---:|---:|
| Previous-year baseline | 53,547,189 | 145,148,329 | 14.48% | 0.999 |
| Rolling 3-year baseline | 91,395,960 | 253,803,495 | 14.18% | 0.998 |
| Random Forest | 97,540,339 | 300,300,565 | 15.88% | 0.997 |
| XGBoost | 121,203,239 | 579,835,466 | 12.52% | 0.990 |

## Interpretation

The previous-year baseline is strongest by MAE and RMSE. This is a useful
modeling finding: annual production is highly persistent, so a simple baseline
is hard to beat.

Random Forest is the strongest ML model by MAE and RMSE, but it does not beat
the persistence baseline on this split.

XGBoost is included as a first boosting benchmark, but it is not the strongest
model on this split. The current result argues for more feature work or
commodity-specific modeling before claiming an ML improvement.

## Top Random Forest Features

The strongest Random Forest features are:

1. current production
2. 3-year rolling mean
3. 5-year rolling mean
4. previous-year production
5. expanding historical mean

This confirms that the model is mostly learning production persistence and
recent trend behavior.

## Artifacts

```text
models/model_metrics.json
models/feature_importance.csv
models/test_predictions.csv
```

## Reproduce

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Train models:

```bash
python src/train_model.py
```

Build features only:

```bash
python src/build_features.py
```

## Next Improvements

- Train separate models by commodity to avoid coffee/yogurt sparsity affecting
  global model behavior.
- Add prediction intervals or uncertainty bands.
- Add direct forecasts for the latest available year per state/commodity.
- Add a dashboard tab comparing actual vs predicted production.
