-- The warehouse dataset. Every table below is rebuilt whole with
-- CREATE OR REPLACE, so running the build twice gives the same result.
CREATE SCHEMA IF NOT EXISTS hmda_dw OPTIONS (location = 'US');
