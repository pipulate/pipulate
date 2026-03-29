SELECT 
    u.value as user_agent_string,
    p.value as path,
    MIN(l.date) as first_404_seen,
    MAX(l.date) as last_404_seen,
    SUM(l.count) as total_404_hits,
    CAST(julianday(MAX(l.date)) - julianday(MIN(l.date)) AS INTEGER) as days_to_learn
FROM daily_logs l
JOIN user_agents u ON l.ua_id = u.id
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND u.value LIKE '%bot%' -- Broad filter to isolate crawlers
GROUP BY u.id, p.id
HAVING total_404_hits > 5 AND days_to_learn > 0
ORDER BY days_to_learn DESC, total_404_hits DESC
LIMIT 20;