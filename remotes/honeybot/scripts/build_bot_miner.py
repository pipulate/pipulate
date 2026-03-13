#!/usr/bin/env python3
import json
from pathlib import Path

# We are right next to the JSON file now
INTEL_PATH = Path(__file__).resolve().parent / "bot_intel.json"

with open(INTEL_PATH, "r") as f:
    BOT_INTEL = json.load(f)

# The foundational heuristics
sql = """SELECT 
    ua.value as suspicious_agent,
    SUM(logs.count) as total_hits,
    (
        -- Heuristic 1: Suspicious Keywords (+10)
        (CASE WHEN ua.value LIKE '%bot%' 
                OR ua.value LIKE '%crawl%' 
                OR ua.value LIKE '%spider%'
                OR ua.value LIKE '%fetch%'
                OR ua.value LIKE '%scrape%'
                OR ua.value LIKE '%search%'
                OR ua.value LIKE '%preview%'
                OR ua.value LIKE '%monitor%'
                OR ua.value LIKE '%http%'
                OR ua.value LIKE '%python%'
                OR ua.value LIKE '%curl%'
                OR ua.value LIKE '%wget%'
                OR ua.value LIKE '%headless%'
                OR ua.value LIKE '%puppeteer%'
                OR ua.value LIKE '%selenium%' 
              THEN 10 ELSE 0 END) +
        
        -- Heuristic 2: Non-Mozilla Format (+5)
        (CASE WHEN ua.value NOT LIKE '%Mozilla%' THEN 5 ELSE 0 END) +
        
        -- Heuristic 3: High Volume (+2 if over 50 hits)
        (CASE WHEN SUM(logs.count) > 50 THEN 2 ELSE 0 END) +
        
        -- Heuristic 4: "Compatible" but not a standard browser (+5)
        (CASE WHEN ua.value LIKE '%compatible%' 
               AND ua.value LIKE '%Mozilla%'
               AND ua.value NOT LIKE '%Chrome%'
               AND ua.value NOT LIKE '%Safari%'
               AND ua.value NOT LIKE '%Firefox%' 
              THEN 5 ELSE 0 END)
    ) as bot_score

FROM daily_logs logs
JOIN user_agents ua ON logs.ua_id = ua.id
WHERE 
"""

# Dynamically generate the exclusions
exclusions = []
for bot in BOT_INTEL["seen"].keys():
    exclusions.append(f"ua.value NOT LIKE '%{bot}%'")

sql += "    " + "\n    AND ".join(exclusions)

sql += """
GROUP BY ua.id
HAVING bot_score > 0
ORDER BY bot_score DESC, total_hits DESC
LIMIT 50;
"""

print(sql)