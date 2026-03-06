-- ============================================================================
-- PROMPT FU: SEMANTIC ROUTER
-- ============================================================================
-- System Directive: Semantic Router (CSV Output ONLY)
-- You are a deterministic semantic routing engine. Your only job is to map the 
-- dead URLs in LIST A (this data) to the living URLs in the INTERLEAVED SEMANTIC MAP.
-- Rules:
-- 1. Analyze the keywords, sub-topics, and summaries in the semantic map to find the best conceptual fit for each 404 path.
-- 2. You must output a strict, two-column CSV format.
-- 3. Column 1: The dead URL from List A.
-- 4. Column 2: The matched living URL from the semantic map.
-- 5. DO NOT include headers, markdown formatting, or Nginx syntax.
-- 6. Output ONLY the raw comma-separated values.
-- Example Output: /2012/07/old-article/,/futureproof/new-concept/
-- ============================================================================

WITH NaughtyIPs AS (
    -- The Script-Kiddie Quarantine
    SELECT DISTINCT l.ip_id
    FROM daily_logs l
    JOIN paths p ON l.path_id = p.id
    WHERE l.status = 404
      AND l.date >= date('now', '-7 days')
      AND (
          p.value LIKE '%.php%' OR 
          p.value LIKE '%wp-%' OR 
          p.value LIKE '%.env%' OR 
          p.value LIKE '%.git%' OR
          p.value LIKE '%/cgi-bin/%' OR
          p.value LIKE '%/admin%'
      )
)
-- The High-Value Structural Signal (The Head of the Curve)
SELECT 
    p.value as structural_404_path, 
    SUM(l.count) as total_hits,
    COUNT(DISTINCT l.ip_id) as unique_clean_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND l.ip_id NOT IN NaughtyIPs
  -- Upstream Length Filter: Block excessively long bot payloads
  AND LENGTH(p.value) <= 150
  -- Artifact Filter: Ignore malformed Jupyter/WordPress media paths
  AND p.value NOT LIKE '%attachment%id%'
  -- The 80/20 Encoding Filter: Drop URL-encoded noise (assumes canonical exists)
  AND instr(p.value, '%') = 0
GROUP BY p.id
HAVING total_hits > 1 
ORDER BY total_hits DESC
LIMIT 250; -- THE CHOKEPOINT: Adjust this value to control the payload
