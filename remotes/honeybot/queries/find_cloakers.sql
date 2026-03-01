SELECT ua.value, SUM(t.count) as total
FROM telemetry t
JOIN user_agents ua ON t.ua_id = ua.id
WHERE ua.value LIKE '%Mozilla%'
  AND t.served_md = 0
  AND t.path_id NOT IN (SELECT id FROM paths WHERE value LIKE '%js_confirm.gif%')
GROUP BY ua.id
ORDER BY total DESC
LIMIT 5;