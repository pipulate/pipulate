-- hydration_rate.sql -- DOM hydration RATE per agent (the denominator query).
--
-- COUNTS ANSWER "how many"; RATES ANSWER "does it at all". An agent absent
-- from the raw trapdoor table either does not execute JavaScript, or was
-- served markdown and never received the pixel. Only triggers over pages that
-- ACTUALLY CARRIED the pixel separates those two worlds -- and separating them
-- is the entire finding, so a query that cannot do it is not worth running.
--
-- BOTH SIDES ARE DRAWN FROM telemetry, NEVER daily_logs. log_request() writes
-- daily_logs unconditionally but writes telemetry only when the Accept header
-- is present (the newer Nginx log format), so daily_logs spans a strictly
-- longer window. Mixing them hands every agent a denominator from more days
-- than its numerator and deflates every rate by an unknown, agent-specific
-- factor -- a plausible small number in both worlds, which is no measurement.
--
-- THE LEFT JOIN IS LOAD-BEARING. The most informative row in this table is an
-- agent with a LARGE denominator and ZERO triggers: that row is the proof that
-- something does not run JavaScript. An inner join deletes exactly those rows
-- and still returns a table that looks entirely reasonable.
--
-- IDENTITY LIVES IN THE TAIL (conviction 2026-07-31, on this file's FIRST
-- flight). The original SELECT rendered SUBSTR(ua.value, 1, 60), and the first
-- sixty characters of a modern bot UA are pure boilerplate: Googlebot, GPTBot,
-- OAI-SearchBot and ChatGPT-User all open with an identical
-- "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; " prefix and
-- diverge only AFTER it. Four distinct ua_ids -- including the single 8.3%
-- hydrator, the most interesting row on the site -- collapsed into one
-- indistinguishable label, and eight of twenty rows became unidentifiable.
-- THE GROUP BY WAS CORRECT AND EVERY NUMBER WAS TRUE; only the RENDER
-- destroyed what the query had already measured, which is why an auditor
-- checking the arithmetic would have found nothing. Cut at 'compatible;'
-- instead, so the name survives and the boilerplate does not.
-- LOWER() is used ONLY for the search: it is length-preserving over ASCII, so
-- the position it returns indexes the ORIGINAL string, and the match survives
-- a "Compatible;" that a case-sensitive INSTR would miss. TRIM absorbs the
-- optional space after the semicolon, so both spellings render identically.
--
-- KNOWN LIMITS, stated so nobody has to rediscover them:
--   * telemetry carries no status column, so 404s and redirects sit in the
--     denominator and depress every rate slightly. Direction known, uniform.
--   * the asset-extension exclusions are a heuristic; a slug containing a
--     literal ".js" would be wrongly dropped. Scan the output once.
--   * agents that fragment across many version strings (claude-code ships
--     ~40) fail the html_hits floor individually despite real aggregate
--     volume. Family rollup is a SEPARATE query, modeled on the CASE ladder
--     in db.py's get_ai_education_status(), not a patch to this one.
--   * THIS TABLE CANNOT TELL YOU WHETHER THE INSTRUMENT WORKS. If a real
--     browser does not hydrate at ~100%, every rate below is suspect and the
--     denominator is contaminated. Run hydration_selftest.sql FIRST; it is
--     the calibration control and it is cheap.
WITH pages AS (
    SELECT t.ua_id AS ua_id, SUM(t.count) AS html_hits
    FROM telemetry t
    JOIN paths p ON t.path_id = p.id
    JOIN ips   i ON t.ip_id   = i.id
    WHERE t.served_md = 0
      AND i.value NOT LIKE '127.%'
      AND i.value NOT LIKE '10.%'
      AND i.value NOT LIKE '192.168.%'
      AND p.value NOT LIKE '%.gif%'
      AND p.value NOT LIKE '%.png%'
      AND p.value NOT LIKE '%.jpg%'
      AND p.value NOT LIKE '%.svg%'
      AND p.value NOT LIKE '%.ico%'
      AND p.value NOT LIKE '%.css%'
      AND p.value NOT LIKE '%.js%'
      AND p.value NOT LIKE '%.xml%'
      AND p.value NOT LIKE '%.txt%'
      AND p.value NOT LIKE '%.md%'
      AND p.value NOT LIKE '%.woff%'
    GROUP BY t.ua_id
),
hydrated AS (
    SELECT t.ua_id AS ua_id, SUM(t.count) AS trapdoor_hits
    FROM telemetry t
    JOIN paths p ON t.path_id = p.id
    JOIN ips   i ON t.ip_id   = i.id
    WHERE p.value LIKE '%js_confirm.gif%'
      AND i.value NOT LIKE '127.%'
      AND i.value NOT LIKE '10.%'
      AND i.value NOT LIKE '192.168.%'
    GROUP BY t.ua_id
)
SELECT
    CASE
        WHEN INSTR(LOWER(ua.value), 'compatible;') > 0
            THEN TRIM(SUBSTR(ua.value, INSTR(LOWER(ua.value), 'compatible;') + 11, 45))
        ELSE SUBSTR(ua.value, 1, 45)
    END AS agent,
    pg.html_hits AS html,
    COALESCE(hy.trapdoor_hits, 0) AS triggers,
    ROUND(100.0 * COALESCE(hy.trapdoor_hits, 0) / pg.html_hits, 1) AS pct
FROM pages pg
JOIN user_agents ua ON pg.ua_id = ua.id
LEFT JOIN hydrated hy ON hy.ua_id = pg.ua_id
-- Floor, not a filter: an agent with 2 HTML hits and 1 trigger reads as 50%
-- and means nothing. Sorted by DENOMINATOR rather than by rate, because
-- sorting by rate puts the noisiest rows on top.
WHERE pg.html_hits >= 20
ORDER BY pg.html_hits DESC
LIMIT 20;
