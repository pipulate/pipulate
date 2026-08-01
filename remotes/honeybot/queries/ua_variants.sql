-- ua_variants.sql -- how many distinct UA strings each family ships, and a
-- BOUNDED SAMPLE OF EACH.
--
-- WHY IT IS SHAPED THIS WAY (conviction 2026-07-31, this file's first
-- flight). The original was a single SELECT with ORDER BY value LIMIT 20. In
-- ASCII, 'D' < 'G' < 'M' < 'P' < 'm', so the Googlebot family filled all
-- twenty slots and the sort never reached PetalBot or meta-externalagent --
-- the two families the query was written to resolve. It printed a clean,
-- complete-looking table and answered none of its questions, and it would
-- have printed the SAME table whether meta-externalagent was one crawler or
-- three. A LIMIT is a last-inch transformation like any other.
--
-- THE FIX IS PER-FAMILY BUDGETS, not a bigger LIMIT. A shared cap lets the
-- noisiest family starve the others; a cap per family cannot. Same instinct
-- as the html_hits floor in hydration_rate.sql: bound each row class on its
-- own terms.
--
-- STATEMENT 1 IS THE ANSWER; statement 2 is the detail. "How many variants"
-- is the discriminating question ("one crawler or three?"), and it is a
-- COUNT -- a scalar per row, with no render surface to destroy.
--
-- CASE NOTE, stated rather than assumed: SQLite's LIKE is case-INSENSITIVE
-- for ASCII by default, which is why lowercase patterns catch 'GoogleBot/2.1'
-- and 'Googlebot' alike. Relying on that silently is the CASE-BLIND trap; the
-- patterns are written lowercase deliberately and this comment is the receipt.
SELECT
    CASE
        WHEN value LIKE '%googlebot%'          THEN 'Googlebot'
        WHEN value LIKE '%meta-externalagent%' THEN 'meta-externalagent'
        WHEN value LIKE '%petalbot%'           THEN 'PetalBot'
        WHEN value LIKE '%gptbot%'             THEN 'GPTBot'
        WHEN value LIKE '%claude%'             THEN 'Claude*'
        WHEN value LIKE '%bingbot%'            THEN 'bingbot'
        WHEN value LIKE '%amazonbot%'          THEN 'Amazonbot'
    END AS family,
    COUNT(*) AS variants
FROM user_agents
GROUP BY family
HAVING family IS NOT NULL
ORDER BY variants DESC;
SELECT * FROM (
    SELECT 'meta-externalagent' AS family, id, value FROM user_agents
    WHERE value LIKE '%meta-externalagent%' ORDER BY value LIMIT 6
)
UNION ALL
SELECT * FROM (
    SELECT 'PetalBot' AS family, id, value FROM user_agents
    WHERE value LIKE '%petalbot%' ORDER BY value LIMIT 6
)
UNION ALL
SELECT * FROM (
    SELECT 'GPTBot' AS family, id, value FROM user_agents
    WHERE value LIKE '%gptbot%' ORDER BY value LIMIT 6
)
ORDER BY family, value;
