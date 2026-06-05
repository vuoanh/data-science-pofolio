/*
USDA Commodities SQL Portfolio
00_schema.sql

Purpose:
Document the relational structure used by this SQLite project. The source
tables are commodity-specific USDA extracts that join to state_lookup through
State_ANSI. The commodity_production_long view consolidates the sources into a
single analysis surface.

Run this file against a new SQLite database before loading CSVs, or read it as
the schema reference for SQL/project-USDA.sqlite.
*/

PRAGMA foreign_keys = ON;

-- State reference table. State_ANSI is the shared join key.
CREATE TABLE IF NOT EXISTS state_lookup (
    State TEXT NOT NULL,
    State_ANSI INTEGER PRIMARY KEY
);

-- Raw monthly and annual milk production records.
CREATE TABLE IF NOT EXISTS milk_production (
    "Year" INTEGER,
    Period TEXT,
    Geo_Level TEXT,
    State_ANSI INTEGER,
    Commodity_ID INTEGER,
    "Domain" TEXT,
    Value INTEGER
);

-- Raw monthly and annual cheese production records.
CREATE TABLE IF NOT EXISTS cheese_production (
    "Year" INTEGER,
    Period TEXT,
    Geo_Level TEXT,
    State_ANSI INTEGER,
    Commodity_ID INTEGER,
    "Domain" TEXT,
    Value INTEGER
);

-- Raw annual honey production records.
CREATE TABLE IF NOT EXISTS honey_production (
    "Year" INTEGER,
    Geo_Level TEXT,
    State_ANSI INTEGER,
    Commodity_ID INTEGER,
    Value INTEGER
);

-- Raw annual coffee production records.
CREATE TABLE IF NOT EXISTS coffee_production (
    "Year" INTEGER,
    Period TEXT,
    Geo_Level TEXT,
    State_ANSI INTEGER,
    Commodity_ID INTEGER,
    Value INTEGER
);

-- Raw annual yogurt production records.
CREATE TABLE IF NOT EXISTS yogurt_production (
    "Year" INTEGER,
    Period TEXT,
    Geo_Level TEXT,
    State_ANSI INTEGER,
    Commodity_ID INTEGER,
    "Domain" TEXT,
    Value INTEGER
);

-- Indexes support the most common joins, filters, and dashboard exports.
CREATE INDEX IF NOT EXISTS idx_state_lookup_state_ansi
ON state_lookup(State_ANSI);

CREATE INDEX IF NOT EXISTS idx_milk_state_year
ON milk_production(State_ANSI, "Year");

CREATE INDEX IF NOT EXISTS idx_cheese_state_year
ON cheese_production(State_ANSI, "Year");

CREATE INDEX IF NOT EXISTS idx_honey_state_year
ON honey_production(State_ANSI, "Year");

CREATE INDEX IF NOT EXISTS idx_coffee_state_year
ON coffee_production(State_ANSI, "Year");

CREATE INDEX IF NOT EXISTS idx_yogurt_state_year
ON yogurt_production(State_ANSI, "Year");

CREATE INDEX IF NOT EXISTS idx_milk_period_year
ON milk_production(Period, "Year");

CREATE INDEX IF NOT EXISTS idx_cheese_period_year
ON cheese_production(Period, "Year");

-- Long-format analysis view. This view is recreated in
-- 02_cleaning_transformations.sql after cleaning logic is applied.
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
