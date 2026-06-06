# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

USDA agricultural production analytics portfolio (1930–2023) covering milk, cheese, honey, coffee, and yogurt. The pipeline flows: raw CSV files → SQLite source tables → SQL cleaning/analysis → dashboard export CSV → Plotly Dash app.

## Commands

**Run SQL analysis files:**
```bash
sqlite3 SQL/project-USDA.sqlite < SQL/01_data_quality_checks.sql
sqlite3 SQL/project-USDA.sqlite < SQL/02_cleaning_transformations.sql
sqlite3 SQL/project-USDA.sqlite < SQL/03_core_analysis_questions.sql
```

**Regenerate the dashboard CSV from SQLite (run inside sqlite3 shell):**
```bash
sqlite3 SQL/project-USDA.sqlite
```
Then inside the shell:
```sql
.headers on
.mode csv
.once SQL/USDA_production_2023.csv
.read SQL/07_dashboard_export.sql
```

**Install dependencies:**
```bash
python -m pip install -r requirements.txt
```

**Run the dashboard:**
```bash
cd dashboard && python app.py
```
Opens at `http://localhost:1234`.

## Architecture

### Data Pipeline

```
Raw CSV files (SQL/*.csv)
  → SQLite source tables (SQL/project-USDA.sqlite)
  → SQL data quality checks (01_)
  → commodity_production_long view (02_)
  → SQL analysis modules (03_–06_)
  → Dashboard export (07_) → SQL/USDA_production_2023.csv
  → Dash app (dashboard/app.py)
```

### Database Schema

`SQL/project-USDA.sqlite` contains five commodity tables (`milk_production`, `cheese_production`, `honey_production`, `coffee_production`, `yogurt_production`) plus `state_lookup`. `State_ANSI` is the universal join key. The view `commodity_production_long` (defined in `SQL/00_schema.sql`, recreated with cleaning in `SQL/02_cleaning_transformations.sql`) is the primary analysis surface for all downstream SQL modules.

**Critical period handling:** Milk and cheese have both monthly (`JAN`–`DEC`) and annual (`YEAR`) records. All aggregation queries and the dashboard export sum monthly records only and exclude `YEAR` to avoid double-counting. Honey has no `Period` column and is annual by default. Coffee and yogurt use `YEAR` records.

**Value column quirk:** Raw `Value` fields contain comma-formatted number strings (e.g., `"1,234,567"`). All queries cast via `REPLACE(CAST(Value AS TEXT), ',', '')` before arithmetic.

### SQL Module Sequence

| File | Role |
|---|---|
| `00_schema.sql` | DDL + indexes + `commodity_production_long` view definition |
| `01_data_quality_checks.sql` | Profiles row counts, nulls, blank State_ANSI, duplicates, coverage gaps |
| `02_cleaning_transformations.sql` | Removes comma formatting; recreates `commodity_production_long` |
| `03_core_analysis_questions.sql` | 10 business questions with direct SQL answers |
| `04_cte_analysis.sql` | Multi-step CTE pipelines |
| `05_window_function_analysis.sql` | LAG, rolling averages, ranks, percent contribution, volatility |
| `06_state_commodity_rankings.sql` | State rankings, production tier segmentation, CASE-based flags |
| `07_dashboard_export.sql` | Generates the annualized CSV consumed by the Dash app |

### Dashboard (`dashboard/app.py`)

Reads `../SQL/USDA_production_2023.csv` (columns: `State`, `Year`, `commodity`, `total_production`). Three Dash callbacks drive the UI:
- `update_line_chart` — national trend line, filtered by year range and commodity
- `update_bar_chart` — top 10 states for the most recent selected year; falls back to the latest year with data for the selected commodity
- `update_table` / `download_csv` — state-filtered AG Grid table with CSV export

Theme switching uses `dash-bootstrap-templates` (`ThemeSwitchAIO`): COSMO (light) and CYBORG (dark). The `COMMODITY_COLORS` dict in `app.py` is used across all three charts for visual consistency.

## Key Data Caveats

- Coffee records cover Hawaii only — do not compare its totals directly to national dairy patterns.
- Some source rows have blank `State_ANSI` and are excluded from `commodity_production_long`; they are profiled in `01_data_quality_checks.sql`.
- USDA source units vary by commodity; cross-commodity production totals are for SQL demonstration, not strict unit equivalence.
