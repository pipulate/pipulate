WITH daily_sessions AS (
    SELECT 
        l.ip_id,
        l.date,
        SUM(CASE WHEN p.value LIKE '%.css' OR p.value LIKE '%.woff2' OR p.value LIKE '%.png' OR p.value LIKE '%.ico' THEN l.count ELSE 0 END) as asset_requests,
        SUM(CASE WHEN p.value NOT LIKE '%.%' OR p.value LIKE '%.html' OR p.value LIKE '%.md' THEN l.count ELSE 0 END) as document_requests
    FROM daily_logs l
    JOIN paths p ON l.path_id = p.id
    GROUP BY l.ip_id, l.date
)
SELECT 
    i.value as ip_address,
    s.document_requests,
    s.asset_requests,
    CASE 
        WHEN s.asset_requests = 0 THEN 'Headless Ghost'
        WHEN s.asset_requests > 0 AND s.asset_requests < 3 THEN 'Partial Renderer'
        ELSE 'Full Simulation'
    END as simulation_score
FROM daily_sessions s
JOIN ips i ON s.ip_id = i.id
WHERE s.document_requests > 0
ORDER BY s.document_requests DESC
LIMIT 20;