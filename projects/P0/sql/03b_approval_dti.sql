-- Q3 Approval, by debt load: How does the denial rate change with the
--              borrower's debt-to-income ratio, for each loan product?
-- Meaning:     which borrowers Lakeshore can serve that others turn away, and
--              where each product stops lending (the second Q3 chart).
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Years:   2023-2025 pooled, both states together.
-- Decided = approved or denied; withdrawn and incomplete files are left out.
-- Denial reason: the first reason the lender gave (denial_reason_1).
WITH base AS (
  SELECT p.loan_type_label, a.dti_band, a.dti_band_order, o.primary_denial_reason,
         f.is_denied
  FROM hmda_dw.fact_application f
  JOIN hmda_dw.dim_product p           USING (product_key)
  JOIN hmda_dw.dim_applicant_profile a USING (profile_key)
  JOIN hmda_dw.dim_outcome o           USING (outcome_key)
  WHERE (f.is_approved OR f.is_denied)
    AND p.dwelling_label = 'Site-built home'
),
-- Denials only: the most common reason in each product and band.
reasons AS (
  SELECT loan_type_label, dti_band, primary_denial_reason, COUNT(*) AS denials,
    ROW_NUMBER() OVER (PARTITION BY loan_type_label, dti_band
                       ORDER BY COUNT(*) DESC, primary_denial_reason) AS rn
  FROM base
  WHERE is_denied
  GROUP BY 1, 2, 3
),
cells AS (
  SELECT loan_type_label, dti_band, dti_band_order,
    COUNT(*) AS decided,
    COUNTIF(is_denied) AS denied
  FROM base
  GROUP BY 1, 2, 3
)
SELECT c.loan_type_label, c.dti_band, c.decided,
  ROUND(SAFE_DIVIDE(c.denied, c.decided) * 100, 1) AS denial_rate_pct,
  r.primary_denial_reason AS top_denial_reason,
  ROUND(SAFE_DIVIDE(r.denials, c.denied) * 100, 1) AS top_reason_share_pct
FROM cells c
LEFT JOIN reasons r
  ON r.loan_type_label = c.loan_type_label AND r.dti_band = c.dti_band AND r.rn = 1
ORDER BY c.loan_type_label, c.dti_band_order;
