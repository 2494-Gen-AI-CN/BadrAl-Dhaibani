-- Q1 Demand: Which counties have the most home-purchase applications,
--            and where is demand growing fastest?
-- Meaning:   the shortlist of counties with enough buyers to build a
--            mortgage book, ranked by size and momentum.
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Years:     compares the first and last year loaded (2023 and 2025).
-- 1,000+ apps in 2025: enough buyers to build a book, and enough that growth % isn't noise
WITH county_apps AS (
  SELECT
    g.county_name,
    g.state_name,
    COUNTIF(f.activity_year = 2023) AS apps_2023,
    COUNTIF(f.activity_year = 2024) AS apps_2024,
    COUNTIF(f.activity_year = 2025) AS apps_2025
  FROM hmda_dw.fact_application AS f
  JOIN hmda_dw.dim_geography AS g ON f.geography_key = g.geography_key
  JOIN hmda_dw.dim_product AS p ON f.product_key = p.product_key
  WHERE p.dwelling_label = 'Site-built home'
  GROUP BY g.county_code, g.county_name, g.state_name
)
SELECT
  county_name,
  state_name,
  apps_2023,
  apps_2024,
  apps_2025,
  ROUND(SAFE_DIVIDE(apps_2025 - apps_2023, apps_2023) * 100, 1) AS growth_pct,
  ROW_NUMBER() OVER (PARTITION BY state_name ORDER BY apps_2025 DESC, county_name) AS rank_in_state
FROM county_apps
WHERE apps_2025 >= 1000
ORDER BY state_name, rank_in_state;
