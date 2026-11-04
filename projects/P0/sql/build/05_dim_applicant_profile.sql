-- Who applied, in bands: income x debt-to-income x loan-to-value.
-- The *_order columns sort the bands low to high on charts.
CREATE OR REPLACE TABLE hmda_dw.dim_applicant_profile AS
SELECT DISTINCT
  profile_key,
  income_band,
  CASE income_band
    WHEN '<$50k' THEN 1 WHEN '$50k-<$100k' THEN 2 WHEN '$100k-<$150k' THEN 3
    WHEN '$150k-<$250k' THEN 4 WHEN '$250k+' THEN 5 ELSE 99
  END AS income_band_order,
  dti_band,
  CASE dti_band
    WHEN '<20%' THEN 1 WHEN '20%-<30%' THEN 2 WHEN '30%-<36%' THEN 3 WHEN '36%-<43%' THEN 4
    WHEN '43%-<50%' THEN 5 WHEN '50%-60%' THEN 6 WHEN '>60%' THEN 7 ELSE 99
  END AS dti_band_order,
  ltv_band,
  CASE ltv_band
    WHEN '<=80%' THEN 1 WHEN '>80%-90%' THEN 2 WHEN '>90%-95%' THEN 3 WHEN '>95%' THEN 4 ELSE 99
  END AS ltv_band_order
FROM hmda_dw.lar_prepared;
