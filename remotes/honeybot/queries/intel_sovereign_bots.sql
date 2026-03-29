WITH trapdoor_hitters AS (
    SELECT DISTINCT ip_id, ua_id 
    FROM daily_logs 
    WHERE path LIKE '%js_confirm.gif%'
),
markdown_negotiators AS (
    SELECT DISTINCT ip_id, ua_id 
    FROM daily_logs 
    WHERE path LIKE '%.md' OR status = 200 -- Adjust if you track the specific content_neg flag in a separate column
)
SELECT 
    i.ip_address,
    u.user_agent_string,
    'Apex Predator' as classification
FROM trapdoor_hitters t
INNER JOIN markdown_negotiators m ON t.ip_id = m.ip_id
JOIN ips i ON t.ip_id = i.id
JOIN user_agents u ON t.ua_id = u.id;