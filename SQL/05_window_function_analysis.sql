/*
USDA Commodities SQL Portfolio
05_window_function_analysis.sql

Purpose:
Show advanced SQL analytics with LAG, moving averages, ranks, percent-of-total,
and volatility logic. Run 02_cleaning_transformations.sql first.
*/

-- 1. Year-over-year production change by state and commodity.
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
yoy AS (
    SELECT
        state,
        commodity,
        year,
        annual_production,
        LAG(annual_production) OVER (
            PARTITION BY state, commodity
            ORDER BY year
        ) AS previous_year_production
    FROM annual_totals
)
SELECT
    state,
    commodity,
    year,
    annual_production,
    previous_year_production,
    ROUND(
        100.0 * (annual_production - previous_year_production)
        / NULLIF(previous_year_production, 0),
        2
    ) AS yoy_percent_change
FROM yoy
ORDER BY commodity, state, year;

-- 2. Rolling 3-year average by state and commodity.
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
    ROUND(
        AVG(annual_production) OVER (
            PARTITION BY state, commodity
            ORDER BY year
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS rolling_3_year_avg
FROM annual_totals
ORDER BY commodity, state, year;

-- 3. Rank states within each commodity and year.
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
    RANK() OVER (
        PARTITION BY commodity, year
        ORDER BY annual_production DESC
    ) AS production_rank,
    DENSE_RANK() OVER (
        PARTITION BY commodity, year
        ORDER BY annual_production DESC
    ) AS dense_production_rank
FROM annual_totals
ORDER BY commodity, year DESC, production_rank;

-- 4. Percent contribution of each state to national commodity total.
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
    SUM(annual_production) OVER (
        PARTITION BY commodity, year
    ) AS national_commodity_total,
    ROUND(
        100.0 * annual_production
        / NULLIF(SUM(annual_production) OVER (PARTITION BY commodity, year), 0),
        2
    ) AS national_share_percent
FROM annual_totals
ORDER BY commodity, year DESC, national_share_percent DESC;

-- 5. Average absolute year-over-year movement as a volatility indicator.
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
yoy AS (
    SELECT
        state,
        commodity,
        year,
        annual_production,
        LAG(annual_production) OVER (
            PARTITION BY state, commodity
            ORDER BY year
        ) AS previous_year_production
    FROM annual_totals
),
yoy_change AS (
    SELECT
        state,
        commodity,
        year,
        ROUND(
            100.0 * (annual_production - previous_year_production)
            / NULLIF(previous_year_production, 0),
            2
        ) AS yoy_percent_change
    FROM yoy
    WHERE previous_year_production IS NOT NULL
)
SELECT
    state,
    commodity,
    COUNT(*) AS yoy_observations,
    ROUND(AVG(ABS(yoy_percent_change)), 2) AS avg_abs_yoy_change
FROM yoy_change
GROUP BY state, commodity
HAVING COUNT(*) >= 5
ORDER BY avg_abs_yoy_change DESC;

-- 6. First and latest production per state-commodity pair using window values.
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
windowed AS (
    SELECT
        state,
        commodity,
        year,
        annual_production,
        FIRST_VALUE(year) OVER (
            PARTITION BY state, commodity
            ORDER BY year
        ) AS first_year,
        FIRST_VALUE(annual_production) OVER (
            PARTITION BY state, commodity
            ORDER BY year
        ) AS first_year_production,
        FIRST_VALUE(year) OVER (
            PARTITION BY state, commodity
            ORDER BY year DESC
        ) AS latest_year,
        FIRST_VALUE(annual_production) OVER (
            PARTITION BY state, commodity
            ORDER BY year DESC
        ) AS latest_year_production
    FROM annual_totals
)
SELECT DISTINCT
    state,
    commodity,
    first_year,
    first_year_production,
    latest_year,
    latest_year_production,
    latest_year_production - first_year_production AS production_change
FROM windowed
ORDER BY ABS(production_change) DESC;
