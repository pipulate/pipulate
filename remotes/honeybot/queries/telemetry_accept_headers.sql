SELECT 
    acc.value as accept_header, 
    SUM(t.count) as total
FROM telemetry t
JOIN accept_headers acc ON t.accept_id = acc.id
GROUP BY acc.id
ORDER BY total DESC
LIMIT 10;