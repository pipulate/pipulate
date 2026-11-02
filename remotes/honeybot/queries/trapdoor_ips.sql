SELECT 
    COUNT(DISTINCT i.id) as distinct_ips,
    CASE
        WHEN ua.value LIKE '%meta-externalagent%'
        THEN 'meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)'
        WHEN ua.value LIKE '%OAI-SearchBot%'
        THEN 'OAI-SearchBot/1.4 (+https://openai.com/searchbot)'
        WHEN (i.value LIKE '34.%' OR i.value LIKE '35.%' OR i.value LIKE '136.65.%')
         AND ua.value LIKE 'Mozilla%'
         AND ua.value NOT LIKE '%compatible%'
        THEN '[CLOUD-RENDERER] Mozilla/5.0 Chrome/Edge (GCP 34.*/35.* & 136.65.* Stealth Fleet)'
        WHEN ua.value LIKE '%GPTBot%'
        THEN 'GPTBot/1.3 (+https://openai.com/gptbot)'
        WHEN ua.value LIKE '%meta-webindexer%'
        THEN 'meta-webindexer/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)'
        WHEN ua.value LIKE '%Bytespider%'
        THEN 'Bytespider (+https://zhanzhang.toutiao.com/)'
        WHEN ua.value LIKE '%HeadlessChrome%'
        THEN 'HeadlessChrome/* (X11; Linux x86_64)'
        WHEN ua.value LIKE '%TikTokSpider%'
        THEN 'TikTokSpider (+https://bytespider.tiktok.com/)'
        WHEN ua.value LIKE '%ShapBot%'
        THEN 'ShapBot/0.1.0 (+https://parallel.ai)'
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
        THEN '[SPOOFED-IP] Googlebot/2.1 (+http://www.google.com/bot.html)'
        ELSE ua.value
    END as agent, 
    SUM(t.count) as triggers
FROM telemetry t
JOIN ips i ON t.ip_id = i.id
JOIN user_agents ua ON t.ua_id = ua.id
JOIN paths p ON t.path_id = p.id
WHERE p.value LIKE '%js_confirm.gif%'
  -- Self-exclusion belongs BEFORE the LIMIT, not after it.
  AND i.value NOT LIKE '127.%'
  AND i.value NOT LIKE '10.%'
  AND i.value NOT LIKE '192.168.%'
  AND ua.value NOT LIKE '%Ubuntu%'
  AND ua.value NOT LIKE '%iPad%'
GROUP BY agent
ORDER BY triggers DESC
LIMIT 25;
