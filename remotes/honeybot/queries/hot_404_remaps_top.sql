WITH NaughtyIPs AS (
    -- The Script-Kiddie Quarantine
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
-- The High-Value Structural Signal (The Head of the Curve)
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
HAVING total_hits > 1 
ORDER BY total_hits DESC
LIMIT 250; -- THE CHOKEPOINT: Adjust this value to control the payload
