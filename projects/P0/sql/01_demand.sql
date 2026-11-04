-- Q1 Demand: Which counties have the most home-purchase applications,
--            and where is demand growing fastest?
-- Meaning:   the shortlist of counties with enough buyers to build a
--            mortgage book, ranked by size and momentum.
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Years:     compares the first and last year loaded (2023 and 2025).
SELECT g.state_name AS state, g.county_name,
  COUNTIF(f.activity_year = 2023) AS apps_2023,
  COUNTIF(f.activity_year = 2025) AS apps_2025,
  ROUND(SAFE_DIVIDE(COUNTIF(f.activity_year = 2025) - COUNTIF(f.activity_year = 2023),
                    COUNTIF(f.activity_year = 2023)) * 100, 1) AS growth_pct
FROM hmda_dw.fact_application f
JOIN hmda_dw.dim_geography g USING (geography_key)
JOIN hmda_dw.dim_product p   USING (product_key)
WHERE p.dwelling_label = 'Site-built home'
GROUP BY 1, 2
HAVING apps_2025 >= 1000
ORDER BY apps_2025 DESC;
