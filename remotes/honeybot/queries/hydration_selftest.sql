-- hydration_selftest.sql -- CALIBRATION CONTROL, and its second flight
-- overturned its own header. Read that as the instrument working, not as a
-- wound: a control whose only possible output is the answer you expected is
-- not a control.
--
-- WHAT IT ACTUALLY FOUND (2026-07-31, grouped by IP *and* user agent). The
-- IP-level 39.8% at 127.0.0.1 was MIXED TRAFFIC, not caching:
--     python-requests/2.32.5     2863 html      0 triggers    0.0%
--     Mozilla/5.0 (X11; rv:146)  2275 html   2046 triggers   89.9%
-- A script carried 56% of the loopback denominator and could never fire the
-- beacon. The browser alone reads 89.9%. The LAN box reads 77.7% and 52.2%
-- across two Chrome builds, with curl/8.18.0 at 0.0% beside them.
--
-- THE CACHING HYPOTHESIS WAS STRUCTURALLY IMPOSSIBLE and this header used to
-- assert it. _layouts/default.html appends a random query string to the
-- beacon URL on every page load, so no browser can ever serve it from cache.
-- The previous header named caching as "the leading explanation" IN THE SAME
-- COMMIT as the query written to discriminate between explanations. Do not
-- write the verdict into the instrument; see THE VERDICT-IN-THE-INSTRUMENT
-- RULE in foo_files.py.
--
-- WHAT THE BEACON ACTUALLY MEASURES, and this is the part that must ride into
-- print: default.html fires the pixel on an 800ms setTimeout, deliberately,
-- to "dodge impatient scrapers." So a nonzero rate proves the agent EXECUTES
-- JAVASCRIPT *AND* REMAINS ON THE PAGE FOR 800ms. That is a narrower and more
-- defensible claim than "runs JS," and it is the leading candidate for the
-- ~10% gap between a real browser and 100%: pages clicked through faster than
-- the timer, plus 404s and redirects sitting in the denominator.
--
-- STANDING CONSEQUENCE FOR hydration_rate.sql AND hydration_family.sql: the
-- ceiling is ~89.9%, not 100%, and every agent rate should be read as a
-- RATIO TO THAT CEILING rather than as an absolute percentage. GPTBot's 8.3%
-- is ~1 page in 11; meta-externalagent's 0.76% is ~1 in 119. Both are
-- SAMPLING, which is the finding.
--
-- LAST-INCH NOTE: SUBSTR(ua.value, 1, 55) truncates. Acceptable HERE and only
-- here, because the question this file asks is "browser or tool," which the
-- first 55 characters answer unambiguously. It would NOT be acceptable in
-- hydration_rate.sql, where identity lives in the tail.
--
-- FLOOR NOTE: html_hits >= 20 drops small per-UA rows, so the per-agent rows
-- for one IP will not sum to that IP's total. That is the floor working, not
-- a join defect.
--
-- Only private and loopback ranges are selected, so nothing here is a third
-- party. Denominator filters are kept CHARACTER-FOR-CHARACTER identical to
-- hydration_rate.sql: a control that filters differently from the instrument
-- it calibrates is not a control.
WITH pages AS (
    SELECT t.ip_id AS ip_id, t.ua_id AS ua_id, SUM(t.count) AS html_hits
    FROM telemetry t
    JOIN paths p ON t.path_id = p.id
    JOIN ips   i ON t.ip_id   = i.id
    WHERE t.served_md = 0
      AND (   i.value LIKE '127.%'
           OR i.value LIKE '10.%'
           OR i.value LIKE '192.168.%')
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
    GROUP BY t.ip_id, t.ua_id
),
hydrated AS (
    SELECT t.ip_id AS ip_id, t.ua_id AS ua_id, SUM(t.count) AS trapdoor_hits
    FROM telemetry t
    JOIN paths p ON t.path_id = p.id
    WHERE p.value LIKE '%js_confirm.gif%'
    GROUP BY t.ip_id, t.ua_id
)
SELECT
    i.value AS ip,
    SUBSTR(ua.value, 1, 55) AS agent,
    pg.html_hits AS html,
    COALESCE(hy.trapdoor_hits, 0) AS triggers,
    ROUND(100.0 * COALESCE(hy.trapdoor_hits, 0) / pg.html_hits, 1) AS pct
FROM pages pg
JOIN ips i ON pg.ip_id = i.id
JOIN user_agents ua ON pg.ua_id = ua.id
LEFT JOIN hydrated hy ON hy.ip_id = pg.ip_id AND hy.ua_id = pg.ua_id
WHERE pg.html_hits >= 20
ORDER BY pg.html_hits DESC
LIMIT 12;
