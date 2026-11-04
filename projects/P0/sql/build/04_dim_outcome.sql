-- What happened to the application, and the first reason given for a denial.
-- "Decided" means the lender made a decision: approved or denied. Withdrawn
-- and incomplete files stay out of approval rates.
CREATE OR REPLACE TABLE hmda_dw.dim_outcome AS
SELECT DISTINCT
  outcome_key,
  action_taken,
  CASE action_taken
    WHEN 1 THEN 'Loan originated'
    WHEN 2 THEN 'Approved, not accepted'
    WHEN 3 THEN 'Denied'
    WHEN 4 THEN 'Withdrawn by applicant'
    WHEN 5 THEN 'Closed as incomplete'
  END AS action_label,
  CASE
    WHEN action_taken IN (1, 2) THEN 'Approved'
    WHEN action_taken = 3       THEN 'Denied'
    ELSE 'Not decided'
  END AS decision,
  denial_reason_1,
  CASE denial_reason_1
    WHEN 1  THEN 'Debt-to-income ratio'
    WHEN 2  THEN 'Employment history'
    WHEN 3  THEN 'Credit history'
    WHEN 4  THEN 'Collateral'
    WHEN 5  THEN 'Insufficient cash'
    WHEN 6  THEN 'Unverifiable information'
    WHEN 7  THEN 'Application incomplete'
    WHEN 8  THEN 'Mortgage insurance denied'
    WHEN 9  THEN 'Other'
    WHEN 10 THEN 'Not applicable'
    ELSE 'Not reported'                     -- exempt lenders may leave it blank
  END AS primary_denial_reason
FROM hmda_dw.lar_prepared;
