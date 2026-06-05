/*
USDA Commodities SQL Portfolio
04_cte_analysis.sql

Purpose:
Make multi-step CTE analysis explicit for review. Run
02_cleaning_transformations.sql first to create commodity_production_long.
*/

-- 1. CTE pipeline: annual totals from the cleaned long-format view.
WITH cleaned_records AS (
    SELECT
        state,
        state_ansi,
        year,
        period,
        commodity,
        production_value
    FROM commodity_production_long
    WHERE production_value IS NOT NULL
),
annual_totals AS (
    SELECT
        commodity,
        state,
        year,
        SUM(production_value) AS annual_production
    FROM cleaned_records
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY commodity, state, year
)
SELECT
    commodity,
    state,
    year,
    annual_production
FROM annual_totals
ORDER BY commodity, state, year;

-- 2. CTE pipeline: compare latest-year production to historical average.
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
historical_average AS (
    SELECT
        commodity,
        state,
        AVG(annual_production) AS avg_annual_production
    FROM annual_totals
    GROUP BY commodity, state
),
latest_year AS (
    SELECT commodity, MAX(year) AS year
    FROM annual_totals
    GROUP BY commodity
)
SELECT
    at.commodity,
    at.state,
    at.year,
    at.annual_production,
    ha.avg_annual_production,
    at.annual_production - ha.avg_annual_production AS difference_from_average,
    ROUND(100.0 * (at.annual_production - ha.avg_annual_production) / NULLIF(ha.avg_annual_production, 0), 2) AS percent_from_average
FROM annual_totals at
JOIN latest_year ly
    ON at.commodity = ly.commodity
   AND at.year = ly.year
JOIN historical_average ha
    ON at.commodity = ha.commodity
   AND at.state = ha.state
ORDER BY ABS(percent_from_average) DESC;

-- 3. CTE pipeline: top states for each commodity after applying minimum history.
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
state_history AS (
    SELECT
        commodity,
        state,
        COUNT(DISTINCT year) AS years_observed,
        SUM(annual_production) AS all_time_production
    FROM annual_totals
    GROUP BY commodity, state
    HAVING COUNT(DISTINCT year) >= 10
),
ranked_states AS (
    SELECT
        commodity,
        state,
        years_observed,
        all_time_production,
        RANK() OVER (
            PARTITION BY commodity
            ORDER BY all_time_production DESC
        ) AS all_time_rank
    FROM state_history
)
SELECT
    commodity,
    state,
    years_observed,
    all_time_production,
    all_time_rank
FROM ranked_states
WHERE all_time_rank <= 10
ORDER BY commodity, all_time_rank;

-- 4. CTE pipeline: states with both dairy and non-dairy commodity coverage.
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
state_mix AS (
    SELECT
        state,
        MAX(CASE WHEN commodity IN ('Milk', 'Cheese', 'Yogurt') THEN 1 ELSE 0 END) AS has_dairy,
        MAX(CASE WHEN commodity IN ('Honey', 'Coffee') THEN 1 ELSE 0 END) AS has_non_dairy,
        COUNT(DISTINCT commodity) AS commodity_count,
        SUM(annual_production) AS all_time_production
    FROM annual_totals
    GROUP BY state
)
SELECT
    state,
    commodity_count,
    all_time_production,
    CASE
        WHEN has_dairy = 1 AND has_non_dairy = 1 THEN 'Dairy and non-dairy'
        WHEN has_dairy = 1 THEN 'Dairy only'
        ELSE 'Non-dairy only'
    END AS production_mix
FROM state_mix
ORDER BY commodity_count DESC, all_time_production DESC;

-- 5. CTE pipeline: latest-year market share by commodity and state.
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
latest_totals AS (
    SELECT
        at.commodity,
        at.state,
        at.year,
        at.annual_production
    FROM annual_totals at
    JOIN latest_year ly
        ON at.commodity = ly.commodity
       AND at.year = ly.year
),
commodity_totals AS (
    SELECT
        commodity,
        SUM(annual_production) AS commodity_total
    FROM latest_totals
    GROUP BY commodity
)
SELECT
    lt.commodity,
    lt.year,
    lt.state,
    lt.annual_production,
    ROUND(100.0 * lt.annual_production / NULLIF(ct.commodity_total, 0), 2) AS latest_year_share_percent
FROM latest_totals lt
JOIN commodity_totals ct
    ON lt.commodity = ct.commodity
ORDER BY lt.commodity, latest_year_share_percent DESC;
