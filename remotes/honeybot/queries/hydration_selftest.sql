-- hydration_selftest.sql -- CALIBRATION CONTROL, and it has already earned
-- its keep: on 2026-07-31 it returned 39.8% (127.0.0.1) and 63.2%
-- (192.168.1.161) -- neither the ~100% of hypothesis A nor the ~0.6% of
-- hypothesis B. It killed BOTH hypotheses it was written to decide between
-- and named a third, which is the best outcome a control can have.
--
-- WHAT THE MIDDLE MEANS. The pixel fires on render, so a browser should
-- report ~100%. It reported 40%. The instrument is NOT broken: 40% is two
-- orders of magnitude above every crawler row on the site. The denominator
-- is NOT clean either. The leading explanation is HTTP CACHING --
-- js_confirm.gif is ONE FIXED URL, so a browser fetches it once and serves
-- every later page's request from memory or disk WITHOUT touching nginx.
-- The numerator is suppressed by cache hits; the denominator, made of
-- distinct page URLs, is not.
--
-- STANDING CONSEQUENCE FOR EVERY RATE THIS INSTRUMENT PRODUCES, including
-- every row of hydration_rate.sql: the number is a FLOOR, never a
-- measurement.
--   * Nonzero PROVES the agent executes JavaScript.
--   * Zero, over a large denominator, is strong evidence it does not.
--   * The MAGNITUDE is NOT comparable across agents, because two clients
--     with different cache behavior report different rates for identical
--     rendering.
-- Quote the binary. Do not quote the fraction as a fraction.
--
-- THE FORWARD FIX is Cache-Control: no-store on the pixel at the nginx
-- layer -- one location block, no JS change, no query strings, no break in
-- URL shape. It repairs nothing retroactively, so data recorded before it
-- lands stays floor-only forever.
--
-- WHY THIS FILE NOW GROUPS BY USER AGENT TOO. "A browser with a warm cache"
-- and "a browser PLUS a non-JS local client sharing one IP" both print
-- ~40%. That is the discrimination question failing INSIDE the control.
-- Splitting loopback by user agent separates them: one browser UA carrying
-- all the volume means caching, while a curl / python-requests / wget row
-- in the mix means mixed traffic and the browser's true rate is higher than
-- the IP-level number showed.
--
-- LAST-INCH NOTE, stated rather than repeated: SUBSTR(ua.value, 1, 55)
-- truncates. That is acceptable HERE and only here, because the question
-- this file asks is "browser or tool," which the first 55 characters answer
-- unambiguously (Mozilla/5.0 (X11; ... vs curl/8.7.1 vs
-- python-requests/2.31.0). It would NOT be acceptable in hydration_rate.sql,
-- where identity lives in the tail.
--
-- Only private and loopback ranges are selected, so nothing in this output
-- is a third party. The denominator filters are kept CHARACTER-FOR-CHARACTER
-- identical to hydration_rate.sql on purpose: a control that filters
-- differently from the instrument it calibrates is not a control.
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
