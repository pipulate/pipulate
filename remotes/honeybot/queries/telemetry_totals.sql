SELECT 
    COUNT(*) as unique_signatures, 
    SUM(count) as total_hits 
FROM telemetry;