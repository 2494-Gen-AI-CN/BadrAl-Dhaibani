-- Q5 Risk: Where do approval rates differ sharply between lower- and
--          higher-income neighbourhoods?
-- Meaning: counties where Lakeshore must plan outreach and monitoring
--          from day one to meet fair-lending expectations.
-- Gap = approval rate in Upper-income tracts minus Low/Moderate-income
-- tracts, in percentage points. An approval gap, not evidence of
-- discrimination: the data cannot show cause. Manufactured homes are left out
-- because they are denied about half the time and cluster in lower-income
-- tracts, which made several counties' gaps look two to three times larger.
-- Scope: 2025 decided applications on site-built homes; counties with 1,000+ decided and at least
-- 100 decided in each of the two bands, so one small band can't drive the gap.
WITH r AS (
  SELECT g.state_name AS state, g.county_name, f.tract_income_band,
    COUNT(*) AS decided,
    AVG(IF(f.is_approved, 1, 0)) AS approval_rate
  FROM hmda_dw.fact_application f
  JOIN hmda_dw.dim_geography g USING (geography_key)
  JOIN hmda_dw.dim_product p   USING (product_key)
  WHERE (f.is_approved OR f.is_denied) AND f.activity_year = 2025
    AND p.dwelling_label = 'Site-built home'
  GROUP BY 1, 2, 3
),
county AS (
  SELECT state, county_name,
    SUM(decided) AS decided,
    SUM(IF(tract_income_band = 'Low/Moderate', decided, 0)) AS decided_low_mod,
    SUM(IF(tract_income_band = 'Upper', decided, 0))        AS decided_upper,
    MAX(IF(tract_income_band = 'Low/Moderate', approval_rate, NULL)) AS approval_low_mod,
    MAX(IF(tract_income_band = 'Upper', approval_rate, NULL))        AS approval_upper
  FROM r
  GROUP BY 1, 2
)
SELECT state, county_name, decided, decided_low_mod, decided_upper,
  ROUND(approval_low_mod * 100, 1) AS approval_low_mod_pct,
  ROUND(approval_upper * 100, 1)   AS approval_upper_pct,
  ROUND((approval_upper - approval_low_mod) * 100, 1) AS approval_gap_pts
FROM county
WHERE decided >= 1000 AND decided_low_mod >= 100 AND decided_upper >= 100
ORDER BY approval_gap_pts DESC;
