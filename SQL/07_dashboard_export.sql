/*
USDA Commodities SQL Portfolio
07_dashboard_export.sql

Purpose:
Generate the legacy SQLite annual production export. Run
02_cleaning_transformations.sql first to create commodity_production_long.

The current canonical dashboard/model CSV is refreshed from USDA QuickStats
bulk exports by src/refresh_usda_bulk_data.py.

Expected dashboard columns:
State, Year, commodity, total_production

From the sqlite3 shell, export the legacy SQLite view with:

.headers on
.mode csv
.once SQL/USDA_production_legacy_sqlite_export.csv
.read SQL/07_dashboard_export.sql
*/

DROP VIEW IF EXISTS dashboard_production_export;

CREATE VIEW dashboard_production_export AS
SELECT
    state AS State,
    year AS Year,
    commodity,
    SUM(production_value) AS total_production
FROM commodity_production_long
WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
   OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
GROUP BY
    state,
    year,
    commodity;

SELECT
    State,
    Year,
    commodity,
    total_production
FROM dashboard_production_export
ORDER BY State, Year, commodity;
