-- Q7 Geography: Where are each state's home buyers concentrated, and how much of
--               the market could five counties reach?
-- Meaning:   how far a five-county start would reach, and whether those counties sit
--            in one or two metros or are spread across the state. One row per county,
--            2025 applications, for the side-by-side county map.
-- Market:    site-built homes only, as in 01_demand.sql.
-- Every county is kept (no 1,000-app floor): the map shades all of them.
-- county_code is the 5-digit FIPS code, which joins to the Census shapefile's GEOID.
SELECT
  g.county_code,
  g.county_name,
  g.state_name,
  COUNT(*) AS apps_2025
FROM hmda_dw.fact_application AS f
JOIN hmda_dw.dim_geography AS g ON f.geography_key = g.geography_key
JOIN hmda_dw.dim_product AS p ON f.product_key = p.product_key
WHERE p.dwelling_label = 'Site-built home'
  AND f.activity_year = 2025
GROUP BY g.county_code, g.county_name, g.state_name
ORDER BY g.state_name, apps_2025 DESC;
