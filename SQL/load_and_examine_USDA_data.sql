/*
Scenario: 
Data Scientist at USDA (United States Department of Agriculture)

Context: 
You are a Data Scientist working at the USDA. Your department has been tracking the production of 
various agricultural commodities across different states. 

Your datasets include:
`milk_production`, `cheese_production`, `coffee_production`, `honey_production`, `yogurt_production`, 
and a `state_lookup` table. 

The data spans multiple years and states, with varying levels of production for each commodity.
Your manager has requested that you generate insights from this data to aid in future planning and decision-making. 
You'll need to use SQL queries to answer the questions that come up in meetings, reports, or strategic discussions.

Objectives:
- Assess state-by-state production for each commodity.
- Identify trends or anomalies.
- Offer data-backed suggestions for areas that may need more attention.
*/

-- Remove the additional comma characters in the value columns
UPDATE milk_production SET Value = REPLACE(value, ',', '');
UPDATE cheese_production SET Value = REPLACE(value, ',', '');
UPDATE honey_production SET Value = REPLACE(value, ',', '');
UPDATE coffee_production SET Value = REPLACE(value, ',', '');
UPDATE yogurt_production SET Value = REPLACE(value, ',', '');

-- Find the total milk production for the year 2023.
SELECT SUM(Value)
FROM milk_production
WHERE "Year" = 2023

-- Show coffee production data for the year 2015.
SELECT SUM(Value)
FROM coffee_production
WHERE "Year" = 2015

-- Find the average honey production for the year 2022.
SELECT AVG(Value)
FROM honey_production
WHERE "Year" = 2022

-- Get the state names with their corresponding ANSI codes from the state_lookup table.
-- What number is Iowa?
SELECT *
FROM state_lookup
WHERE LOWER(State) = 'iowa'


-- Find the highest yogurt production value for the year 2022.
SELECT MAX(Value), "Year" 
FROM yogurt_production
WHERE "Year" = 2022
GROUP BY "Year" 


-- Find states where both honey and milk were produced in 2022.
-- Extract views of counts of production entries in 2022 by state
CREATE VIEW mp AS
SELECT COUNT(Value)prod, 
State_ANSI, Year
FROM milk_production
WHERE Year = 2022
GROUP BY State_ANSI;

CREATE VIEW hp AS
SELECT COUNT(Value) prod, 
State_ANSI, Year
FROM honey_production
WHERE Year = 2022
GROUP BY State_ANSI;

-- Track whether different states produced both honey and milk in 2022
SELECT CASE 
	WHEN mp.prod > 0 THEN "YES"
	ELSE "NO"
END milk_prod, 
CASE 
	WHEN hp.prod > 0 THEN "YES"
	ELSE "NO"
END honey_prod, sl.State, sl.State_ANSI
FROM state_lookup sl 
LEFT JOIN hp ON sl.State_ANSI = hp.State_ANSI 
LEFT JOIN mp ON sl.State_ANSI = mp.State_ANSI;

-- Drops the views
DROP VIEW IF EXISTS mp;
DROP VIEW IF EXISTS hp;
-- Did State_ANSI "35" produce both honey and milk in 2022? No

-- Find the total yogurt production for states that also produced cheese in 2022.
SELECT SUM(Value)
FROM yogurt_production yp 
WHERE yp."Year" = 2022 AND yp.State_ANSI IN (
SELECT DISTINCT State_ANSI 
FROM cheese_production 
WHERE "Year" = 2022 
)

-- 1. Can you find out the total milk production for 2023? Your manager wants this information for the yearly report.
-- What is the total milk production for 2023?
SELECT SUM(Value)
FROM milk_production
WHERE "Year" = 2023;

-- 2. Which states had cheese production greater than 100 million in April 2023? The Cheese Department wants to focus their marketing efforts there. 
-- California and Wisconsin
-- How many states are there? 2
SELECT sl.State 
FROM state_lookup sl 
WHERE sl.State_ANSI IN (
	SELECT State_ANSI 
	FROM cheese_production
	WHERE "Year" = 2023 AND Period = "APR"
	GROUP BY State_ANSI
	HAVING SUM(Value) > 100000000
)

-- 3.Your manager wants to know how coffee production has changed over the years. 
-- What is the total value of coffee production for 2011? 7600000
SELECT SUM(Value) production, "Year" 
FROM coffee_production
GROUP by "Year" 

-- 4. There's a meeting with the Honey Council next week. Find the average honey production for 2022 so you're prepared.
SELECT AVG(Value) ave_prod, "Year" 
FROM honey_production
WHERE "Year" = 2022

-- 5. The State Relations team wants a list of all states names with their corresponding ANSI codes. Can you generate that list?
-- What is the State_ANSI code for Florida? 12
SELECT *
FROM state_lookup
WHERE State = 'FLORIDA'

-- 6. For a cross-commodity report, can you list all states with their cheese production values, 
-- even if they didn't produce any cheese in April of 2023?
-- What is the total for NEW JERSEY?
SELECT sl.State, SUM(cp.Value)
FROM state_lookup sl 
LEFT JOIN cheese_production cp ON sl.State_ANSI = cp.State_ANSI 
WHERE cp."Year" = 2023 AND cp.Period = "APR" 
GROUP BY sl.State 


-- 7. Can you find the total yogurt production for states in the year 2022 which also have cheese production data from 2023?
-- This will help the Dairy Division in their planning.
SELECT SUM(yp.Value) yogurt_production
FROM yogurt_production yp 
INNER JOIN state_lookup sl ON yp.State_ANSI = sl.State_ANSI 
WHERE yp."Year" = 2022 AND yp.State_ANSI IN ( 
	SELECT DISTINCT State_ANSI 
	FROM cheese_production
	WHERE "Year" = 2023 
)

-- 8. List all states from state_lookup that are missing from milk_production in 2023.
-- How many states are there?
SELECT State
FROM state_lookup 
WHERE State_ANSI NOT IN (
	SELECT DISTINCT State_ANSI 
	FROM milk_production
	WHERE "Year" = 2023
)

-- 9. List all states with their cheese production values, including states that didn't produce any cheese in April 2023.
-- Did Delaware produce any cheese in April 2023? No
SELECT sl.State , CASE 
	WHEN cp.Value IS NULL THEN 0
	ELSE SUM(cp.Value)
END cheese_production
FROM state_lookup sl  LEFT JOIN cheese_production cp ON sl.State_ANSI = cp.State_ANSI 
WHERE (cp."Year" = 2023 AND cp.Period = "APR") OR cp."Year" IS NULL
GROUP BY sl.State 


-- 10. Find the average coffee production for all years where the honey production exceeded 1 million.
SELECT AVG(Value)
FROM coffee_production 
WHERE "Year" IN (
	SELECT "Year" 
	FROM honey_production
	GROUP BY "Year" 
	HAVING SUM(Value) > 1000000
)

-- 11. Total production of milk, cheese, yogurt, honey, and coffee by state and year (UNION ALL)
-- Each row shows one commodity type per state/year combination
SELECT
    sl.State,
    mp.Year,
    'Milk' AS commodity,
    SUM(mp.Value) AS total_production
FROM milk_production mp
JOIN state_lookup sl ON mp.State_ANSI = sl.State_ANSI
WHERE mp.Period <> 'YEAR'
GROUP BY sl.State, mp.Year
UNION ALL
SELECT
    sl.State,
    cp.Year,
    'Cheese' AS commodity,
    SUM(cp.Value) AS total_production
FROM cheese_production cp
JOIN state_lookup sl ON cp.State_ANSI = sl.State_ANSI
WHERE cp.Period <> 'YEAR'
GROUP BY sl.State, cp.Year
UNION ALL
SELECT
    sl.State,
    yp.Year,
    'Yogurt' AS commodity,
    SUM(yp.Value) AS total_production
FROM yogurt_production yp
JOIN state_lookup sl ON yp.State_ANSI = sl.State_ANSI
GROUP BY sl.State, yp.Year
UNION ALL
SELECT
    sl.State,
    hp.Year,
    'Honey' AS commodity,
    SUM(hp.Value) AS total_production
FROM honey_production hp
JOIN state_lookup sl ON hp.State_ANSI = sl.State_ANSI
GROUP BY sl.State, hp.Year
UNION ALL
SELECT
    sl.State,
    cfp.Year,
    'Coffee' AS commodity,
    SUM(cfp.Value) AS total_production
FROM coffee_production cfp
JOIN state_lookup sl ON cfp.State_ANSI = sl.State_ANSI
GROUP BY sl.State, cfp.Year
ORDER BY State, Year, commodity;
-- Save the output to a csv file for further analysis and visualization