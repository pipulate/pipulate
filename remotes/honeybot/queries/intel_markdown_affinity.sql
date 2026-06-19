-- remotes/honeybot/queries/intel_markdown_affinity.sql
-- ============================================================================
-- MARKDOWN AFFINITY RATIO
-- Raw hit counts favor whoever crawls most often, not whoever wants markdown
-- most. This normalizes for that: each agent's markdown-serving requests
-- (anything tagged with the ?src= tracer dye — manifest follow, hyperlink,
-- <link rel>, or content negotiation) as a SHARE of its total traffic.
-- ============================================================================

-- Part 1: HIGHEST AFFINITY (the markdown-hungry agents)
SELECT
    ua.value AS agent,
    SUM(l.count) AS total_requests,
    SUM(CASE WHEN p.value LIKE '%.md?src=%' THEN l.count ELSE 0 END) AS markdown_requests,
    ROUND(
        100.0 * SUM(CASE WHEN p.value LIKE '%.md?src=%' THEN l.count ELSE 0 END)
        / SUM(l.count), 1
    ) AS markdown_affinity_pct
FROM daily_logs l
JOIN user_agents ua ON l.ua_id = ua.id
JOIN paths p ON l.path_id = p.id
GROUP BY ua.id
HAVING total_requests >= 20
ORDER BY markdown_affinity_pct DESC, total_requests DESC
LIMIT 25;

-- Part 2: LOWEST AFFINITY (high-volume crawlers that ignore markdown)
SELECT
    ua.value AS agent,
    SUM(l.count) AS total_requests,
    SUM(CASE WHEN p.value LIKE '%.md?src=%' THEN l.count ELSE 0 END) AS markdown_requests,
    ROUND(
        100.0 * SUM(CASE WHEN p.value LIKE '%.md?src=%' THEN l.count ELSE 0 END)
        / SUM(l.count), 1
    ) AS markdown_affinity_pct
FROM daily_logs l
JOIN user_agents ua ON l.ua_id = ua.id
JOIN paths p ON l.path_id = p.id
GROUP BY ua.id
HAVING total_requests >= 20
ORDER BY markdown_affinity_pct ASC, total_requests DESC
LIMIT 25;
