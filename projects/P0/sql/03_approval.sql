-- Q3 Approval: Why are applications denied, by loan product, and how does
--              that differ between Ohio and North Carolina?
-- Meaning:     which loan products Lakeshore should lead with: how much of each
--              state's demand a product carries, and how often it is turned down.
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Years:   2023-2025 pooled; each state's product mix moves by 3 points or less
--          across the three years, so one figure per product is fair.
-- Decided = approved or denied; withdrawn and incomplete files are left out of
--          denial rates, but counted in each product's share of applications.
-- Denial reason: the first reason the lender gave (denial_reason_1).

-- One row per state and loan type: its applications, its share of the state's
-- applications, and how many were decided and denied.
WITH product_apps AS (
  SELECT
    g.state,
    p.loan_type_label,
    COUNT(*) AS apps,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY g.state) * 100 AS product_share_pct,
    COUNTIF(f.is_approved OR f.is_denied) AS decided,
    COUNTIF(f.is_denied) AS denied
  FROM hmda_dw.fact_application AS f
  JOIN hmda_dw.dim_geography AS g ON f.geography_key = g.geography_key
  JOIN hmda_dw.dim_product AS p ON f.product_key = p.product_key
  WHERE p.dwelling_label = 'Site-built home'
  GROUP BY g.state, p.loan_type_label
),
-- Denials only: how many each reason accounts for, ranked within state and loan type.
reasons AS (
  SELECT
    g.state,
    p.loan_type_label,
    o.primary_denial_reason,
    COUNT(*) AS denials,
    ROW_NUMBER() OVER (PARTITION BY g.state, p.loan_type_label
                       ORDER BY COUNT(*) DESC, o.primary_denial_reason) AS reason_rank
  FROM hmda_dw.fact_application AS f
  JOIN hmda_dw.dim_geography AS g ON f.geography_key = g.geography_key
  JOIN hmda_dw.dim_product AS p ON f.product_key = p.product_key
  JOIN hmda_dw.dim_outcome AS o ON f.outcome_key = o.outcome_key
  WHERE p.dwelling_label = 'Site-built home'
    AND f.is_denied
  GROUP BY g.state, p.loan_type_label, o.primary_denial_reason
)
SELECT
  a.state,
  a.loan_type_label,
  a.apps,
  ROUND(a.product_share_pct, 1) AS product_share_pct,
  a.decided,
  a.denied,
  ROUND(SAFE_DIVIDE(a.denied, a.decided) * 100, 1) AS denial_rate_pct,
  r.primary_denial_reason AS top_denial_reason,
  ROUND(SAFE_DIVIDE(r.denials, a.denied) * 100, 1) AS top_reason_share_pct
FROM product_apps AS a
JOIN reasons AS r
  ON a.state = r.state AND a.loan_type_label = r.loan_type_label AND r.reason_rank = 1
ORDER BY a.state, a.apps DESC
