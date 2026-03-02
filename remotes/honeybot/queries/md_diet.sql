SELECT 
    p.value as article_path, 
    SUM(t.count) as total_reads
FROM telemetry t
JOIN paths p ON t.path_id = p.id
WHERE t.served_md = 1
GROUP BY p.id
ORDER BY total_reads DESC
LIMIT 15;