-- One row per staged application with its bands and dimension keys worked
-- out once. Every dimension except the lender is built from this view, and
-- so is the fact table, so a key can never be computed two different ways.
--
-- Keys are fingerprints of the natural key, so they are stable across rebuilds.
CREATE OR REPLACE VIEW hmda_dw.lar_prepared AS
WITH banded AS (
  SELECT *,
    CASE
      WHEN income IS NULL OR income <= 0 THEN 'Not reported'
      WHEN income < 50  THEN '<$50k'
      WHEN income < 100 THEN '$50k-<$100k'
      WHEN income < 150 THEN '$100k-<$150k'
      WHEN income < 250 THEN '$150k-<$250k'
      ELSE '$250k+'
    END AS income_band,                         -- income is in thousands of dollars
    COALESCE(debt_to_income_ratio, 'Not reported') AS dti_band,   -- banded in Python
    CASE
      WHEN loan_to_value_ratio IS NULL OR loan_to_value_ratio <= 0 THEN 'Not reported'
      WHEN loan_to_value_ratio <= 80 THEN '<=80%'
      WHEN loan_to_value_ratio <= 90 THEN '>80%-90%'
      WHEN loan_to_value_ratio <= 95 THEN '>90%-95%'
      ELSE '>95%'
    END AS ltv_band                             -- 80% is where mortgage insurance starts
  FROM hmda_staging.stg_lar
)
SELECT *,
  FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(census_tract, derived_msa_md))) AS geography_key,
  FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(loan_type, lien_status, derived_dwelling_category)))
    AS product_key,
  FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(action_taken, denial_reason_1))) AS outcome_key,
  FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(income_band, dti_band, ltv_band))) AS profile_key
FROM banded;
