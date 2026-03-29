WITH session_windows AS (
    SELECT 
        ip_id,
        datetime(timestamp, 'unixepoch', 'start of minute') as session_min,
        SUM(CASE WHEN path LIKE '%.css' OR path LIKE '%.woff2' OR path LIKE '%.png' OR path LIKE '%.ico' THEN 1 ELSE 0 END) as asset_requests,
        SUM(CASE WHEN path NOT LIKE '%.%' OR path LIKE '%.html' OR path LIKE '%.md' THEN 1 ELSE 0 END) as document_requests
    FROM daily_logs
    GROUP BY ip_id, session_min
)
SELECT 
    i.ip_address,
    s.document_requests,
    s.asset_requests,
    CASE 
        WHEN s.asset_requests = 0 THEN 'Headless Ghost'
        WHEN s.asset_requests > 0 AND s.asset_requests < 3 THEN 'Partial Renderer'
        ELSE 'Full Simulation'
    END as simulation_score
FROM session_windows s
JOIN ips i ON s.ip_id = i.id
WHERE s.document_requests > 0
ORDER BY s.document_requests DESC
LIMIT 20;