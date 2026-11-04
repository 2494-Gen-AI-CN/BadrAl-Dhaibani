-- One row per home-purchase application in staging.
-- Each application binds to the lender version valid in its year, so market
-- share is reported against the lender as it was, not as it is today.
CREATE OR REPLACE TABLE hmda_dw.fact_application
CLUSTER BY activity_year AS
SELECT
  p.geography_key,
  l.lender_key,
  p.product_key,
  p.outcome_key,
  p.profile_key,
  p.activity_year,
  p.lei,
  p.action_taken IN (1, 2) AS is_approved,      -- originated, or approved but not accepted
  p.action_taken = 3       AS is_denied,
  p.action_taken = 1       AS is_originated,
  p.loan_amount,                                -- rounded to $10,000 bands by HMDA
  p.property_value,
  p.income,                                     -- thousands of dollars
  p.interest_rate,                              -- originated loans only
  p.rate_spread,                                -- APR minus average prime offer rate
  p.loan_term,
  p.loan_to_value_ratio AS combined_loan_to_value_ratio,
  p.loan_to_income,
  p.tract_income_band,
  p.tract_to_msa_income_percentage,
  p.tract_population,
  p.denial_reason_2,
  p.denial_reason_3,
  p.denial_reason_4,
  p.source_name
FROM hmda_dw.lar_prepared p
JOIN hmda_dw.dim_lender l
  ON l.lei = p.lei
 AND DATE(p.activity_year, 1, 1) BETWEEN l.effective_from AND l.effective_to;
