-- ua_variants.sql -- FULL user-agent strings for the families that survive
-- hydration_rate.sql's 45-character label, so the collapse is resolved by
-- READING rather than by widening a substring and hoping.
--
-- WHY THIS EXISTS. The SUBSTR fix of 2026-07-31 resolved the four-way
-- boilerplate collapse -- bingbot, Amazonbot, ClaudeBot and GPTBot are now
-- distinct, and GPTBot/1.3 is the 8.3% hydrator -- but left TWO: three
-- meta-externalagent rows of which two render identically, and two PetalBot
-- rows that render identically. Both families differ only in the URL tail,
-- well past character 45.
--
-- THE LESSON, banked in the same breath: fixing the collapse you SAW is not
-- applying THE LAST-INCH RULE. Widening the substring only moves the cut to
-- a different character and buys another turn of the same mistake. Print the
-- strings WHOLE, decide by eye whether these are one crawler or several, and
-- let the ARTICLE aggregate deliberately instead of the RENDER aggregating
-- by accident.
--
-- Googlebot is in the WHERE clause for a different reason: it is ABSENT from
-- hydration_rate.sql's top twenty entirely (its HTML volume is below 5,391)
-- while being the site's single largest markdown negotiator at 283 reads.
-- Whatever variants exist, this file names them.
--
-- No IP, no path, no counts. This query answers exactly one question -- what
-- does this agent actually call itself -- and a query that answers one
-- question is a query whose output you can trust at a glance.
SELECT id, value
FROM user_agents
WHERE value LIKE '%meta-externalagent%'
   OR value LIKE '%PetalBot%'
   OR value LIKE '%Googlebot%'
ORDER BY value
LIMIT 20;
