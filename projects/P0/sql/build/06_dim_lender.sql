-- Type 2 lender dimension: one row per version of a lender.
--
-- Each year's filers file is a snapshot of one name per LEI. A new version
-- opens when the lender's name or size tier differs from its previous year;
-- effective_from / effective_to bound each version and is_current marks the
-- latest.
--
-- Lender years come from the applications, not the filers, so every
-- application finds its lender. A lender with applications but no filers row
-- that year is named 'UNKNOWN LENDER (<lei>)' rather than given a name from
-- another year, which could be wrong; name_in_filers is FALSE on those rows.

-- The filers files are per state, so a lender appears once per state and
-- year. Stop if those rows ever disagree on the name.
ASSERT NOT EXISTS (
  SELECT lei FROM hmda_staging.stg_filers
  GROUP BY lei, period
  HAVING COUNT(DISTINCT UPPER(TRIM(name))) > 1
) AS 'stg_filers has two names for the same lei and year';

CREATE OR REPLACE TABLE hmda_dw.dim_lender AS
WITH apps AS (
  SELECT lei, activity_year AS yr, COUNT(*) AS apps
  FROM hmda_staging.stg_lar
  GROUP BY 1, 2
),
names AS (
  -- normalise before comparing, so spacing or case alone is not a rename
  SELECT lei, period AS yr,
    ANY_VALUE(REGEXP_REPLACE(UPPER(TRIM(name)), r'\s+', ' ')) AS lender_name
  FROM hmda_staging.stg_filers
  GROUP BY 1, 2
),
yearly AS (
  SELECT a.lei, a.yr,
    COALESCE(n.lender_name, CONCAT('UNKNOWN LENDER (', a.lei, ')')) AS lender_name,
    n.lei IS NOT NULL AS name_in_filers,
    -- home-purchase applications across both states that year
    CASE WHEN a.apps >= 2000 THEN 'National'
         WHEN a.apps >= 200  THEN 'Regional'
         ELSE 'Local' END AS size_tier
  FROM apps a
  LEFT JOIN names n USING (lei, yr)
),
flagged AS (
  SELECT *,
    IF(LAG(lender_name || '|' || size_tier) OVER w = lender_name || '|' || size_tier, 0, 1)
      AS is_change
  FROM yearly
  WINDOW w AS (PARTITION BY lei ORDER BY yr)
),
versioned AS (
  SELECT *, SUM(is_change) OVER (PARTITION BY lei ORDER BY yr) AS version
  FROM flagged
),
grouped AS (
  SELECT lei, version,
    ANY_VALUE(lender_name) AS lender_name,
    ANY_VALUE(size_tier) AS size_tier,
    ANY_VALUE(name_in_filers) AS name_in_filers,
    MIN(yr) AS first_yr
  FROM versioned
  GROUP BY lei, version
)
SELECT
  FARM_FINGERPRINT(CONCAT(lei, '-', CAST(version AS STRING))) AS lender_key,
  lei,
  version,
  lender_name,
  size_tier,
  name_in_filers,
  DATE(first_yr, 1, 1) AS effective_from,
  COALESCE(DATE_SUB(DATE(LEAD(first_yr) OVER p, 1, 1), INTERVAL 1 DAY), DATE '9999-12-31')
    AS effective_to,
  LEAD(first_yr) OVER p IS NULL AS is_current
FROM grouped
WINDOW p AS (PARTITION BY lei ORDER BY version);
