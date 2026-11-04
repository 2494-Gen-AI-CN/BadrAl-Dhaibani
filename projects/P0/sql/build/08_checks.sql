-- Build checks: the build stops with an error if any of these fail.

ASSERT (SELECT COUNT(*) FROM hmda_dw.fact_application)
     = (SELECT COUNT(*) FROM hmda_staging.stg_lar)
  AS 'fact_application row count differs from stg_lar';

ASSERT (SELECT COUNT(*) FROM hmda_dw.dim_geography)
     = (SELECT COUNT(DISTINCT geography_key) FROM hmda_dw.dim_geography)
  AS 'dim_geography has a duplicate key';
ASSERT (SELECT COUNT(*) FROM hmda_dw.dim_product)
     = (SELECT COUNT(DISTINCT product_key) FROM hmda_dw.dim_product)
  AS 'dim_product has a duplicate key';
ASSERT (SELECT COUNT(*) FROM hmda_dw.dim_outcome)
     = (SELECT COUNT(DISTINCT outcome_key) FROM hmda_dw.dim_outcome)
  AS 'dim_outcome has a duplicate key';
ASSERT (SELECT COUNT(*) FROM hmda_dw.dim_applicant_profile)
     = (SELECT COUNT(DISTINCT profile_key) FROM hmda_dw.dim_applicant_profile)
  AS 'dim_applicant_profile has a duplicate key';
ASSERT (SELECT COUNT(*) FROM hmda_dw.dim_lender)
     = (SELECT COUNT(DISTINCT lender_key) FROM hmda_dw.dim_lender)
  AS 'dim_lender has a duplicate key';

ASSERT NOT EXISTS (
  SELECT lei FROM hmda_dw.dim_lender GROUP BY lei HAVING COUNTIF(is_current) != 1
) AS 'a lender does not have exactly one current version';

ASSERT NOT EXISTS (
  SELECT 1 FROM hmda_dw.fact_application f
  LEFT JOIN hmda_dw.dim_geography g USING (geography_key)
  LEFT JOIN hmda_dw.dim_product p USING (product_key)
  LEFT JOIN hmda_dw.dim_outcome o USING (outcome_key)
  LEFT JOIN hmda_dw.dim_applicant_profile a USING (profile_key)
  WHERE g.geography_key IS NULL OR p.product_key IS NULL
     OR o.outcome_key IS NULL OR a.profile_key IS NULL
) AS 'fact_application has a key with no dimension row';

ASSERT NOT EXISTS (
  SELECT 1 FROM hmda_dw.dim_product WHERE loan_type_label IS NULL
  UNION ALL SELECT 1 FROM hmda_dw.dim_outcome WHERE action_label IS NULL
  UNION ALL SELECT 1 FROM hmda_dw.dim_geography WHERE county_name IS NULL
) AS 'a code has no label';

SELECT 'fact_application' AS table_name, COUNT(*) AS row_count FROM hmda_dw.fact_application
UNION ALL SELECT 'dim_lender', COUNT(*) FROM hmda_dw.dim_lender
UNION ALL SELECT 'dim_geography', COUNT(*) FROM hmda_dw.dim_geography
UNION ALL SELECT 'dim_product', COUNT(*) FROM hmda_dw.dim_product
UNION ALL SELECT 'dim_outcome', COUNT(*) FROM hmda_dw.dim_outcome
UNION ALL SELECT 'dim_applicant_profile', COUNT(*) FROM hmda_dw.dim_applicant_profile
ORDER BY table_name;
