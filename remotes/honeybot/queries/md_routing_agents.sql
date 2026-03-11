-- ============================================================================
-- THE SEMANTIC DISCOVERY VANGUARD
-- Maps specific User Agents to their Markdown discovery mechanism.
-- Excludes content negotiation to focus on crawler traversal behavior.
-- ============================================================================

SELECT 
    CASE 
        WHEN p.value LIKE '%src=a+href%' THEN 'a+href (Standard Hyperlink)'
        WHEN p.value LIKE '%src=link+rel%' THEN 'link+rel (HTML Head Discovery)'
        WHEN p.value LIKE '%src=llms.txt%' THEN 'llms.txt (Direct Agent Map)'
        ELSE 'Unknown Routing'
    END as ingestion_method,
    ua.value as agent,
    SUM(l.count) as total_reads
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
JOIN user_agents ua ON l.ua_id = ua.id
WHERE p.value LIKE '%.md?src=%'
  AND p.value NOT LIKE '%src=content_neg%' -- Exclude negotiated content
  -- Optional: Filter out known local development/admin IPs if needed
  -- AND l.ip_id NOT IN (SELECT id FROM ips WHERE value = '127.0.0.1')
GROUP BY ingestion_method, ua.id
ORDER BY 
    ingestion_method ASC, 
    total_reads DESC;