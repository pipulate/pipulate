SELECT ua.value as agent, SUM(logs.count) as total
FROM daily_logs logs
JOIN user_agents ua ON logs.ua_id = ua.id
JOIN paths p ON logs.path_id = p.id
WHERE p.value LIKE '%js_confirm.gif%'
GROUP BY ua.id
ORDER BY total DESC
LIMIT 15;