-- What was applied for: loan type x lien x dwelling, with plain labels.
CREATE OR REPLACE TABLE hmda_dw.dim_product AS
SELECT DISTINCT
  product_key,
  loan_type,
  CASE loan_type
    WHEN 1 THEN 'Conventional' WHEN 2 THEN 'FHA' WHEN 3 THEN 'VA' WHEN 4 THEN 'USDA'
  END AS loan_type_label,
  lien_status,
  CASE lien_status WHEN 1 THEN 'First lien' WHEN 2 THEN 'Subordinate lien' END AS lien_label,
  derived_dwelling_category,
  CASE
    WHEN ENDS_WITH(derived_dwelling_category, 'Site-Built')   THEN 'Site-built home'
    WHEN ENDS_WITH(derived_dwelling_category, 'Manufactured') THEN 'Manufactured home'
    ELSE derived_dwelling_category
  END AS dwelling_label
FROM hmda_dw.lar_prepared;
