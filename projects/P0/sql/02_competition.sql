-- Q2 Competition: How concentrated is each state's market, who are the
--                 largest lenders, and is their grip loosening over time?
-- Meaning:   how hard it would be for a new bank to win share. A market where
--            the top lenders hold little and the leader is slipping is easier
--            to enter than one held by a few big names.
-- Market:    site-built homes only, the market Lakeshore would enter; manufactured
--            homes are a specialist niche (see README, "Manufactured homes").
-- Measures, per state and year:
--   leader share   share held by the #1 lender
--   top-10 share   combined share of the ten largest lenders
--   HHI            sum of squared % shares (0-10,000); the 2023 US merger
--                  guidelines call a market above 1,800 highly concentrated
-- Ranking:   ROW_NUMBER, ties broken by LEI, so "top 10" is always exactly ten
--            lenders and Ohio and North Carolina compare like for like.
-- Lender names: uses the type 2 lender history, so each application is shown
--            under the name its lender filed that year. renamed_since is TRUE
--            only when both names come from the filers file; a year with no
--            filers row (UNKNOWN LENDER) is not a rename. Unknown lenders carry
--            0.08% (2024) and 0.16% (2025) of applications, too few to affect
--            the rankings.
-- size_tier counts a lender's home-purchase applications across both states
--            and all dwelling types, so "National" means large in OH + NC
--            combined, not nationwide.
-- One row per lender, state and year: its apps, its share of that state-year's
-- site-built apps, and its rank. Shares stay unrounded here because HHI squares them.
WITH share AS (
  SELECT
    g.state,
    f.activity_year,
    l.lei,
    l.lender_name,
    l.size_tier,
    l.name_in_filers,
    ROW_NUMBER() OVER (PARTITION BY g.state, f.activity_year ORDER BY COUNT(*) DESC, l.lei) as rank_in_state,
    COUNT(*) as apps,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY g.state, f.activity_year) * 100 as market_share_pct
  FROM hmda_dw.fact_application AS f
  JOIN hmda_dw.dim_geography AS g ON f.geography_key = g.geography_key
  JOIN hmda_dw.dim_lender AS l ON f.lender_key = l.lender_key
  JOIN hmda_dw.dim_product AS p ON f.product_key = p.product_key
  WHERE p.dwelling_label = 'Site-built home'
  GROUP BY g.state, f.activity_year, l.lei, l.lender_name, l.size_tier, l.name_in_filers
),
concentration AS (
  SELECT
    state,
    activity_year,
    COUNT(lei) as lenders,
    MAX(market_share_pct) as leader_share,
    SUM(IF(rank_in_state <= 10, market_share_pct, 0)) as top10_share,
    SUM(POW(market_share_pct, 2)) as hhi

  FROM share
  GROUP BY state, activity_year
)
SELECT
  s.state,
  s.activity_year,
  s.lei,
  s.lender_name,
  s.size_tier,
  s.apps,
  ROUND(s.market_share_pct, 2) as market_share_pct,
  s.rank_in_state,
  ROUND(c.leader_share, 2) as leader_share,
  ROUND(c.top10_share, 2) as top10_share,
  ROUND(c.hhi, 2) as hhi,
  c.lenders,
  l.lender_name as name_today,
  s.name_in_filers AND l.name_in_filers AND s.lender_name != l.lender_name as renamed_since
FROM share AS s
JOIN concentration AS c ON s.state = c.state AND s.activity_year = c.activity_year
JOIN hmda_dw.dim_lender AS l ON s.lei = l.lei AND l.is_current
WHERE s.rank_in_state <= 10
ORDER BY s.state, s.activity_year, s.rank_in_state

