WITH trapdoor_hitters AS (
    SELECT DISTINCT l.ip_id, l.ua_id 
    FROM daily_logs l
    JOIN paths p ON l.path_id = p.id
    WHERE p.value LIKE '%js_confirm.gif%'
),
markdown_negotiators AS (
    SELECT DISTINCT t.ip_id, t.ua_id 
    FROM telemetry t
    WHERE t.served_md = 1
)
SELECT 
    i.value as ip_address,
    u.value as user_agent_string,
    'Apex Predator' as classification
FROM trapdoor_hitters th
INNER JOIN markdown_negotiators mn ON th.ip_id = mn.ip_id AND th.ua_id = mn.ua_id
JOIN ips i ON th.ip_id = i.id
JOIN user_agents u ON th.ua_id = u.id;