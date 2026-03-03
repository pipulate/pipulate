WITH NaughtyIPs AS (
    -- Identify IPs that have probed for known vulnerabilities in the last 7 days
    SELECT DISTINCT l.ip_id
    FROM daily_logs l
    JOIN paths p ON l.path_id = p.id
    WHERE l.status = 404
      AND l.date >= date('now', '-7 days')
      AND (
          p.value LIKE '%.php%' OR 
          p.value LIKE '%wp-%' OR 
          p.value LIKE '%.env%' OR 
          p.value LIKE '%.git%' OR
          p.value LIKE '%/cgi-bin/%' OR
          p.value LIKE '%/admin%'
      )
)
-- Select 404s that did NOT come from the Naughty IPs, isolating structural issues
SELECT 
    p.value as structural_404_path, 
    SUM(l.count) as total_hits,
    COUNT(DISTINCT l.ip_id) as unique_clean_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND l.ip_id NOT IN NaughtyIPs
GROUP BY p.id
HAVING total_hits > 1 -- Filter out single random typos
ORDER BY total_hits DESC
LIMIT 20;