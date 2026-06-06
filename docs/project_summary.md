# Project Summary

## Objective

This project analyzes USDA agricultural production data from 1930-2023 using
SQLite, SQL, Python, and Dash. The portfolio goal is to show an end-to-end
structured data workflow: schema design, data quality checks, cleaning,
long-format transformations, analytical SQL, forecasting models, and
dashboard-ready reporting.

## Data Source

The canonical dashboard/model dataset is refreshed from USDA NASS QuickStats
public bulk exports for milk, cheese, honey, coffee, and yogurt. The refresh
filters exact annual state-level production measures for 1930-2023, excludes
blank state codes and `OTHER STATES` rollups, and keeps the latest USDA
`load_time` per state/year/commodity.

The SQLite database at `SQL/project-USDA.sqlite` remains useful for the legacy
SQL exercises that demonstrate cleaning, CTEs, and window functions on the
original source tables.

## SQL Methods Used

- Schema design and indexing
- Data quality checks for missing keys, coverage gaps, duplicate records, and
  invalid values
- Cleaning transformations for comma-formatted numeric values
- Long-format view creation with `UNION ALL`
- Joins and subqueries
- `GROUP BY` and `HAVING`
- `CASE` logic for segmentation and prioritization
- CTE-based analysis pipelines
- Window functions for ranking, year-over-year change, rolling averages, and
  percent contribution
- Forecasting feature engineering
- Random Forest and XGBoost model comparison
- Time-based model validation against persistence baselines

## Key Findings

Finding 1: Milk is the largest production category in the refreshed
dashboard-ready annual data, with roughly 13.5 trillion pounds of recorded
state-level production from 1930-2023.  
Evidence: [`SQL/USDA_production_2023.csv`](../SQL/USDA_production_2023.csv)

Finding 2: Latest-year top producers are highly concentrated by commodity:
California leads milk in 2023, Wisconsin leads cheese in 2023, North Dakota
leads honey in 2023, New York leads yogurt in 2023, and Hawaii leads coffee in
2023.  
Evidence: [`data/processed/usda_production_1930_2023_coverage_summary.csv`](../data/processed/usda_production_1930_2023_coverage_summary.csv)

Finding 3: The refreshed 2023 dataset has complete latest-year coverage for
all five project commodities: 48 milk states, 39 honey states, 13 cheese
states, 2 yogurt states, and 1 coffee state.  
Evidence: [`data/processed/usda_production_1930_2023_coverage_summary.csv`](../data/processed/usda_production_1930_2023_coverage_summary.csv)

Finding 4: Coffee coverage remains narrow because the USDA project measure is
reported only for Hawaii, and it is reported in pounds on a cherry-basis unit.  
Evidence: [`data/processed/usda_production_1930_2023_complete.csv`](../data/processed/usda_production_1930_2023_complete.csv)

Finding 5: The bulk refresh increased the canonical dashboard/model dataset
from 5,027 rows to 7,477 rows.  
Evidence: [`data/processed/usda_1930_2023_existing_vs_bulk_summary.csv`](../data/processed/usda_1930_2023_existing_vs_bulk_summary.csv)

Finding 6: The previous-year baseline is strongest by MAE for next-year
production forecasting, while Random Forest is the best ML benchmark. This
shows that annual commodity production is highly persistent and that ML models
must be evaluated against simple baselines.  
Model evidence: [`docs/forecasting_model_summary.md`](forecasting_model_summary.md)

## Limitations

- USDA source units can differ by commodity, so cross-commodity totals are best
  interpreted as examples of SQL workflow and relative records within this
  dataset, not unit-equivalent measures.
- The refreshed canonical dataset is annual state-level production. Some
  legacy SQL exercises still use the original SQLite/raw monthly tables for
  month-specific questions.
- Coffee and yogurt have much narrower state coverage than milk or honey.
- The dashboard currently visualizes annual production totals and does not yet
  include model predictions or a separate year-over-year tab.

## Next Steps

- Add a dashboard tab for year-over-year change using the logic in
  `SQL/05_window_function_analysis.sql`.
- Add a dashboard tab comparing actual vs predicted production.
- Add automated checks that compare the regenerated dashboard CSV against the
  expected app columns.
- Add a small Makefile or script to rebuild the SQLite database from raw CSVs.

## Portfolio Positioning

Resume bullet:

```text
Built an end-to-end SQL analytics project using USDA commodity production data, including relational schema design, data quality checks, CTEs, window functions, year-over-year trend analysis, and an interactive Dash dashboard.
```

LinkedIn Featured description:

```text
USDA Commodities SQL Analytics Project: SQLite, SQL, Python, and Dash project analyzing agricultural production trends from 1930-2023. Demonstrates schema design, data cleaning, joins, CTEs, window functions, ranking queries, and interactive dashboarding.
```
