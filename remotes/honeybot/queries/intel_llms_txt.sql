-- remotes/honeybot/queries/intel_llms_txt.sql

-- Part 1: THE DISCOVERERS (Who is reading the map?)
-- Identifies which agents are actively checking for your AI manifest.
SELECT 
    'Manifest Reader' as interaction_type,
    ua.value as ai_agent, 
    SUM(l.count) as total_requests,
    COUNT(DISTINCT l.ip_id) as unique_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
JOIN user_agents ua ON l.ua_id = ua.id
WHERE p.value LIKE '%/llms.txt%'
GROUP BY ua.id
ORDER BY total_requests DESC
LIMIT 15;

-- Part 2: THE FOLLOWERS (Who is obeying the map?)
-- Identifies agents hitting content *specifically* because they found the link in llms.txt
SELECT 
    'Manifest Follower' as interaction_type,
    ua.value as ai_agent, 
    SUM(l.count) as total_follows,
    COUNT(DISTINCT l.ip_id) as unique_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
JOIN user_agents ua ON l.ua_id = ua.id
WHERE p.value LIKE '%src=llms.txt%'
GROUP BY ua.id
ORDER BY total_follows DESC
LIMIT 15;

-- Part 3: THE CONTENT DIET (What are they reading from the map?)
-- Shows exactly which articles/endpoints the llms.txt file is successfully funneling traffic toward.
SELECT 
    p.value as mapped_path, 
    SUM(l.count) as total_reads,
    COUNT(DISTINCT l.ua_id) as unique_agent_types,
    COUNT(DISTINCT l.ip_id) as unique_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE p.value LIKE '%src=llms.txt%'
GROUP BY p.id
ORDER BY total_reads DESC
LIMIT 15;
