# USDA Commodity Production Analytics Portfolio

[![CI](https://github.com/vuoanh/data-science-pofolio/actions/workflows/ci.yml/badge.svg)](https://github.com/vuoanh/data-science-pofolio/actions/workflows/ci.yml)

End-to-end data science project turning USDA QuickStats production data
from 1930-2023 into SQL analysis, machine-learning forecasts, and a
business-facing Dash dashboard.

![USDA commodity production dashboard preview](dashboard_preview.gif)

## Overview

- **Built a full analytics workflow**: USDA bulk-data refresh, cleaning,
  SQLite/SQL analysis, feature engineering, ML forecasting, dashboarding, and CI.
- **Modeled next-year production** for each state and commodity using
  commodity-specific Random Forest and XGBoost pipelines.
- **Added forecast uncertainty** with 80% and 95% prediction intervals.
- **Designed a business dashboard** with Overview, State Rankings, Forecasts,
  and Model Validation tabs.
- **Validated the modeling layer** against simple baselines with a time-based
  split and automated `pytest` coverage.

## Tech Stack

Python, pandas, scikit-learn, XGBoost, Dash, Plotly, Dash AG Grid, SQLite, SQL,
pytest, GitHub Actions.

## Dashboard Workflow

Select one
commodity, view all states, compare historical production, inspect forecasts,
and validate model behavior before trusting the forecast.

| Tab | What It Shows |
|---|---|
| **Overview** | KPI cards, YoY change, top state, production trend, top states, filtered records |
| **State Rankings** | All-state production benchmark and concentration/share view |
| **Forecasts** | Latest direct forecasts by state with 80% or 95% confidence intervals |
| **Model Validation** | Actual vs predicted production, residuals, and largest forecast misses |

Global controls: light/dark theme, commodity, year range, ML model, and
confidence interval.

## Modeling Summary

The supervised target is next-year production for each `State` and `commodity`
pair. Models are trained separately by commodity so Milk, Cheese, Honey,
Coffee, and Yogurt do not share one global error pattern.

| Model | MAE | RMSE | MAPE | R2 |
|---|---:|---:|---:|---:|
| Previous-year baseline | 53,547,189 | 145,148,329 | 14.48% | 0.999 |
| Rolling 3-year baseline | 91,395,960 | 253,803,495 | 14.18% | 0.998 |
| Random Forest | 95,637,996 | 299,652,379 | 13.07% | 0.997 |
| XGBoost | 91,818,392 | 288,924,673 | 12.78% | 0.998 |

The previous-year baseline remains strongest by MAE/RMSE, which is an important
finding because annual production is highly persistent. XGBoost is the strongest
ML benchmark and powers the model-comparison workflow.

## Key Outputs

| Artifact | Purpose |
|---|---|
| [`dashboard/app.py`](dashboard/app.py) | Interactive Dash dashboard |
| [`SQL/USDA_production_2023.csv`](SQL/USDA_production_2023.csv) | Canonical dashboard/model dataset |
| [`models/test_predictions.csv`](models/test_predictions.csv) | Backtest predictions, residuals, and intervals |
| [`models/latest_forecasts.csv`](models/latest_forecasts.csv) | Latest forward forecasts by state/commodity |
| [`models/by_commodity/`](models/by_commodity/) | Commodity-specific Random Forest and XGBoost pipelines |
| [`tests/`](tests/) | Forecasting pipeline tests |
| [`docs/forecasting_model_summary.md`](docs/forecasting_model_summary.md) | Modeling methodology and interpretation |

## Data Pipeline

```text
USDA QuickStats bulk exports
    -> refresh and reconcile annual state-level records
    -> SQL/USDA_production_2023.csv
    -> forecasting_features.csv
    -> commodity-specific ML models
    -> test_predictions.csv and latest_forecasts.csv
    -> Dash dashboard
```

The refreshed canonical dataset contains **7,477 annual state/commodity
records**. It excludes blank state codes and USDA `OTHER STATES` rollups to keep
the analysis state-level.

## Run Locally

```bash
python -m pip install -r requirements.txt
cd dashboard
python app.py
```

Open `http://localhost:1234`.

## Deploy On Render

This repo includes [`render.yaml`](render.yaml) for a free Render Web Service.
Render installs only the dashboard runtime dependencies from
[`requirements-render.txt`](requirements-render.txt), then starts the app with
Gunicorn:

```bash
gunicorn dashboard.app:server --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

In Render, create a new **Blueprint**, connect this GitHub repo, and select the
free `usda-commodity-dashboard` service. The first visit after inactivity can
take longer because free Render services may spin down.

## Rebuild Models

```bash
python src/build_features.py
python src/train_model.py
python src/generate_forecasts.py
```

## Test

```bash
python -m pip install -r requirements-dev.txt
pytest
```

Tests cover leakage prevention, feature engineering, prediction intervals,
forward-forecast recency filtering, and metric calculations. GitHub Actions runs
the suite on Python 3.11 and 3.12.

## Notes

- USDA units vary by commodity, so cross-commodity totals should be interpreted
  carefully.
- Coffee and Yogurt have narrower state coverage than Milk, Cheese, and Honey.
- Full project context: [`docs/project_summary.md`](docs/project_summary.md),
  [`docs/schema.md`](docs/schema.md), and
  [`docs/data_dictionary.md`](docs/data_dictionary.md).
