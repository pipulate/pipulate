#!/usr/bin/env python3
"""
The Dragnet: Fetches historical GSC data to ground the Virtual Graph in Reality.
Aggregates 16 months of data to eliminate 'Gray Circles' (Unknown Status).

Outputs: gsc_velocity.json (Rate-limited to once per day)
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import random
from pathlib import Path
import common

# --- CONFIGURATION ---
SITE_URL = "sc-domain:mikelev.in" 
SCRIPT_DIR = Path(__file__).parent.resolve()
# Adjust path to match your actual key location provided in context
SERVICE_ACCOUNT_KEY_FILE = Path.home() / ".config/articleizer/service-account-key.json"
OUTPUT_FILE = SCRIPT_DIR / 'gsc_velocity.json'

# The date of the "Crash" to pivot analysis around
CRASH_DATE = datetime(2025, 4, 23).date()
HISTORY_MONTHS = 16
ROW_LIMIT = 25000  # Max allowed by API per request

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

def authenticate_gsc():
    """Authenticates with the GSC API using Service Account."""
    if not SERVICE_ACCOUNT_KEY_FILE.exists():
        print(f"❌ Key file not found: {SERVICE_ACCOUNT_KEY_FILE}")
        sys.exit(1)
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES)
    return build('webmasters', 'v3', credentials=creds)

def extract_slug(url):
    """
    Normalizes a full URL into the specific slug format expected by build_hierarchy.py.
    """
    # Remove protocol and domain
    path = url.replace(SITE_URL.replace("sc-domain:", "https://"), "")
    path = path.replace("http://", "").replace("https://", "")
    
    # Remove domain if still present (for sc-domain properties)
    if "/" in path:
        path = path.split("/", 1)[1] 
    
    # Strip slashes
    clean_path = path.strip("/")
    
    # Get the last segment (the slug)
    if "/" in clean_path:
        slug = clean_path.split("/")[-1]
    else:
        slug = clean_path
        
    return slug

def fetch_month_data(service, start_date, end_date):
    """Fetches clicks per page for a specific date range with heavy pagination."""
    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['page'],
        'rowLimit': ROW_LIMIT,
        'startRow': 0
    }
    
    all_rows = []
    
    while True:
        try:
            response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
            rows = response.get('rows', [])
            all_rows.extend(rows)
            
            # Check if we hit the limit, if so, page next
            if len(rows) == ROW_LIMIT:
                print(".", end="", flush=True) # visual heartbeat
                request['startRow'] += ROW_LIMIT
                time.sleep(0.5) # Be nice to the API
            else:
                break
                
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                print(f"⏳", end="", flush=True)
                time.sleep(5) # Backoff
                continue
            print(f"\n  ⚠️ Error fetching {start_date}: {e}")
            break

    # Convert to dict: slug -> clicks (Aggregating if slugs duplicate due to protocol variations)
    mapped_data = {}
    for r in all_rows:
        url = r['keys'][0]
        clicks = r['clicks']
        slug = extract_slug(url)
        
        if slug:
            if slug in mapped_data:
                mapped_data[slug] += clicks
            else:
                mapped_data[slug] = clicks
            
    return mapped_data

def should_run(force=False):
    """Checks if the output file exists and was updated today."""
    if force:
        return True
        
    if not OUTPUT_FILE.exists():
        return True
        
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        last_updated = data.get('_meta', {}).get('last_updated')
        today = datetime.now().strftime('%Y-%m-%d')
        
        if last_updated == today:
            print(f"✅ GSC Data is fresh for today ({today}). Skipping fetch.")
            return False
            
    except Exception:
        # If file is corrupt or format is old, run anyway
        return True
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Fetch GSC History")
    parser.add_argument('--force', action='store_true', help="Ignore cache and force fetch")
    
    # Add this line so it swallows the --target flag without error
    common.add_target_argument(parser) 
    
    args = parser.parse_args()

    if not should_run(args.force):
        return

    print(f"🚀 Starting GSC Historical Dragnet for {SITE_URL}")
    print(f"📅 Pivot Date (Crash): {CRASH_DATE}")
    
    service = authenticate_gsc()
    
    # Generate date ranges (Monthly chunks going back 16 months)
    # We lag 3 days because GSC data is never real-time
    end_date = datetime.now().date() - timedelta(days=3) 
    current = end_date
    
    # Data Structure:
    # { 
    #   "_meta": { "last_updated": "YYYY-MM-DD" },
    #   "my-slug": { ... } 
    # }
    history_data = {} 
    
    print(f"⏳ Fetching last {HISTORY_MONTHS} months of data...")
    
    total_months_processed = 0
    
    for _ in range(HISTORY_MONTHS):
        # Calculate month window
        month_end = current
        month_start = (current - relativedelta(months=1)) + timedelta(days=1)
        
        month_key = month_start.strftime('%Y-%m')
        print(f"  [{month_key}] Fetching...", end="", flush=True)
        
        data = fetch_month_data(service, month_start, month_end)
        
        page_count = len(data)
        click_count = sum(data.values())
        print(f" ✓ {page_count} pages / {click_count:.0f} clicks")
        
        # Merge into main history
        for slug, clicks in data.items():
            if slug not in history_data:
                history_data[slug] = {'timeline': {}}
            
            # Add to timeline
            history_data[slug]['timeline'][month_key] = clicks
            
        current = month_start - timedelta(days=1)
        total_months_processed += 1
        time.sleep(random.uniform(0.5, 1.5)) # Human jitter

    print(f"\n🧮 Calculating Velocity and Health Scores for {len(history_data)} unique slugs...")
    
    final_output = {
        "_meta": {
            "last_updated": datetime.now().strftime('%Y-%m-%d')
        }
    }
    
    for slug, data in history_data.items():
        timeline = data['timeline']
        sorted_months = sorted(timeline.keys())
        
        # Calculate Pre/Post Crash Averages
        pre_crash_clicks = []
        post_crash_clicks = []
        recent_clicks = [] # Last 3 months for velocity
        
        # Calculate recent threshold date
        recent_threshold = (end_date - relativedelta(months=3))
        
        for month_str in sorted_months:
            m_date = datetime.strptime(month_str, '%Y-%m').date()
            clicks = timeline[month_str]
            
            if m_date < CRASH_DATE.replace(day=1):
                pre_crash_clicks.append(clicks)
            else:
                post_crash_clicks.append(clicks)
                
            if m_date >= recent_threshold.replace(day=1):
                recent_clicks.append(clicks)
        
        avg_pre = sum(pre_crash_clicks) / len(pre_crash_clicks) if pre_crash_clicks else 0
        avg_post = sum(post_crash_clicks) / len(post_crash_clicks) if post_crash_clicks else 0
        
        # Velocity: Slope of last 3 months
        velocity = 0
        if len(recent_clicks) >= 2:
            # Simple diff: Latest month - 3 months ago
            velocity = recent_clicks[-1] - recent_clicks[0]
            
        # Health Status Determination
        status = "stable"
        
        if avg_pre > 0:
            recovery_ratio = avg_post / avg_pre
            if recovery_ratio < 0.5:
                status = "critical"   # Lost >50% traffic
            elif recovery_ratio < 0.8:
                status = "ailing"     # Lost >20% traffic
            elif recovery_ratio > 1.2:
                status = "thriving"   # Grew >20%
            elif recovery_ratio > 0.8:
                status = "recovering" # Holding steady-ish
        elif avg_post > 5: # Low threshold for "Newborn"
            status = "newborn" # No pre-crash data, but has traffic now
        elif avg_post == 0 and avg_pre == 0:
            status = "unknown"
        elif avg_post == 0:
            status = "dormant"

        final_output[slug] = {
            "total_clicks": sum(timeline.values()),
            "pre_crash_avg": round(avg_pre, 1),
            "post_crash_avg": round(avg_post, 1),
            "velocity": velocity,
            "status": status,
            "timeline": timeline
        }

    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2)
        
    print(f"💾 Saved velocity data to {OUTPUT_FILE}")
    print(f"💎 Total Unique Content Nodes Grounded: {len(history_data)}")

if __name__ == "__main__":
    main()
