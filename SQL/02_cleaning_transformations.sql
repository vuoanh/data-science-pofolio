/*
USDA Commodities SQL Portfolio
02_cleaning_transformations.sql

Purpose:
Apply repeatable cleaning logic and create the long-format analysis view used
by the remaining portfolio SQL files.
*/

-- Remove comma formatting from production values. SQLite will coerce the
-- cleaned text back into numeric values because these columns use integer
-- affinity in the current database.
UPDATE milk_production
SET Value = REPLACE(CAST(Value AS TEXT), ',', '')
WHERE CAST(Value AS TEXT) LIKE '%,%';

UPDATE cheese_production
SET Value = REPLACE(CAST(Value AS TEXT), ',', '')
WHERE CAST(Value AS TEXT) LIKE '%,%';

UPDATE honey_production
SET Value = REPLACE(CAST(Value AS TEXT), ',', '')
WHERE CAST(Value AS TEXT) LIKE '%,%';

UPDATE coffee_production
SET Value = REPLACE(CAST(Value AS TEXT), ',', '')
WHERE CAST(Value AS TEXT) LIKE '%,%';

UPDATE yogurt_production
SET Value = REPLACE(CAST(Value AS TEXT), ',', '')
WHERE CAST(Value AS TEXT) LIKE '%,%';

-- Consolidate commodity-specific source tables into one long-format view.
-- Blank State_ANSI records are excluded because they cannot be attributed to a
-- state in the dashboard or state-level analysis.
DROP VIEW IF EXISTS commodity_production_long;

CREATE VIEW commodity_production_long AS
SELECT
    sl.State AS state,
    CAST(mp.State_ANSI AS INTEGER) AS state_ansi,
    mp."Year" AS year,
    mp.Period AS period,
    'Milk' AS commodity,
    CAST(REPLACE(CAST(mp.Value AS TEXT), ',', '') AS REAL) AS production_value,
    'milk_production' AS source_table
FROM milk_production mp
JOIN state_lookup sl
    ON CAST(mp.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE TRIM(CAST(mp.State_ANSI AS TEXT)) <> ''
UNION ALL
SELECT
    sl.State AS state,
    CAST(cp.State_ANSI AS INTEGER) AS state_ansi,
    cp."Year" AS year,
    cp.Period AS period,
    'Cheese' AS commodity,
    CAST(REPLACE(CAST(cp.Value AS TEXT), ',', '') AS REAL) AS production_value,
    'cheese_production' AS source_table
FROM cheese_production cp
JOIN state_lookup sl
    ON CAST(cp.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE TRIM(CAST(cp.State_ANSI AS TEXT)) <> ''
UNION ALL
SELECT
    sl.State AS state,
    CAST(hp.State_ANSI AS INTEGER) AS state_ansi,
    hp."Year" AS year,
    'YEAR' AS period,
    'Honey' AS commodity,
    CAST(REPLACE(CAST(hp.Value AS TEXT), ',', '') AS REAL) AS production_value,
    'honey_production' AS source_table
FROM honey_production hp
JOIN state_lookup sl
    ON CAST(hp.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE TRIM(CAST(hp.State_ANSI AS TEXT)) <> ''
UNION ALL
SELECT
    sl.State AS state,
    CAST(cfp.State_ANSI AS INTEGER) AS state_ansi,
    cfp."Year" AS year,
    cfp.Period AS period,
    'Coffee' AS commodity,
    CAST(REPLACE(CAST(cfp.Value AS TEXT), ',', '') AS REAL) AS production_value,
    'coffee_production' AS source_table
FROM coffee_production cfp
JOIN state_lookup sl
    ON CAST(cfp.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE TRIM(CAST(cfp.State_ANSI AS TEXT)) <> ''
UNION ALL
SELECT
    sl.State AS state,
    CAST(yp.State_ANSI AS INTEGER) AS state_ansi,
    yp."Year" AS year,
    yp.Period AS period,
    'Yogurt' AS commodity,
    CAST(REPLACE(CAST(yp.Value AS TEXT), ',', '') AS REAL) AS production_value,
    'yogurt_production' AS source_table
FROM yogurt_production yp
JOIN state_lookup sl
    ON CAST(yp.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE TRIM(CAST(yp.State_ANSI AS TEXT)) <> '';

-- Confirm that each commodity is represented in the cleaned long view.
SELECT
    commodity,
    COUNT(*) AS cleaned_rows,
    COUNT(DISTINCT state) AS states,
    MIN(year) AS min_year,
    MAX(year) AS max_year
FROM commodity_production_long
GROUP BY commodity
ORDER BY commodity;
