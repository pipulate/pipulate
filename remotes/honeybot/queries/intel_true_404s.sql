SELECT p.value as missing_path, SUM(l.count) as total
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND p.value NOT LIKE '%.php%'
  AND p.value NOT LIKE '%wp-%'
  AND p.value NOT LIKE '%.env%'
  AND p.value NOT LIKE '%.git%'
GROUP BY p.id
ORDER BY total DESC
LIMIT 20;