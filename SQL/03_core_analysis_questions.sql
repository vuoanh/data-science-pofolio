/*
USDA Commodities SQL Portfolio
03_core_analysis_questions.sql

Purpose:
Answer practical business-style questions with readable SQL. Run
02_cleaning_transformations.sql first to create commodity_production_long.
*/

-- 1. Which commodities have the highest total production over the full dataset?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
)
SELECT
    commodity,
    SUM(annual_production) AS all_time_production
FROM annual_totals
GROUP BY commodity
ORDER BY all_time_production DESC;

-- 2. Which states are the top producers by commodity in the latest available year?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
),
latest_year AS (
    SELECT commodity, MAX(year) AS year
    FROM annual_totals
    GROUP BY commodity
),
ranked AS (
    SELECT
        at.commodity,
        at.year,
        at.state,
        at.annual_production,
        RANK() OVER (
            PARTITION BY at.commodity, at.year
            ORDER BY at.annual_production DESC
        ) AS production_rank
    FROM annual_totals at
    JOIN latest_year ly
        ON at.commodity = ly.commodity
       AND at.year = ly.year
)
SELECT
    commodity,
    year,
    state,
    annual_production
FROM ranked
WHERE production_rank = 1
ORDER BY commodity;

-- 3. Which states have the most diverse commodity production profiles?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
)
SELECT
    state,
    COUNT(DISTINCT commodity) AS commodity_count,
    SUM(annual_production) AS all_time_production
FROM annual_totals
GROUP BY state
HAVING COUNT(DISTINCT commodity) >= 4
ORDER BY commodity_count DESC, all_time_production DESC;

-- 4. Which commodities have the widest state coverage?
SELECT
    commodity,
    COUNT(DISTINCT state) AS state_count,
    COUNT(DISTINCT year) AS year_count,
    MIN(year) AS min_year,
    MAX(year) AS max_year
FROM commodity_production_long
GROUP BY commodity
ORDER BY state_count DESC, commodity;

-- 5. Which state-commodity pairs have the highest production in the latest year?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
),
latest_year AS (
    SELECT commodity, MAX(year) AS year
    FROM annual_totals
    GROUP BY commodity
)
SELECT
    at.state,
    at.commodity,
    at.year,
    at.annual_production
FROM annual_totals at
JOIN latest_year ly
    ON at.commodity = ly.commodity
   AND at.year = ly.year
ORDER BY at.annual_production DESC
LIMIT 15;

-- 6. Which states are missing production records for each commodity?
WITH commodities AS (
    SELECT 'Milk' AS commodity
    UNION ALL SELECT 'Cheese'
    UNION ALL SELECT 'Honey'
    UNION ALL SELECT 'Coffee'
    UNION ALL SELECT 'Yogurt'
),
state_commodity AS (
    SELECT DISTINCT commodity, state_ansi
    FROM commodity_production_long
)
SELECT
    c.commodity,
    sl.State AS missing_state
FROM commodities c
CROSS JOIN state_lookup sl
LEFT JOIN state_commodity sc
    ON c.commodity = sc.commodity
   AND sl.State_ANSI = sc.state_ansi
WHERE sc.state_ansi IS NULL
ORDER BY c.commodity, sl.State;

-- 7. Which commodities have grown or declined most from first year to latest year?
WITH national_annual AS (
    SELECT
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, year
),
first_latest AS (
    SELECT
        commodity,
        MIN(year) AS first_year,
        MAX(year) AS latest_year
    FROM national_annual
    GROUP BY commodity
)
SELECT
    fl.commodity,
    fl.first_year,
    first_year.annual_production AS first_year_production,
    fl.latest_year,
    latest_year.annual_production AS latest_year_production,
    latest_year.annual_production - first_year.annual_production AS production_change,
    ROUND(
        100.0 * (latest_year.annual_production - first_year.annual_production)
        / NULLIF(first_year.annual_production, 0),
        2
    ) AS percent_change
FROM first_latest fl
JOIN national_annual first_year
    ON fl.commodity = first_year.commodity
   AND fl.first_year = first_year.year
JOIN national_annual latest_year
    ON fl.commodity = latest_year.commodity
   AND fl.latest_year = latest_year.year
ORDER BY percent_change DESC;

-- 8. Which state-commodity records are high-value outliers within each commodity?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
),
commodity_average AS (
    SELECT
        commodity,
        AVG(annual_production) AS avg_annual_production
    FROM annual_totals
    GROUP BY commodity
)
SELECT
    at.commodity,
    at.state,
    at.year,
    at.annual_production,
    ca.avg_annual_production,
    ROUND(at.annual_production / NULLIF(ca.avg_annual_production, 0), 2) AS multiple_of_average
FROM annual_totals at
JOIN commodity_average ca
    ON at.commodity = ca.commodity
WHERE at.annual_production >= ca.avg_annual_production * 5
ORDER BY multiple_of_average DESC
LIMIT 25;

-- 9. Which commodities are geographically concentrated in a few states?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
),
all_time_state AS (
    SELECT
        commodity,
        state,
        SUM(annual_production) AS state_production
    FROM annual_totals
    GROUP BY commodity, state
),
ranked AS (
    SELECT
        commodity,
        state,
        state_production,
        SUM(state_production) OVER (PARTITION BY commodity) AS commodity_total,
        RANK() OVER (PARTITION BY commodity ORDER BY state_production DESC) AS production_rank
    FROM all_time_state
)
SELECT
    commodity,
    SUM(CASE WHEN production_rank <= 3 THEN state_production ELSE 0 END) AS top_3_production,
    MAX(commodity_total) AS commodity_total,
    ROUND(
        100.0 * SUM(CASE WHEN production_rank <= 3 THEN state_production ELSE 0 END)
        / NULLIF(MAX(commodity_total), 0),
        2
    ) AS top_3_share_percent
FROM ranked
GROUP BY commodity
ORDER BY top_3_share_percent DESC;

-- 10. Which state-commodity pairs should be prioritized for deeper forecasting?
WITH annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
),
coverage AS (
    SELECT
        commodity,
        state,
        COUNT(DISTINCT year) AS years_observed,
        SUM(annual_production) AS all_time_production,
        AVG(annual_production) AS avg_annual_production
    FROM annual_totals
    GROUP BY commodity, state
)
SELECT
    commodity,
    state,
    years_observed,
    all_time_production,
    avg_annual_production,
    CASE
        WHEN years_observed >= 20 AND all_time_production >= 1000000000 THEN 'High priority'
        WHEN years_observed >= 10 AND all_time_production >= 100000000 THEN 'Medium priority'
        ELSE 'Low priority'
    END AS forecasting_priority
FROM coverage
ORDER BY
    CASE forecasting_priority
        WHEN 'High priority' THEN 1
        WHEN 'Medium priority' THEN 2
        ELSE 3
    END,
    all_time_production DESC;
