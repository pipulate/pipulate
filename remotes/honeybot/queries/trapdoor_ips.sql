SELECT 
    i.value as ip_address, 
    ua.value as agent, 
    SUM(t.count) as triggers
FROM telemetry t
JOIN ips i ON t.ip_id = i.id
JOIN user_agents ua ON t.ua_id = ua.id
JOIN paths p ON t.path_id = p.id
WHERE p.value LIKE '%js_confirm.gif%'
GROUP BY i.id, ua.id
ORDER BY triggers DESC
LIMIT 15;