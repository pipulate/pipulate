-- Replace '%feed.xml%' with whatever file you want to check before running
SELECT 
    ua.value as user_agent, 
    SUM(logs.count) as total_hits
FROM daily_logs logs
JOIN paths p ON logs.path_id = p.id
JOIN user_agents ua ON logs.ua_id = ua.id
WHERE p.value LIKE '%feed.xml%'
GROUP BY ua.id
ORDER BY total_hits DESC
LIMIT 20;