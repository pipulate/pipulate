-- remotes/honeybot/queries/hub_candidates.sql
-- ============================================================================
-- HUB CANDIDATES: THE DESIRE PATHS
-- Isolates high-volume 404s and 301s within /futureproof/ to identify
-- organic demand for new, stable hub pages.
-- ============================================================================

SELECT 
    p.value AS path, 
    l.status,
    SUM(l.count) AS total_hits
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE 
    p.value LIKE '/futureproof/%' 
    AND l.status IN (404, 301)
GROUP BY p.id, l.status
ORDER BY total_hits DESC
LIMIT 100;