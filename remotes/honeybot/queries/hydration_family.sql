-- hydration_family.sql -- BOTH STRATEGIES, ONE TABLE, ROLLED UP BY FAMILY.
--
-- WHY THE ROLLUP IS MANDATORY AND NOT A REFINEMENT (conviction 2026-07-31):
-- hydration_rate.sql groups by ua_id, and a user agent string is a key the
-- SUBJECT CONTROLS AND REVS. Googlebot ships 20+ distinct strings on this
-- site -- bare 'Googlebot', 'GoogleBot/2.1', -Image, -News, -Video, -Mobile,
-- the classic '+http://www.google.com/bot.html' form, and one Chrome
-- smartphone variant PER RELEASE (117, 125, 126, 141, 143 x2, 144 x2,
-- 145 x2, 146 x3). claude-code ships ~41. Every fragment falls below the
-- html_hits floor individually, so BOTH VANISH from a top-20 that then looks
-- complete and is silently biased toward crawlers with STABLE UA strings.
-- The floor did not fail. The KEY did. See THE CHURNING-KEY RULE.
--
-- THE md COLUMN IS THE POINT. Counting who negotiates markdown and who
-- renders JavaScript in two separate queries invites comparing two lists
-- built from two denominators. One row per family, both columns, and the gap
-- between them is legible without arithmetic.
--
-- READ THE RATES AGAINST THE CEILING, NOT AGAINST 100. hydration_selftest.sql
-- puts a known-JavaScript browser at ~89.9%, and the beacon fires on an 800ms
-- timer -- so it measures "executes JS AND stays 800ms", and an agent's rate
-- divided by ~0.899 is roughly its true render fraction. Run the selftest
-- first; a rate without its ceiling is a number without units.
--
-- LEFT JOINs are load-bearing in both directions: a family with a large
-- denominator and zero triggers is the proof that something does not render,
-- and the key set is the UNION of html and markdown families so an agent that
-- ONLY negotiates markdown cannot be deleted by an inner join.
--
-- CASE NOTE: SQLite LIKE is ASCII-case-insensitive by default, which is why
-- lowercase patterns catch mixed-case UA strings. Ladder order matters --
-- specific before general -- and the two Unclassified buckets are deliberate:
-- a rollup with no residue is a rollup that is hiding something.
WITH families AS (
    SELECT
        ua.id AS ua_id,
        CASE
            WHEN ua.value LIKE '%googlebot%'             THEN 'Googlebot (all variants)'
            WHEN ua.value LIKE '%google-inspectiontool%' THEN 'Google-InspectionTool'
            WHEN ua.value LIKE '%google-extended%'       THEN 'Google-Extended'
            WHEN ua.value LIKE '%gptbot%'                THEN 'GPTBot'
            WHEN ua.value LIKE '%oai-searchbot%'         THEN 'OAI-SearchBot'
            WHEN ua.value LIKE '%chatgpt-user%'          THEN 'ChatGPT-User'
            WHEN ua.value LIKE '%claudebot%'             THEN 'ClaudeBot'
            WHEN ua.value LIKE '%claude-user%'           THEN 'Claude-User (claude-code)'
            WHEN ua.value LIKE '%claude%'                THEN 'Claude* (other)'
            WHEN ua.value LIKE '%perplexity%'            THEN 'PerplexityBot'
            WHEN ua.value LIKE '%bytespider%'            THEN 'Bytespider'
            WHEN ua.value LIKE '%meta-externalagent%'    THEN 'meta-externalagent'
            WHEN ua.value LIKE '%facebookexternalhit%'   THEN 'facebookexternalhit'
            WHEN ua.value LIKE '%bingbot%'               THEN 'bingbot'
            WHEN ua.value LIKE '%amazonbot%'             THEN 'Amazonbot'
            WHEN ua.value LIKE '%applebot%'              THEN 'Applebot'
            WHEN ua.value LIKE '%petalbot%'              THEN 'PetalBot'
            WHEN ua.value LIKE '%yandex%'                THEN 'YandexBot'
            WHEN ua.value LIKE '%ahrefsbot%'             THEN 'AhrefsBot'
            WHEN ua.value LIKE '%semrushbot%'            THEN 'SemrushBot'
            WHEN ua.value LIKE '%barkrowler%'            THEN 'Barkrowler'
            WHEN ua.value LIKE '%duckduckbot%'           THEN 'DuckDuckBot'
            WHEN ua.value LIKE '%llmstxt%'               THEN 'llmstxt-radar'
            WHEN ua.value LIKE 'curl/%'                  THEN 'curl (all versions)'
            WHEN ua.value LIKE 'python-requests/%'       THEN 'python-requests'
            WHEN ua.value LIKE 'wget/%'                  THEN 'wget'
            WHEN ua.value LIKE 'go-http-client%'         THEN 'Go http client'
            WHEN ua.value LIKE 'axios/%'                 THEN 'axios'
            WHEN ua.value = '-'                          THEN '(no UA declared)'
            WHEN ua.value LIKE '%mozilla%'               THEN 'Unclassified browser-shaped UA'
            ELSE 'Unclassified other'
        END AS family
    FROM user_agents ua
),
pages AS (
    SELECT f.family AS family, SUM(t.count) AS html_hits
    FROM telemetry t
    JOIN families f ON t.ua_id  = f.ua_id
    JOIN paths    p ON t.path_id = p.id
    JOIN ips      i ON t.ip_id   = i.id
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
    GROUP BY f.family
),
hydrated AS (
    SELECT f.family AS family, SUM(t.count) AS trapdoor_hits
    FROM telemetry t
    JOIN families f ON t.ua_id  = f.ua_id
    JOIN paths    p ON t.path_id = p.id
    JOIN ips      i ON t.ip_id   = i.id
    WHERE p.value LIKE '%js_confirm.gif%'
      AND i.value NOT LIKE '127.%'
      AND i.value NOT LIKE '10.%'
      AND i.value NOT LIKE '192.168.%'
    GROUP BY f.family
),
negotiated AS (
    SELECT f.family AS family, SUM(t.count) AS md_reads
    FROM telemetry t
    JOIN families f ON t.ua_id = f.ua_id
    JOIN ips      i ON t.ip_id = i.id
    WHERE t.served_md = 1
      AND i.value NOT LIKE '127.%'
      AND i.value NOT LIKE '10.%'
      AND i.value NOT LIKE '192.168.%'
    GROUP BY f.family
),
keys AS (
    SELECT family FROM pages
    UNION
    SELECT family FROM negotiated
)
SELECT
    k.family AS family,
    COALESCE(pg.html_hits, 0) AS html,
    COALESCE(hy.trapdoor_hits, 0) AS triggers,
    CASE WHEN COALESCE(pg.html_hits, 0) > 0
         THEN ROUND(100.0 * COALESCE(hy.trapdoor_hits, 0) / pg.html_hits, 1)
         ELSE NULL END AS pct,
    COALESCE(ng.md_reads, 0) AS md
FROM keys k
LEFT JOIN pages      pg ON pg.family = k.family
LEFT JOIN hydrated   hy ON hy.family = k.family
LEFT JOIN negotiated ng ON ng.family = k.family
WHERE COALESCE(pg.html_hits, 0) >= 20
   OR COALESCE(ng.md_reads, 0) >= 20
ORDER BY COALESCE(pg.html_hits, 0) + COALESCE(ng.md_reads, 0) DESC
LIMIT 25;
