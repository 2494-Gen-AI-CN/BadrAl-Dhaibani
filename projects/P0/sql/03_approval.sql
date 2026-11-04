-- Q3 Approval: Why are applications denied, and how does it differ by
--              loan product and borrower debt load?
-- Meaning:     which borrowers Lakeshore can serve that others turn away,
--              and which products need the most underwriting care.
-- Market:  site-built homes only, the market Lakeshore would enter; manufactured
--          homes are a specialist niche (see README, "Manufactured homes").
-- Decided = approved or denied; withdrawn and incomplete files are left out.
-- All three years together.
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
reasons AS (
  SELECT loan_type_label, dti_band, primary_denial_reason, COUNT(*) AS denials,
    ROW_NUMBER() OVER (PARTITION BY loan_type_label, dti_band ORDER BY COUNT(*) DESC)
      AS rn
  FROM base WHERE is_denied
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
