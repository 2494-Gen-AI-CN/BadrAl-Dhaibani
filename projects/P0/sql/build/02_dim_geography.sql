-- Where the property is: census tract -> county -> metro area -> state.
-- One row per tract and metro area: the 2024 change to federal metro
-- definitions moved some tracts into a different metro, so a tract can have
-- two rows. County and state never change for a tract.
CREATE OR REPLACE TABLE hmda_dw.dim_geography AS
SELECT DISTINCT
  p.geography_key,
  p.census_tract,
  p.county_code,
  c.countyname AS county_name,
  c.state,
  CASE c.state WHEN 'OH' THEN 'Ohio' WHEN 'NC' THEN 'North Carolina' ELSE c.state END
    AS state_name,
  p.derived_msa_md AS msa_md,
  p.derived_msa_md != '99999' AS in_metro_area  -- 99999 = outside any metro area
FROM hmda_dw.lar_prepared p
JOIN hmda_staging.stg_counties c USING (county_code);
