SELECT 
    ua.value as suspicious_agent,
    SUM(logs.count) as total_hits,
    (
        -- Heuristic 1: Suspicious Keywords (+10)
        (CASE WHEN ua.value LIKE '%bot%' 
                OR ua.value LIKE '%crawl%' 
                OR ua.value LIKE '%spider%'
                OR ua.value LIKE '%fetch%'
                OR ua.value LIKE '%scrape%'
                OR ua.value LIKE '%search%'
                OR ua.value LIKE '%preview%'
                OR ua.value LIKE '%monitor%'
                OR ua.value LIKE '%http%'
                OR ua.value LIKE '%python%'
                OR ua.value LIKE '%curl%'
                OR ua.value LIKE '%wget%'
                OR ua.value LIKE '%headless%'
                OR ua.value LIKE '%puppeteer%'
                OR ua.value LIKE '%selenium%' 
              THEN 10 ELSE 0 END) +
        
        -- Heuristic 2: Non-Mozilla Format (+5)
        (CASE WHEN ua.value NOT LIKE '%Mozilla%' THEN 5 ELSE 0 END) +
        
        -- Heuristic 3: High Volume (+2 if over 50 hits)
        (CASE WHEN SUM(logs.count) > 50 THEN 2 ELSE 0 END) +
        
        -- Heuristic 4: "Compatible" but not a standard browser (+5)
        (CASE WHEN ua.value LIKE '%compatible%' 
               AND ua.value LIKE '%Mozilla%'
               AND ua.value NOT LIKE '%Chrome%'
               AND ua.value NOT LIKE '%Safari%'
               AND ua.value NOT LIKE '%Firefox%' 
              THEN 5 ELSE 0 END)
    ) as bot_score

FROM daily_logs logs
JOIN user_agents ua ON logs.ua_id = ua.id
WHERE 
    -- 1. Exclude the "Orange List" (KNOWN BOTS)
    ua.value NOT LIKE '%AhrefsBot%'
    AND ua.value NOT LIKE '%Amazonbot%'
    AND ua.value NOT LIKE '%Applebot%'
    AND ua.value NOT LIKE '%Baiduspider%'
    AND ua.value NOT LIKE '%Bytespider%'
    AND ua.value NOT LIKE '%ChatGPT-User%'
    AND ua.value NOT LIKE '%ClaudeBot%'
    AND ua.value NOT LIKE '%DataForSeoBot%'
    AND ua.value NOT LIKE '%GPTBot%'
    AND ua.value NOT LIKE '%Googlebot%'
    AND ua.value NOT LIKE '%MJ12bot%'
    AND ua.value NOT LIKE '%OAI-SearchBot%'
    AND ua.value NOT LIKE '%Perplexity%'
    AND ua.value NOT LIKE '%PetalBot%'
    AND ua.value NOT LIKE '%PromptingBot%'
    AND ua.value NOT LIKE '%SemrushBot%'
    AND ua.value NOT LIKE '%SeznamBot%'
    AND ua.value NOT LIKE '%TikTokSpider%'
    AND ua.value NOT LIKE '%Yandex%'
    AND ua.value NOT LIKE '%YisouSpider%'
    AND ua.value NOT LIKE '%axios%'
    AND ua.value NOT LIKE '%bingbot%'
    AND ua.value NOT LIKE '%meta-externalagent%'

GROUP BY ua.id
-- Only show things that triggered at least one heuristic rule
HAVING bot_score > 0
ORDER BY bot_score DESC, total_hits DESC
LIMIT 50;
