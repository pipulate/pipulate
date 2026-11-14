-- ============================================================================
-- COMPILED CONTEXT: SEMANTIC ROUTER
-- ============================================================================
-- System Directive: Semantic Router (CSV Output ONLY)
-- Maps legitimate structural 404 paths onto the 28 permanent hubs while
-- excluding hostile exploit scanners, dotfiles, and non-page static metadata.
-- ============================================================================

CREATE TEMP TABLE IF NOT EXISTS exclusions (url TEXT);

WITH NaughtyIPs AS (
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
          p.value LIKE '%/.svn%' OR
          p.value LIKE '%/.hg%' OR
          p.value LIKE '%/api/session/properties%' OR
          p.value LIKE '%/boaform%' OR
          p.value LIKE '%/actuator%' OR
          p.value LIKE '%/phpmyadmin%' OR
          p.value LIKE '%/autodiscover%' OR
          p.value LIKE '%/owa%' OR
          p.value LIKE '%/cgi-bin/%' OR
          p.value LIKE '%/admin%'
      )
)
SELECT
    p.value as structural_404_path,
    SUM(l.count) as total_hits,
    COUNT(DISTINCT l.ip_id) as unique_clean_ips
FROM daily_logs l
JOIN paths p ON l.path_id = p.id
LEFT JOIN exclusions e ON LOWER(p.value) = e.url
WHERE l.status = 404
  AND l.date >= date('now', '-7 days')
  AND l.ip_id NOT IN NaughtyIPs
  AND p.value LIKE '/%'
  AND p.value NOT LIKE '//%'
  AND LENGTH(p.value) BETWEEN 2 AND 150
  AND instr(p.value, '?') = 0
  AND instr(p.value, '%') = 0
  AND instr(p.value, ' ') = 0
  AND instr(p.value, ';') = 0
  AND instr(p.value, '<') = 0
  AND instr(p.value, '>') = 0
  AND instr(p.value, '{') = 0
  AND instr(p.value, '}') = 0
  AND p.value NOT LIKE '%...%'
  AND LOWER(p.value) NOT LIKE '%placeholder%'
  AND LOWER(p.value) NOT LIKE '%/slug/%'
  AND LOWER(p.value) NOT LIKE '%attachment%'
  AND LOWER(p.value) NOT LIKE '%sitemap%'
  AND p.value NOT LIKE '/.%'
  AND p.value NOT LIKE '%/.%'
  AND LOWER(p.value) NOT LIKE '/wp-%'
  AND LOWER(p.value) NOT LIKE '%/wp-%'
  AND LOWER(p.value) NOT LIKE '%xmlrpc%'
  AND LOWER(p.value) NOT LIKE '/api/%'
  AND LOWER(p.value) NOT LIKE '/v1/%'
  AND LOWER(p.value) NOT LIKE '/v2/%'
  AND LOWER(p.value) NOT LIKE '/cgi-bin%'
  AND LOWER(p.value) NOT LIKE '%phpmyadmin%'
  AND LOWER(p.value) NOT LIKE '%boaform%'
  AND LOWER(p.value) NOT LIKE '/actuator%'
  AND LOWER(p.value) NOT LIKE '%autodiscover%'
  AND LOWER(p.value) NOT LIKE '%/owa%'
  AND LOWER(p.value) NOT LIKE '%/ecp%'
  AND LOWER(p.value) NOT LIKE '%/solr%'
  AND LOWER(p.value) NOT LIKE '%/geoserver%'
  AND LOWER(p.value) NOT LIKE '%/vendor/phpunit%'
  AND LOWER(p.value) NOT LIKE '/admin%'
  AND LOWER(p.value) NOT LIKE '/login%'
  AND LOWER(p.value) NOT LIKE '/logout%'
  AND LOWER(p.value) NOT LIKE '/signin%'
  AND LOWER(p.value) NOT LIKE '/signup%'
  AND LOWER(p.value) NOT LIKE '/rdweb%'
  AND LOWER(p.value) NOT LIKE '/sslvpn%'
  AND LOWER(p.value) NOT IN (
      '/robots.txt', '/favicon.ico', '/ads.txt', '/app-ads.txt', '/sellers.json',
      '/security.txt', '/humans.txt', '/manifest.json', '/site.webmanifest',
      '/browserconfig.xml', '/sse', '/mcp', '/graphql', '/metrics', '/health',
      '/healthz', '/status', '/server-status', '/files', '/files/', '/uploads',
      '/uploads/', '/images', '/images/', '/media', '/media/', '/assets',
      '/assets/', '/static', '/static/', '/backup', '/backup/', '/backups',
      '/backups/', '/temp', '/temp/', '/tmp', '/tmp/'
  )
  AND (
      p.value LIKE '%/'
      OR LOWER(p.value) LIKE '%.html'
      OR LOWER(p.value) LIKE '%.htm'
      OR LOWER(p.value) LIKE '%/index.md'
      OR instr(p.value, '.') = 0
  )
  AND e.url IS NULL
GROUP BY p.id
HAVING total_hits > 1
ORDER BY total_hits DESC
LIMIT 250;
