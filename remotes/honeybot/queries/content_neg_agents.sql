SELECT 
    CASE
        WHEN ua.value LIKE 'Claude-User (claude-code/%'
        THEN 'Claude-User (claude-code/*; +https://support.anthropic.com/)'
        WHEN ua.value LIKE '%ShapBot/%'
        THEN 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ShapBot/0.1.0 (+https://parallel.ai)'
        WHEN ua.value LIKE '%KeenableBot/%'
        THEN 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; KeenableBot/1.0; +https://keenable.ai/)'
        WHEN ua.value LIKE '%ExaUser/%'
        THEN 'Mozilla/5.0 (compatible; ExaUser/1.0; +https://crawler.exa.ai/exauser)'
        WHEN ua.value LIKE 'axios/%'
        THEN 'axios/* (Node.js HTTP client)'
        WHEN ua.value LIKE '%Googlebot%'
         AND i.value NOT LIKE '66.249.%'
         AND i.value NOT LIKE '64.233.%'
         AND i.value NOT LIKE '72.14.%'
         AND i.value NOT LIKE '74.125.%'
         AND i.value NOT LIKE '108.177.%'
         AND i.value NOT LIKE '142.250.%'
         AND i.value NOT LIKE '142.251.%'
         AND i.value NOT LIKE '172.217.%'
         AND i.value NOT LIKE '173.194.%'
         AND i.value NOT LIKE '192.178.%'
         AND i.value NOT LIKE '207.126.%'
         AND i.value NOT LIKE '209.85.%'
         AND i.value NOT LIKE '216.58.%'
         AND i.value NOT LIKE '216.239.%'
        THEN '[SPOOFED-IP] Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        ELSE ua.value
    END as agent, 
    SUM(t.count) as total_reads
FROM telemetry t
JOIN ips i ON t.ip_id = i.id
JOIN paths p ON t.path_id = p.id
JOIN user_agents ua ON t.ua_id = ua.id
JOIN accept_headers ah ON t.accept_id = ah.id
WHERE t.served_md = 1
  AND ah.value LIKE '%text/markdown%'
  AND p.value LIKE '%src=content_neg%'
  AND i.value NOT LIKE '127.%'
  AND i.value NOT LIKE '10.%'
  AND i.value NOT LIKE '192.168.%'
  AND ua.value NOT LIKE '%Nexus 5X%'
  AND ua.value NOT LIKE '%Google-InspectionTool%'
  AND ua.value NOT LIKE '%Ubuntu%'
  AND ua.value NOT LIKE '%iPad%'
  AND ua.value NOT LIKE 'python-httpx%'
  AND ua.value NOT LIKE 'Go-http-client%'
  AND NOT (
      ua.value LIKE 'Mozilla%'
      AND ua.value NOT LIKE '%compatible%'
      AND ua.value NOT LIKE '%Bot%'
      AND ua.value NOT LIKE '%Spider%'
      AND ua.value NOT LIKE '%Crawler%'
      AND ua.value NOT LIKE '%Claude%'
      AND (
          ua.value LIKE '%Windows NT%' OR
          ua.value LIKE '%Macintosh%' OR
          ua.value LIKE '%X11%' OR
          ua.value LIKE '%iPhone%' OR
          ua.value LIKE '%iPad%' OR
          ua.value LIKE '%Android%'
      )
  )
GROUP BY agent
ORDER BY total_reads DESC;