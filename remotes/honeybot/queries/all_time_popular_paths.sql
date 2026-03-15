-- remotes/honeybot/queries/all_time_popular_paths.sql
-- ============================================================================
-- ALL-TIME POPULAR PATHS (THE GRAND TOTALS)
-- Pulls the top 2000 most requested paths across all HTTP statuses.
-- ============================================================================

SELECT 
    p.value AS path, 
    SUM(l.count) AS total_hits
FROM daily_logs l
JOIN paths p ON l.path_id = p.id

-- OPTIONAL: Uncomment the block below to filter out the most obvious hostile noise
-- WHERE p.value NOT LIKE '%.php%' 
--   AND p.value NOT LIKE '%wp-%' 
--   AND p.value NOT LIKE '%.env%' 
--   AND p.value NOT LIKE '%.git%'
--   AND p.value NOT LIKE '%/cgi-bin/%'

GROUP BY p.id
ORDER BY total_hits DESC
LIMIT 2000;