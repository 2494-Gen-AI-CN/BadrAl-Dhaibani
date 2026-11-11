-- Load log: How many rows came in, how many were in scope, and how many
--           reached the warehouse?
-- Meaning:  the audit trail behind the warehouse; the TOTAL row gives the
--           counts in the README (2,919,828 read, 1,010,939 in scope,
--           14,542 rejected, 996,397 loaded).
-- Scope:    the latest successful load of each loan (LAR) file; filers and
--           counties files are left out, and skipped reruns are ignored.
WITH latest AS (
  SELECT *
  FROM hmda_staging.load_log
  WHERE status = 'loaded' AND STARTS_WITH(source_name, 'lar_')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY source_name ORDER BY run_id DESC) = 1
)
SELECT IFNULL(source_name, 'TOTAL') AS loan_file,
  SUM(rows_read) AS rows_read,
  SUM(rows_read - rows_filtered) AS in_scope,
  SUM(rows_rejected) AS rejected,
  SUM(rows_loaded) AS loaded
FROM latest
GROUP BY ROLLUP (source_name)
ORDER BY source_name IS NULL, source_name;
