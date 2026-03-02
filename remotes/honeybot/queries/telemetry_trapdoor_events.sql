SELECT 
    p.value as path, 
    ua.value as user_agent, 
    t.count as hits, 
    t.last_updated
FROM telemetry t
JOIN paths p ON t.path_id = p.id
JOIN user_agents ua ON t.ua_id = ua.id
WHERE t.served_md = 1
ORDER BY t.last_updated DESC
LIMIT 10;