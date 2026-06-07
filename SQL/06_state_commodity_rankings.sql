/*
USDA Commodities SQL Portfolio
06_state_commodity_rankings.sql

Purpose:
Show ranking, segmentation, CASE logic, and decision-ready summaries.
Run 02_cleaning_transformations.sql first.
*/

-- 1. Top 10 states by commodity in the latest available year.
WITH annual_totals AS (
    SELECT
        state,
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY state, commodity, year
),
latest_year AS (
    SELECT commodity, MAX(year) AS year
    FROM annual_totals
    GROUP BY commodity
),
ranked AS (
    SELECT
        at.state,
        at.commodity,
        at.year,
        at.annual_production,
        RANK() OVER (
            PARTITION BY at.commodity
            ORDER BY at.annual_production DESC
        ) AS production_rank
    FROM annual_totals at
    JOIN latest_year ly
        ON at.commodity = ly.commodity
       AND at.year = ly.year
)
SELECT
    state,
    commodity,
    year,
    annual_production,
    production_rank
FROM ranked
WHERE production_rank <= 10
ORDER BY commodity, production_rank;

-- 2. Top commodity per state across the full dataset.
WITH annual_totals AS (
    SELECT
        state,
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY state, commodity, year
),
state_commodity_totals AS (
    SELECT
        state,
        commodity,
        SUM(annual_production) AS all_time_production
    FROM annual_totals
    GROUP BY state, commodity
),
ranked AS (
    SELECT
        state,
        commodity,
        all_time_production,
        RANK() OVER (
            PARTITION BY state
            ORDER BY all_time_production DESC
        ) AS commodity_rank
    FROM state_commodity_totals
)
SELECT
    state,
    commodity AS top_commodity,
    all_time_production
FROM ranked
WHERE commodity_rank = 1
ORDER BY all_time_production DESC;

-- 3. Production category bands with CASE logic.
WITH annual_totals AS (
    SELECT
        state,
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY state, commodity, year
)
SELECT
    state,
    commodity,
    year,
    annual_production,
    CASE
        WHEN annual_production >= 1000000000 THEN 'Very high'
        WHEN annual_production >= 100000000 THEN 'High'
        WHEN annual_production >= 10000000 THEN 'Medium'
        ELSE 'Low'
    END AS production_category
FROM annual_totals
ORDER BY annual_production DESC;

-- 4. State specialization score: share of each state's production from its top commodity.
WITH annual_totals AS (
    SELECT
        state,
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY state, commodity, year
),
state_commodity_totals AS (
    SELECT
        state,
        commodity,
        SUM(annual_production) AS commodity_production
    FROM annual_totals
    GROUP BY state, commodity
),
state_totals AS (
    SELECT
        state,
        SUM(commodity_production) AS state_total_production
    FROM state_commodity_totals
    GROUP BY state
),
ranked AS (
    SELECT
        sct.state,
        sct.commodity,
        sct.commodity_production,
        st.state_total_production,
        RANK() OVER (
            PARTITION BY sct.state
            ORDER BY sct.commodity_production DESC
        ) AS commodity_rank
    FROM state_commodity_totals sct
    JOIN state_totals st
        ON sct.state = st.state
)
SELECT
    state,
    commodity AS dominant_commodity,
    commodity_production,
    state_total_production,
    ROUND(100.0 * commodity_production / NULLIF(state_total_production, 0), 2) AS specialization_score_percent,
    CASE
        WHEN 100.0 * commodity_production / NULLIF(state_total_production, 0) >= 90 THEN 'Highly specialized'
        WHEN 100.0 * commodity_production / NULLIF(state_total_production, 0) >= 70 THEN 'Moderately specialized'
        ELSE 'Diversified'
    END AS specialization_category
FROM ranked
WHERE commodity_rank = 1
ORDER BY specialization_score_percent DESC;

-- 5. States with consistently high production across many years.
WITH annual_totals AS (
    SELECT
        state,
        commodity,
        year,
        SUM(production_value) AS annual_production
    FROM commodity_production_long
    WHERE (commodity IN ('Milk', 'Cheese') AND period <> 'YEAR')
       OR (commodity IN ('Honey', 'Coffee', 'Yogurt') AND period = 'YEAR')
    GROUP BY state, commodity, year
),
ranked AS (
    SELECT
        state,
        commodity,
        year,
        annual_production,
        RANK() OVER (
            PARTITION BY commodity, year
            ORDER BY annual_production DESC
        ) AS annual_rank
    FROM annual_totals
)
SELECT
    state,
    commodity,
    COUNT(*) AS top_5_years,
    MIN(year) AS first_top_5_year,
    MAX(year) AS latest_top_5_year
FROM ranked
WHERE annual_rank <= 5
GROUP BY state, commodity
HAVING COUNT(*) >= 10
ORDER BY top_5_years DESC, commodity, state;

-- 6. April 2023 cheese producers above 100 million, a direct business filter.
SELECT
    state AS State,
    SUM(production_value) AS april_2023_cheese_production,
    CASE
        WHEN SUM(production_value) > 200000000 THEN 'National priority'
        WHEN SUM(production_value) > 100000000 THEN 'Regional priority'
        ELSE 'Monitor'
    END AS marketing_priority
FROM commodity_production_long
WHERE commodity = 'Cheese'
  AND year = 2023
  AND period = 'APR'
GROUP BY state
HAVING SUM(production_value) > 100000000
ORDER BY april_2023_cheese_production DESC;
