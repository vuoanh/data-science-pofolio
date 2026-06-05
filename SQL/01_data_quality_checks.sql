/*
USDA Commodities SQL Portfolio
01_data_quality_checks.sql

Purpose:
Profile source tables before analysis. These checks make missing join keys,
coverage gaps, duplicate records, and suspicious values visible before the
dashboard export is generated.
*/

-- 1. Row counts and year coverage by table.
SELECT
    'milk_production' AS table_name,
    COUNT(*) AS total_rows,
    MIN("Year") AS min_year,
    MAX("Year") AS max_year
FROM milk_production
UNION ALL
SELECT 'cheese_production', COUNT(*), MIN("Year"), MAX("Year")
FROM cheese_production
UNION ALL
SELECT 'honey_production', COUNT(*), MIN("Year"), MAX("Year")
FROM honey_production
UNION ALL
SELECT 'coffee_production', COUNT(*), MIN("Year"), MAX("Year")
FROM coffee_production
UNION ALL
SELECT 'yogurt_production', COUNT(*), MIN("Year"), MAX("Year")
FROM yogurt_production;

-- 2. Blank State_ANSI and blank Value checks. SQLite can store blank strings
-- in integer-affinity columns, so this check handles NULL and blank text.
SELECT
    'milk_production' AS table_name,
    COUNT(*) AS total_rows,
    SUM(CASE WHEN State_ANSI IS NULL OR TRIM(CAST(State_ANSI AS TEXT)) = '' THEN 1 ELSE 0 END) AS blank_state_ansi,
    SUM(CASE WHEN Value IS NULL OR TRIM(CAST(Value AS TEXT)) = '' THEN 1 ELSE 0 END) AS blank_value
FROM milk_production
UNION ALL
SELECT
    'cheese_production',
    COUNT(*),
    SUM(CASE WHEN State_ANSI IS NULL OR TRIM(CAST(State_ANSI AS TEXT)) = '' THEN 1 ELSE 0 END),
    SUM(CASE WHEN Value IS NULL OR TRIM(CAST(Value AS TEXT)) = '' THEN 1 ELSE 0 END)
FROM cheese_production
UNION ALL
SELECT
    'honey_production',
    COUNT(*),
    SUM(CASE WHEN State_ANSI IS NULL OR TRIM(CAST(State_ANSI AS TEXT)) = '' THEN 1 ELSE 0 END),
    SUM(CASE WHEN Value IS NULL OR TRIM(CAST(Value AS TEXT)) = '' THEN 1 ELSE 0 END)
FROM honey_production
UNION ALL
SELECT
    'coffee_production',
    COUNT(*),
    SUM(CASE WHEN State_ANSI IS NULL OR TRIM(CAST(State_ANSI AS TEXT)) = '' THEN 1 ELSE 0 END),
    SUM(CASE WHEN Value IS NULL OR TRIM(CAST(Value AS TEXT)) = '' THEN 1 ELSE 0 END)
FROM coffee_production
UNION ALL
SELECT
    'yogurt_production',
    COUNT(*),
    SUM(CASE WHEN State_ANSI IS NULL OR TRIM(CAST(State_ANSI AS TEXT)) = '' THEN 1 ELSE 0 END),
    SUM(CASE WHEN Value IS NULL OR TRIM(CAST(Value AS TEXT)) = '' THEN 1 ELSE 0 END)
FROM yogurt_production;

-- 3. Source rows that cannot join to the state lookup table.
WITH source_rows AS (
    SELECT 'milk_production' AS table_name, State_ANSI FROM milk_production
    UNION ALL
    SELECT 'cheese_production', State_ANSI FROM cheese_production
    UNION ALL
    SELECT 'honey_production', State_ANSI FROM honey_production
    UNION ALL
    SELECT 'coffee_production', State_ANSI FROM coffee_production
    UNION ALL
    SELECT 'yogurt_production', State_ANSI FROM yogurt_production
)
SELECT
    sr.table_name,
    sr.State_ANSI,
    COUNT(*) AS rows_missing_lookup_match
FROM source_rows sr
LEFT JOIN state_lookup sl
    ON CAST(sr.State_ANSI AS INTEGER) = sl.State_ANSI
WHERE sl.State_ANSI IS NULL
GROUP BY sr.table_name, sr.State_ANSI
ORDER BY sr.table_name, rows_missing_lookup_match DESC;

-- 4. Duplicate state/year/period records in monthly or annual tables.
WITH source_rows AS (
    SELECT 'milk_production' AS table_name, "Year" AS year, Period AS period, State_ANSI FROM milk_production
    UNION ALL
    SELECT 'cheese_production', "Year", Period, State_ANSI FROM cheese_production
    UNION ALL
    SELECT 'honey_production', "Year", 'YEAR', State_ANSI FROM honey_production
    UNION ALL
    SELECT 'coffee_production', "Year", Period, State_ANSI FROM coffee_production
    UNION ALL
    SELECT 'yogurt_production', "Year", Period, State_ANSI FROM yogurt_production
)
SELECT
    table_name,
    year,
    period,
    State_ANSI,
    COUNT(*) AS duplicate_rows
FROM source_rows
GROUP BY table_name, year, period, State_ANSI
HAVING COUNT(*) > 1
ORDER BY duplicate_rows DESC, table_name, year;

-- 5. Non-positive production values should be reviewed before aggregation.
WITH source_rows AS (
    SELECT 'milk_production' AS table_name, "Year" AS year, Period AS period, State_ANSI, Value FROM milk_production
    UNION ALL
    SELECT 'cheese_production', "Year", Period, State_ANSI, Value FROM cheese_production
    UNION ALL
    SELECT 'honey_production', "Year", 'YEAR', State_ANSI, Value FROM honey_production
    UNION ALL
    SELECT 'coffee_production', "Year", Period, State_ANSI, Value FROM coffee_production
    UNION ALL
    SELECT 'yogurt_production', "Year", Period, State_ANSI, Value FROM yogurt_production
)
SELECT
    table_name,
    year,
    period,
    State_ANSI,
    Value
FROM source_rows
WHERE CAST(REPLACE(CAST(Value AS TEXT), ',', '') AS REAL) <= 0
ORDER BY table_name, year, State_ANSI;

-- 6. Commodity coverage by state count and year count.
WITH source_rows AS (
    SELECT 'Milk' AS commodity, "Year" AS year, State_ANSI FROM milk_production
    UNION ALL
    SELECT 'Cheese', "Year", State_ANSI FROM cheese_production
    UNION ALL
    SELECT 'Honey', "Year", State_ANSI FROM honey_production
    UNION ALL
    SELECT 'Coffee', "Year", State_ANSI FROM coffee_production
    UNION ALL
    SELECT 'Yogurt', "Year", State_ANSI FROM yogurt_production
)
SELECT
    commodity,
    COUNT(*) AS rows,
    COUNT(DISTINCT State_ANSI) AS distinct_state_codes,
    COUNT(DISTINCT year) AS distinct_years,
    MIN(year) AS min_year,
    MAX(year) AS max_year
FROM source_rows
GROUP BY commodity
ORDER BY distinct_state_codes DESC, commodity;

-- 7. States in the lookup table with no records for each commodity.
WITH commodities AS (
    SELECT 'Milk' AS commodity
    UNION ALL SELECT 'Cheese'
    UNION ALL SELECT 'Honey'
    UNION ALL SELECT 'Coffee'
    UNION ALL SELECT 'Yogurt'
),
state_commodity_records AS (
    SELECT DISTINCT 'Milk' AS commodity, CAST(State_ANSI AS INTEGER) AS state_ansi FROM milk_production
    UNION ALL
    SELECT DISTINCT 'Cheese', CAST(State_ANSI AS INTEGER) FROM cheese_production
    UNION ALL
    SELECT DISTINCT 'Honey', CAST(State_ANSI AS INTEGER) FROM honey_production
    UNION ALL
    SELECT DISTINCT 'Coffee', CAST(State_ANSI AS INTEGER) FROM coffee_production
    UNION ALL
    SELECT DISTINCT 'Yogurt', CAST(State_ANSI AS INTEGER) FROM yogurt_production
)
SELECT
    c.commodity,
    sl.State AS missing_state
FROM commodities c
CROSS JOIN state_lookup sl
LEFT JOIN state_commodity_records scr
    ON c.commodity = scr.commodity
   AND sl.State_ANSI = scr.state_ansi
WHERE scr.state_ansi IS NULL
ORDER BY c.commodity, sl.State;

-- 8. Annual vs monthly period coverage by commodity.
WITH source_rows AS (
    SELECT 'Milk' AS commodity, Period AS period FROM milk_production
    UNION ALL
    SELECT 'Cheese', Period FROM cheese_production
    UNION ALL
    SELECT 'Honey', 'YEAR' FROM honey_production
    UNION ALL
    SELECT 'Coffee', Period FROM coffee_production
    UNION ALL
    SELECT 'Yogurt', Period FROM yogurt_production
)
SELECT
    commodity,
    period,
    COUNT(*) AS rows
FROM source_rows
GROUP BY commodity, period
ORDER BY commodity, rows DESC;

-- 9. High-level annual totals to catch unusually large or small aggregates.
WITH annual_totals AS (
    SELECT 'Milk' AS commodity, "Year" AS year, SUM(Value) AS total_value
    FROM milk_production
    WHERE Period <> 'YEAR'
    GROUP BY "Year"
    UNION ALL
    SELECT 'Cheese', "Year", SUM(Value)
    FROM cheese_production
    WHERE Period <> 'YEAR'
    GROUP BY "Year"
    UNION ALL
    SELECT 'Honey', "Year", SUM(Value)
    FROM honey_production
    GROUP BY "Year"
    UNION ALL
    SELECT 'Coffee', "Year", SUM(Value)
    FROM coffee_production
    GROUP BY "Year"
    UNION ALL
    SELECT 'Yogurt', "Year", SUM(Value)
    FROM yogurt_production
    GROUP BY "Year"
)
SELECT
    commodity,
    year,
    total_value
FROM annual_totals
WHERE total_value IS NULL OR total_value <= 0
ORDER BY commodity, year;
