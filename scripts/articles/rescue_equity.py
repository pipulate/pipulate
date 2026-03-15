#!/usr/bin/env python3
"""
The Equity Rescuer: Analyzes GSC velocity data to identify high-value
content bleeding traffic ('critical' or 'ailing').
Outputs a prioritized list of hub candidates sorted by the largest traffic drop.
"""

import json
from pathlib import Path

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).parent.resolve()
GSC_FILE = SCRIPT_DIR / "gsc_velocity.json"

def analyze_bleeding_equity():
    if not GSC_FILE.exists():
        print(f"❌ Error: {GSC_FILE} not found. Run gsc_historical_fetch.py first.")
        return

    with open(GSC_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    candidates = []
    for slug, metrics in data.items():
        if slug == "_meta":
            continue
        
        status = metrics.get("status")
        if status in ["critical", "ailing"]:
            # Calculate the absolute drop in average monthly clicks
            pre_avg = metrics.get("pre_crash_avg", 0)
            post_avg = metrics.get("post_crash_avg", 0)
            drop = pre_avg - post_avg
            
            # Only care about things that actually had significant traffic to lose
            if drop > 1.0: 
                candidates.append({
                    "slug": slug,
                    "status": status,
                    "pre_crash_avg": pre_avg,
                    "post_crash_avg": post_avg,
                    "drop": round(drop, 1),
                    "velocity": metrics.get("velocity", 0)
                })

    # Sort primarily by the size of the drop (largest hemorrhage first)
    candidates.sort(key=lambda x: x["drop"], reverse=True)

    print(f"🚑 FOUND {len(candidates)} BLEEDING CONTENT NODES")
    print("=" * 95)
    print(f"{'SLUG':<55} | {'STATUS':<10} | {'PRE-AVG':<7} | {'POST-AVG':<8} | {'DROP':<5}")
    print("-" * 95)
    
    for c in candidates:
        print(f"{c['slug']:<55} | {c['status']:<10} | {c['pre_crash_avg']:<7} | {c['post_crash_avg']:<8} | -{c['drop']:<5}")

if __name__ == "__main__":
    analyze_bleeding_equity()