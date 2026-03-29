SELECT 
    u.user_agent_string,
    l.path,
    MIN(datetime(l.timestamp, 'unixepoch')) as first_404_seen,
    MAX(datetime(l.timestamp, 'unixepoch')) as last_404_seen,
    COUNT(*) as total_404_hits,
    CAST((MAX(l.timestamp) - MIN(l.timestamp)) / 86400 AS INTEGER) as days_to_learn
FROM daily_logs l
JOIN user_agents u ON l.ua_id = u.id
WHERE l.status = 404
  AND u.user_agent_string LIKE '%bot%' -- Broad filter to isolate crawlers
GROUP BY u.user_agent_string, l.path
HAVING total_404_hits > 5
ORDER BY days_to_learn DESC, total_404_hits DESC
LIMIT 20;