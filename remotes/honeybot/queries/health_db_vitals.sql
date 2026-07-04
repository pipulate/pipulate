-- remotes/honeybot/queries/health_db_vitals.sql
-- ============================================================================
-- HONEYBOT DB VITALS (The Gauge)
-- Read-only internals: page math, per-table cardinality, and the two known
-- bloat vectors (hostile-path dimension poisoning, fact-table key blowup).
-- Usage: cat this | ssh honeybot 'sqlite3 -header -column ~/www/mikelev.in/honeybot.db'
-- ============================================================================

SELECT 'page_size_bytes' AS metric, page_size AS value FROM pragma_page_size()
UNION ALL SELECT 'page_count', page_count FROM pragma_page_count()
UNION ALL SELECT 'freelist_pages', freelist_count FROM pragma_freelist_count()
UNION ALL SELECT 'db_bytes_approx',
    (SELECT page_count FROM pragma_page_count()) * (SELECT page_size FROM pragma_page_size())
UNION ALL SELECT 'rows_ips', COUNT(*) FROM ips
UNION ALL SELECT 'rows_user_agents', COUNT(*) FROM user_agents
UNION ALL SELECT 'rows_paths', COUNT(*) FROM paths
UNION ALL SELECT 'rows_referrers', COUNT(*) FROM referrers
UNION ALL SELECT 'rows_accept_headers', COUNT(*) FROM accept_headers
UNION ALL SELECT 'rows_daily_logs', COUNT(*) FROM daily_logs
UNION ALL SELECT 'rows_telemetry', COUNT(*) FROM telemetry
UNION ALL SELECT 'rows_kv_store', COUNT(*) FROM kv_store
UNION ALL SELECT 'distinct_days_logged', COUNT(DISTINCT date) FROM daily_logs
UNION ALL SELECT 'daily_logs_rows_last7d', COUNT(*) FROM daily_logs WHERE date >= date('now','-7 days')
UNION ALL SELECT 'telemetry_rows_last7d', COUNT(*) FROM telemetry WHERE date >= date('now','-7 days')
UNION ALL SELECT 'paths_avg_len', CAST(AVG(LENGTH(value)) AS INTEGER) FROM paths
UNION ALL SELECT 'paths_max_len', MAX(LENGTH(value)) FROM paths
UNION ALL SELECT 'paths_hostile_est', COUNT(*) FROM paths
    WHERE value LIKE '%.php%' OR value LIKE '%wp-%' OR value LIKE '%.env%'
       OR value LIKE '%.git%' OR value LIKE '%/cgi-bin/%';
