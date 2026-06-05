# Project Summary

## Objective

This project analyzes USDA agricultural production data from 1930-2023 using
SQLite, SQL, Python, and Dash. The portfolio goal is to show an end-to-end
structured data workflow: schema design, data quality checks, cleaning,
long-format transformations, analytical SQL, and dashboard-ready reporting.

## Data Source

The repository includes USDA commodity production extracts for milk, cheese,
honey, coffee, and yogurt, plus a state lookup table with ANSI state codes. The
SQLite database is stored at `SQL/project-USDA.sqlite`.

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

## Key Findings

Finding 1: Milk is the largest production category by all-time total in the
dashboard-ready annualized data, with roughly 11.7 trillion in total recorded
production.  
SQL evidence: [`SQL/03_core_analysis_questions.sql`](../SQL/03_core_analysis_questions.sql)

Finding 2: Latest-year top producers are highly concentrated by commodity:
California leads milk in 2023, Wisconsin leads cheese in 2023, North Dakota
leads honey in 2022, New York leads yogurt in 2022, and Hawaii leads coffee in
2016.  
SQL evidence: [`SQL/06_state_commodity_rankings.sql`](../SQL/06_state_commodity_rankings.sql)

Finding 3: In April 2023 cheese production, only Wisconsin and California
exceeded 100 million in production.  
SQL evidence: [`SQL/06_state_commodity_rankings.sql`](../SQL/06_state_commodity_rankings.sql)

Finding 4: Coffee coverage is narrow in this dataset, with records only for
Hawaii. It should not be compared directly with national dairy patterns without
calling out the coverage difference.  
SQL evidence: [`SQL/01_data_quality_checks.sql`](../SQL/01_data_quality_checks.sql)

Finding 5: The source tables include blank `State_ANSI` records in milk,
cheese, and honey. The cleaned long-format view excludes those rows from
state-level analysis because they cannot join to `state_lookup`.  
SQL evidence: [`SQL/01_data_quality_checks.sql`](../SQL/01_data_quality_checks.sql)

## Limitations

- USDA source units can differ by commodity, so cross-commodity totals are best
  interpreted as examples of SQL workflow and relative records within this
  dataset, not unit-equivalent measures.
- Milk and cheese include monthly and annual records. The dashboard export sums
  monthly records and excludes annual summary rows to avoid double counting.
- Coffee and yogurt have much narrower state coverage than milk or honey.
- The dashboard currently visualizes annual production totals and does not yet
  include a separate year-over-year tab.

## Next Steps

- Add a dashboard tab for year-over-year change using the logic in
  `SQL/05_window_function_analysis.sql`.
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
