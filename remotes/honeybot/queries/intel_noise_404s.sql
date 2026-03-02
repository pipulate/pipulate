SELECT p.value as probed_path, SUM(l.count) as total
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND (p.value LIKE '%.php%' OR p.value LIKE '%wp-%' OR p.value LIKE '%.env%')
GROUP BY p.id
ORDER BY total DESC
LIMIT 10;