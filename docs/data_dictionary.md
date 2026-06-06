# Data Dictionary

This project uses USDA agricultural production extracts loaded into SQLite.
The source tables keep the commodity-specific shape from the raw CSV files,
then `commodity_production_long` consolidates them for analysis and dashboard
export.

## Source Tables

### `state_lookup`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `State` | `TEXT` | Uppercase US state name. | Used for dashboard labels and final reporting. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Primary join key between the lookup and commodity tables. |

### `milk_production`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `Year` | `INTEGER` | Production year. | Monthly records are used for annual dashboard totals; `YEAR` period records are excluded from the dashboard export to avoid double counting. |
| `Period` | `TEXT` | Month abbreviation or `YEAR`. | Monthly periods are summed to annual totals. |
| `Geo_Level` | `TEXT` | USDA geographic level, usually `STATE`. | Retained for source traceability. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Blank codes are excluded from state-level analysis. |
| `Commodity_ID` | `INTEGER` | USDA commodity identifier. | Retained for source traceability. |
| `Domain` | `TEXT` | USDA domain, usually `TOTAL`. | Retained for source traceability. |
| `Value` | `INTEGER` | Production amount. | Raw CSV values contain commas; `02_cleaning_transformations.sql` removes commas before casting. |

### `cheese_production`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `Year` | `INTEGER` | Production year. | Monthly records are used for annual dashboard totals; `YEAR` records are excluded from the dashboard export. |
| `Period` | `TEXT` | Month abbreviation or `YEAR`. | Used to separate monthly and annual records. |
| `Geo_Level` | `TEXT` | USDA geographic level, usually `STATE`. | Retained for source traceability. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Blank codes are excluded from state-level analysis. |
| `Commodity_ID` | `INTEGER` | USDA commodity identifier. | Retained for source traceability. |
| `Domain` | `TEXT` | USDA domain, usually `TOTAL`. | Retained for source traceability. |
| `Value` | `INTEGER` | Production amount. | Raw CSV values contain commas; cleaned before numeric analysis. |

### `honey_production`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `Year` | `INTEGER` | Production year. | Annual records only. |
| `Geo_Level` | `TEXT` | USDA geographic level, usually `STATE`. | Retained for source traceability. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Blank codes are excluded from state-level analysis. |
| `Commodity_ID` | `INTEGER` | USDA commodity identifier. | Retained for source traceability. |
| `Value` | `INTEGER` | Production amount. | Raw CSV values contain commas; cleaned before numeric analysis. |

### `coffee_production`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `Year` | `INTEGER` | Production year. | Annual records only in this dataset. |
| `Period` | `TEXT` | Time period, currently `YEAR`. | Retained for consistency with other commodity tables. |
| `Geo_Level` | `TEXT` | USDA geographic level, usually `STATE`. | Retained for source traceability. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Joins to `state_lookup`; coffee coverage is limited to Hawaii. |
| `Commodity_ID` | `INTEGER` | USDA commodity identifier. | Retained for source traceability. |
| `Value` | `INTEGER` | Production amount. | Raw CSV values contain commas; cleaned before numeric analysis. |

### `yogurt_production`

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `Year` | `INTEGER` | Production year. | Annual records only in this dataset. |
| `Period` | `TEXT` | Time period, currently `YEAR`. | Retained for consistency with other commodity tables. |
| `Geo_Level` | `TEXT` | USDA geographic level, usually `STATE`. | Retained for source traceability. |
| `State_ANSI` | `INTEGER` | State ANSI code. | Joins to `state_lookup`. |
| `Commodity_ID` | `INTEGER` | USDA commodity identifier. | Retained for source traceability. |
| `Domain` | `TEXT` | USDA domain, usually `TOTAL`. | Retained for source traceability. |
| `Value` | `INTEGER` | Production amount. | Raw CSV values contain commas; cleaned before numeric analysis. |

## Analysis View

### `commodity_production_long`

Created in [`SQL/02_cleaning_transformations.sql`](../SQL/02_cleaning_transformations.sql).

| Column | Type | Description | Cleaning Notes |
|---|---:|---|---|
| `state` | `TEXT` | State name from `state_lookup`. | Only records that match `state_lookup` are included. |
| `state_ansi` | `INTEGER` | State ANSI join key. | Cast from source values after excluding blanks. |
| `year` | `INTEGER` | Production year. | Standardized across commodity tables. |
| `period` | `TEXT` | Month abbreviation or `YEAR`. | Honey is assigned `YEAR` because its source table has no period column. |
| `commodity` | `TEXT` | Commodity label: `Milk`, `Cheese`, `Honey`, `Coffee`, or `Yogurt`. | Added during long-format consolidation. |
| `production_value` | `REAL` | Numeric production amount. | Commas are removed and values are cast for aggregation. |
| `source_table` | `TEXT` | Original source table name. | Preserves lineage for audit and debugging. |

## Canonical Refreshed Dataset

The current dashboard/model dataset is generated by
[`src/refresh_usda_bulk_data.py`](../src/refresh_usda_bulk_data.py) from USDA
NASS QuickStats public bulk exports.

### `SQL/USDA_production_2023.csv`

| Column | Type | Description |
|---|---:|---|
| `State` | `TEXT` | Uppercase state name shown in dashboard filters and tables. |
| `Year` | `INTEGER` | Annual production year. |
| `commodity` | `TEXT` | Commodity label: `Milk`, `Cheese`, `Honey`, `Coffee`, or `Yogurt`. |
| `total_production` | `REAL` | Annual state-level production in the USDA-reported unit. |

### `data/processed/usda_production_1930_2023_complete.csv`

This audit-rich file preserves the dashboard columns plus `state_ansi`, `unit`,
`short_desc`, `load_time`, `source_file`, and `source`.

## Legacy SQLite Dashboard Export

Created in [`SQL/07_dashboard_export.sql`](../SQL/07_dashboard_export.sql).
This is retained for the SQL portfolio exercises built on the original SQLite
source tables; the refreshed canonical CSV is generated by the bulk refresh
script above.

| Column | Type | Description |
|---|---:|---|
| `State` | `TEXT` | State name shown in the Dash filters and tables. |
| `Year` | `INTEGER` | Annual production year. |
| `commodity` | `TEXT` | Commodity label used for chart colors and filters. |
| `total_production` | `REAL` | Annual production total. |
