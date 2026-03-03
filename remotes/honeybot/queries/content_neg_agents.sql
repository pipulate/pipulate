SELECT 
    ua.value as agent, 
    SUM(t.count) as total_reads
FROM telemetry t
JOIN paths p ON t.path_id = p.id
JOIN user_agents ua ON t.ua_id = ua.id
WHERE p.value LIKE '%src=content_neg%'
GROUP BY ua.id
ORDER BY total_reads DESC;