-- Q4 Pricing: Where do borrowers pay most above the benchmark rate?
-- Meaning:    counties where a competitive rate could win business.
--             rate_spread = loan APR minus the average prime offer rate for a
--             comparable loan, in percentage points.
-- Scope:      conventional loans on site-built homes originated in 2025,
--             counties with 300+.
-- Caveat:     a high spread can also mean riskier borrowers, not only weak
--             competition; read it with the lender count.
SELECT g.state_name AS state, g.county_name,
  COUNT(*) AS originations,
  ROUND(APPROX_QUANTILES(f.rate_spread, 2)[OFFSET(1)], 3) AS median_rate_spread,
  ROUND(APPROX_QUANTILES(f.interest_rate, 2)[OFFSET(1)], 3) AS median_interest_rate,
  COUNT(DISTINCT f.lei) AS active_lenders
FROM hmda_dw.fact_application f
JOIN hmda_dw.dim_geography g USING (geography_key)
JOIN hmda_dw.dim_product p   USING (product_key)
WHERE f.is_originated
  AND p.loan_type_label = 'Conventional'
  AND p.dwelling_label = 'Site-built home'
  AND f.activity_year = 2025
  AND f.rate_spread IS NOT NULL
GROUP BY 1, 2
HAVING originations >= 300
ORDER BY median_rate_spread DESC;
