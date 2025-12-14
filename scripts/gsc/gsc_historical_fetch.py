#!/usr/bin/env python3
"""
Fetches historical GSC data (last 16 months) to analyze trends and velocity.
Specifically looks for the 'April 23, 2025' crash impact.

Outputs: gsc_velocity.json
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---
SITE_URL = "sc-domain:mikelev.in" # Update if needed
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_KEY_FILE = os.path.join(SCRIPT_DIR, 'service-account-key.json')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, '../d3js/gsc_velocity.json')

# The date of the "Crash" to pivot analysis around
CRASH_DATE = datetime(2025, 4, 23).date()
HISTORY_MONTHS = 16

SCOPES = ['https://www.googleapis.com/auth/webmasters']

def authenticate_gsc():
    if not os.path.exists(SERVICE_ACCOUNT_KEY_FILE):
        print(f"❌ Key file not found: {SERVICE_ACCOUNT_KEY_FILE}")
        sys.exit(1)
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES)
    return build('webmasters', 'v3', credentials=creds)

def fetch_month_data(service, start_date, end_date):
    """Fetches clicks per page for a specific date range."""
    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['page'],
        'rowLimit': 25000,
        'startRow': 0
    }
    
    rows = []
    try:
        response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
        rows = response.get('rows', [])
        # Handle pagination if needed (though 25k pages is a lot for one month)
        while 'rows' in response and len(response['rows']) == 25000:
             request['startRow'] += 25000
             response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
             rows.extend(response.get('rows', []))
    except Exception as e:
        print(f"  ⚠️ Error fetching {start_date}: {e}")
        return {}

    # Convert to dict: url -> clicks
    return {r['keys'][0]: r['clicks'] for r in rows}

def main():
    print(f"🚀 Starting GSC Historical Fetch for {SITE_URL}")
    print(f"📅 Analyzing impact of Crash Date: {CRASH_DATE}")
    
    service = authenticate_gsc()
    
    # Generate date ranges (Monthly chunks going back 16 months)
    end_date = datetime.now().date() - timedelta(days=2) # 2 day lag
    current = end_date
    
    history_data = {} # url -> { 'months': [], 'clicks': [] }
    
    # We will aggregate by month for the trend line
    print(f"⏳ Fetching last {HISTORY_MONTHS} months of data...")
    
    for _ in range(HISTORY_MONTHS):
        # Calculate month window
        month_end = current
        month_start = (current - relativedelta(months=1)) + timedelta(days=1)
        
        print(f"  Fetching {month_start} to {month_end}...", end="", flush=True)
        
        data = fetch_month_data(service, month_start, month_end)
        print(f" ✓ {len(data)} pages")
        
        # Merge into main history
        month_key = month_start.strftime('%Y-%m')
        for url, clicks in data.items():
            if url not in history_data:
                history_data[url] = {'timeline': {}}
            history_data[url]['timeline'][month_key] = clicks
            
        current = month_start - timedelta(days=1)
        time.sleep(0.5) # Rate limit niceness

    print("\n🧮 Calculating Velocity and Health Scores...")
    
    final_output = {}
    
    for url, data in history_data.items():
        timeline = data['timeline']
        sorted_months = sorted(timeline.keys())
        
        # Calculate Pre/Post Crash Averages
        pre_crash_clicks = []
        post_crash_clicks = []
        recent_clicks = [] # Last 3 months
        
        for month_str in sorted_months:
            # Approx date check
            m_date = datetime.strptime(month_str, '%Y-%m').date()
            clicks = timeline[month_str]
            
            if m_date < CRASH_DATE.replace(day=1):
                pre_crash_clicks.append(clicks)
            else:
                post_crash_clicks.append(clicks)
                
            # For recent velocity
            if m_date >= (end_date - relativedelta(months=3)).replace(day=1):
                recent_clicks.append(clicks)
        
        avg_pre = sum(pre_crash_clicks) / len(pre_crash_clicks) if pre_crash_clicks else 0
        avg_post = sum(post_crash_clicks) / len(post_crash_clicks) if post_crash_clicks else 0
        
        # Velocity: Simple slope of last 3 months (or diff)
        velocity = 0
        if len(recent_clicks) >= 2:
            # Simple diff: Last month - 3 months ago
            velocity = recent_clicks[-1] - recent_clicks[0]
            
        # Health Status
        status = "stable"
        if avg_pre > 0:
            recovery_ratio = avg_post / avg_pre
            if recovery_ratio < 0.5:
                status = "critical" # Lost >50% traffic
            elif recovery_ratio < 0.8:
                status = "ailing"
            elif recovery_ratio > 1.2:
                status = "thriving"
            elif recovery_ratio > 0.8:
                status = "recovering"
        elif avg_post > 10:
            status = "newborn" # No pre-crash data, but has traffic now
            
        final_output[url] = {
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
    print(f"🔍 Analyzed {len(final_output)} URLs.")

if __name__ == "__main__":
    main()