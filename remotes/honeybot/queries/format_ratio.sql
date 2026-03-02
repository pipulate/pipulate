SELECT 
    CASE WHEN served_md = 1 THEN 'Raw Markdown (AI/Bots)' ELSE 'HTML/Other (Humans/Legacy)' END as format_delivered,
    SUM(count) as total_hits,
    ROUND((SUM(count) * 100.0) / (SELECT SUM(count) FROM telemetry), 2) as percentage
FROM telemetry
GROUP BY served_md;