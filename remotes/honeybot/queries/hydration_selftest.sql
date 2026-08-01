-- hydration_selftest.sql -- CALIBRATION CONTROL. Not a finding, an instrument
-- check, and it must be run BEFORE any number from hydration_rate.sql is
-- quoted anywhere.
--
-- THE PROBLEM IT SETTLES. The trapdoor pixel lives in _layouts/default.html,
-- so any client that RENDERS a page fires it. A real browser should therefore
-- hydrate at close to 100%. On 2026-07-31 the top twenty agents by volume
-- topped out at 8.3% and rows presenting as desktop Chrome came in near 0.6%.
-- Two hypotheses explain that, and they demand OPPOSITE articles:
--   A) The instrument is sound. Then almost all "browser" traffic is crawlers
--      wearing browser UA strings, and even agents that DO render are
--      SAMPLING -- hydrating a fraction of what they fetch, because rendering
--      is the expensive thing. That is a much stronger cost finding.
--   B) The denominator is contaminated. The asset-extension exclusions leak
--      non-page requests, or 404s and redirects inflate it, and every rate in
--      hydration_rate.sql is depressed by an unknown factor.
--
-- THE DISCRIMINATOR IS THE OPERATOR'S OWN BROWSER, which is the one client on
-- this dataset KNOWN to execute JavaScript. Under A it reports ~100% here.
-- Under B it reports a low rate like everything else. Different printouts,
-- therefore a probe rather than a ritual.
--
-- Grouped by IP rather than by user agent, because identity is not in
-- question here -- presence of a known-good renderer is. Only private and
-- loopback ranges are selected, so nothing in this output is a third party.
-- The denominator filters are kept CHARACTER-FOR-CHARACTER identical to
-- hydration_rate.sql on purpose: a control that filters differently from the
-- instrument it calibrates is not a control.
WITH pages AS (
    SELECT t.ip_id AS ip_id, SUM(t.count) AS html_hits
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
    GROUP BY t.ip_id
),
hydrated AS (
    SELECT t.ip_id AS ip_id, SUM(t.count) AS trapdoor_hits
    FROM telemetry t
    JOIN paths p ON t.path_id = p.id
    WHERE p.value LIKE '%js_confirm.gif%'
    GROUP BY t.ip_id
)
SELECT
    i.value AS ip,
    pg.html_hits AS html,
    COALESCE(hy.trapdoor_hits, 0) AS triggers,
    ROUND(100.0 * COALESCE(hy.trapdoor_hits, 0) / pg.html_hits, 1) AS pct
FROM pages pg
JOIN ips i ON pg.ip_id = i.id
LEFT JOIN hydrated hy ON hy.ip_id = pg.ip_id
WHERE pg.html_hits >= 20
ORDER BY pg.html_hits DESC
LIMIT 10;
