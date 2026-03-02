SELECT ua.value as agent, SUM(l.count) as total
FROM daily_logs l
JOIN user_agents ua ON l.ua_id = ua.id
WHERE l.date >= date('now', '-7 days') 
  AND ua.value NOT LIKE '%Mozilla%' 
  AND ua.value NOT LIKE '%Chrome%'
  AND ua.value NOT LIKE '%Safari%'
GROUP BY ua.id
ORDER BY total DESC
LIMIT 15;