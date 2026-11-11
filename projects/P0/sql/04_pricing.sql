-- Q4 Pricing: Where do borrowers pay most above the benchmark rate?
-- Meaning:    counties where a competitive rate could win business.
--             rate_spread = loan APR minus the average prime offer rate for a
--             comparable loan, in percentage points.
-- Scope:      conventional loans on site-built homes originated in 2025,
--             counties with 300+.
-- Medians:    exact (PERCENTILE_CONT), so reruns give the same numbers.
--             state_median_spread is the median over every loan in the state,
--             not a median of the county medians.
-- Caveat:     a high spread can also mean riskier borrowers, not only weak
--             competition; read it with the lender count.
WITH loans AS (
  SELECT g.state_name AS state, g.county_name, f.lei, f.rate_spread, f.interest_rate
  FROM hmda_dw.fact_application f
  JOIN hmda_dw.dim_geography g USING (geography_key)
  JOIN hmda_dw.dim_product p   USING (product_key)
  WHERE f.is_originated
    AND p.loan_type_label = 'Conventional'
    AND p.dwelling_label = 'Site-built home'
    AND f.activity_year = 2025
    AND f.rate_spread IS NOT NULL
),
county AS (
  SELECT DISTINCT state, county_name,
    COUNT(*) OVER w AS originations,
    PERCENTILE_CONT(rate_spread, 0.5) OVER w AS median_rate_spread,
    PERCENTILE_CONT(interest_rate, 0.5) OVER w AS median_interest_rate
  FROM loans
  WINDOW w AS (PARTITION BY state, county_name)
),
lenders AS (
  SELECT state, county_name, COUNT(DISTINCT lei) AS active_lenders
  FROM loans
  GROUP BY 1, 2
),
state_median AS (
  SELECT DISTINCT state, PERCENTILE_CONT(rate_spread, 0.5) OVER (PARTITION BY state) AS state_median_spread
  FROM loans
)
SELECT c.state, c.county_name, c.originations,
  ROUND(c.median_rate_spread, 3) AS median_rate_spread,
  ROUND(c.median_interest_rate, 3) AS median_interest_rate,
  l.active_lenders,
  ROUND(s.state_median_spread, 3) AS state_median_spread
FROM county c
JOIN lenders l USING (state, county_name)
JOIN state_median s USING (state)
WHERE c.originations >= 300
ORDER BY median_rate_spread DESC;
