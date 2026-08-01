SELECT 
    i.value as ip_address, 
    ua.value as agent, 
    SUM(t.count) as triggers
FROM telemetry t
JOIN ips i ON t.ip_id = i.id
JOIN user_agents ua ON t.ua_id = ua.id
JOIN paths p ON t.path_id = p.id
WHERE p.value LIKE '%js_confirm.gif%'
  -- Self-exclusion belongs BEFORE the LIMIT, not after it. Filtering local
  -- IPs downstream (in awk) discards rows the LIMIT already admitted, so the
  -- sample silently shrinks and rows 16+ never enter -- an undercount whose
  -- size grows with the operator's own browsing.
  AND i.value NOT LIKE '127.%'
  AND i.value NOT LIKE '10.%'
  AND i.value NOT LIKE '192.168.%'
GROUP BY i.id, ua.id
ORDER BY triggers DESC
LIMIT 15;