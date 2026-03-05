-- remotes/honeybot/queries/hot_404_remaps.sql

WITH NaughtyIPs AS (
    -- Stage 1: The Expanded Trap (Identify hostile IPs)
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
          p.value LIKE '%/admin%' OR
          p.value LIKE '%/.well-known/%' OR
          p.value LIKE '%/uploads/%' OR
          p.value LIKE '%config%' OR
          p.value LIKE '%docker%' OR
          p.value LIKE '%/.aws/%' OR
          p.value LIKE '%.sql' OR
          p.value LIKE '%/.svn/%' OR
          p.value LIKE '%.yml' OR
          p.value LIKE '%.json' OR
          p.value LIKE '%allow_url_include%'
      )
)
-- Stage 2: The Pure Structural Signal
SELECT 
    p.value as structural_404_path, 
    SUM(l.count) as total_hits,
    COUNT(DISTINCT l.ip_id) as unique_clean_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND l.ip_id NOT IN NaughtyIPs
  -- The Double-Tap: Ensure no rogue IBR slips through from clean IPs
  AND p.value NOT LIKE '%.php%' 
  AND p.value NOT LIKE '%wp-%' 
  AND p.value NOT LIKE '%.env%'
  AND p.value NOT LIKE '%/.well-known/%'
  AND p.value NOT LIKE '%/uploads/%'
  AND p.value NOT LIKE '%config%'
  AND p.value NOT LIKE '%docker%'
  AND p.value NOT LIKE '%/.aws/%'
  AND p.value NOT LIKE '%.sql'
  AND p.value NOT LIKE '%/.svn/%'
  AND p.value NOT LIKE '%.yml'
  AND p.value NOT LIKE '%.json'
  AND p.value NOT LIKE '% %'
GROUP BY p.id
HAVING total_hits > 1 
ORDER BY total_hits DESC
LIMIT 250; -- Expanded limit for the AI to process
