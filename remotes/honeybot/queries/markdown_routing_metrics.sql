SELECT 
    CASE 
        WHEN p.value LIKE '%src=content_neg%' THEN 'content_neg (HTTP Accept Header)'
        WHEN p.value LIKE '%src=link+rel%' THEN 'link+rel (HTML Head Discovery)'
        WHEN p.value LIKE '%src=llms.txt%' THEN 'llms.txt (Direct Agent Map)'
        WHEN p.value LIKE '%src=a+href%' THEN 'a+href (Standard Hyperlink)'
        ELSE 'Unknown/Unattributed'
    END as ingestion_method,
    SUM(t.count) as total_reads,
    COUNT(DISTINCT t.ip_id) as unique_ips,
    COUNT(DISTINCT t.ua_id) as unique_agents
FROM telemetry t
JOIN paths p ON t.path_id = p.id
WHERE p.value LIKE '%.md?src=%'
GROUP BY ingestion_method
ORDER BY total_reads DESC;