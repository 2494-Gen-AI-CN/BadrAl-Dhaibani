-- Correlation: Do counties where buyers stretch further on income see more
--              denials?
-- Meaning:     stretched counties need tighter affordability checks, or
--              products built for higher loan-to-income borrowers.
-- One point per county (2025 decided applications on site-built homes,
-- counties with 300+):
-- median loan-to-income against the share of decisions that were denials.
-- Pearson r for both states together and for each state.
-- Not a cause: HMDA has no credit scores, house prices push up both
-- measures, and product mix (FHA vs conventional) differs by county.
-- With manufactured homes included, r is driven by their share of each county
-- (they are denied about half the time and have low loan-to-income).
WITH county AS (
  SELECT g.state_name AS state, g.county_name,
    APPROX_QUANTILES(f.loan_to_income, 2)[OFFSET(1)] AS median_lti,
    AVG(IF(f.is_denied, 1, 0)) AS denial_rate,
    COUNT(*) AS decided
  FROM hmda_dw.fact_application f
  JOIN hmda_dw.dim_geography g USING (geography_key)
  JOIN hmda_dw.dim_product p   USING (product_key)
  WHERE (f.is_approved OR f.is_denied) AND f.activity_year = 2025
    AND p.dwelling_label = 'Site-built home'
  GROUP BY 1, 2
  HAVING decided >= 300
)
SELECT 'Both states' AS scope, ROUND(CORR(median_lti, denial_rate), 2) AS pearson_r,
  COUNT(*) AS counties
FROM county
UNION ALL
SELECT state, ROUND(CORR(median_lti, denial_rate), 2), COUNT(*)
FROM county
GROUP BY state
ORDER BY scope;
