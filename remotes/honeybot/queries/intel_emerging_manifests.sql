-- remotes/honeybot/queries/intel_emerging_manifests.sql
-- ============================================================================
-- EMERGING MANIFEST INTELLIGENCE
-- Tracks exploration of llms-full.txt and public website agents.md paths
-- ============================================================================

SELECT 
    p.value AS target_path,
    l.status AS http_status,
    ua.value AS crawler_agent,
    SUM(l.count) AS total_probes,
    COUNT(DISTINCT l.ip_id) AS unique_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
JOIN user_agents ua ON l.ua_id = ua.id
WHERE p.value LIKE '%llms-full.txt%' 
   OR p.value LIKE '%agents.md%'
GROUP BY p.value, l.status, ua.id
ORDER BY total_probes DESC;