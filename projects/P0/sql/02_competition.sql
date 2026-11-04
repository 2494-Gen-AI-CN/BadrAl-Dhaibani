-- Q2 Competition: Which lenders hold each market, and how has the field
--                 changed as lenders renamed, merged or changed tier?
-- Meaning:        who Lakeshore would take share from, shown under the name
--                 each lender filed under that year, not only its name today.
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Uses the type 2 lender history: each application joins the lender version
-- valid in its year. renamed_since is only TRUE when both names come from the
-- filers file; a year with no filers row is UNKNOWN, not a rename.
WITH share AS (
  SELECT f.activity_year, g.state_name AS state, l.lei,
    l.lender_name AS name_that_year,
    l.size_tier   AS tier_that_year,
    l.name_in_filers,
    COUNT(*) AS apps,
    ROUND(COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY f.activity_year, g.state_name) * 100, 2)
      AS market_share_pct
  FROM hmda_dw.fact_application f
  JOIN hmda_dw.dim_lender l     USING (lender_key)
  JOIN hmda_dw.dim_geography g  USING (geography_key)
  JOIN hmda_dw.dim_product p    USING (product_key)
  WHERE p.dwelling_label = 'Site-built home'
  GROUP BY 1, 2, 3, 4, 5, 6
)
SELECT s.state, s.activity_year, s.lei, s.name_that_year, s.tier_that_year,
  s.apps, s.market_share_pct,
  cur.lender_name AS name_today,
  s.name_in_filers AND cur.name_in_filers AND s.name_that_year != cur.lender_name
    AS renamed_since
FROM share s
JOIN hmda_dw.dim_lender cur ON cur.lei = s.lei AND cur.is_current
QUALIFY RANK() OVER (PARTITION BY s.activity_year, s.state ORDER BY s.apps DESC) <= 10
ORDER BY s.state, s.activity_year, s.apps DESC;
