#!/usr/bin/env python
# coding: utf-8

"""
Fetches Google Search Console (GSC) data over a specified date range,
identifies the top N keywords (<= M words) per page based on total impressions,
and outputs the results to a JSON file for Jekyll (_data).

Required pip installs:
    pip install google-api-python-client google-auth pandas python-dateutil # Added python-dateutil
"""

import os
import sys
import time
import json # Added
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta # Added
from urllib.parse import urlparse # Added

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configuration ---

# GSC Property URL (e.g., "sc-domain:example.com" or "https://www.example.com/")
SITE_URL = "sc-domain:mikelev.in"
# Base URL of your website (used to convert absolute GSC URLs to relative paths)
BASE_URL = "https://mikelev.in"

# Path to your service account key JSON file — resolved from the wallet, never
# from inside this repo. Resolution chain (identical to scripts/connectors/gsc.py):
#   PIPULATE_GSC_KEY env -> connectors.json gsc.paths.service_account
#     -> wallet-path default. Duplicated deliberately (WET, per the
#   connectors README): this file must stay a standalone artifact.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # Use abspath for reliability


def _resolve_gsc_key_path():
    import json as _json
    from pathlib import Path as _Path
    env = os.environ.get('PIPULATE_GSC_KEY')
    if env:
        return os.path.expanduser(env)
    wallet = _Path.home() / '.config' / 'pipulate' / 'connectors.json'
    if wallet.exists():
        try:
            data = _json.loads(wallet.read_text(encoding='utf-8'))
            p = (data.get('gsc') or {}).get('paths', {}).get('service_account')
            if p:
                return os.path.expanduser(p)
        except (_json.JSONDecodeError, OSError):
            pass
    return os.path.expanduser('~/.config/pipulate/service-account-key.json')


SERVICE_ACCOUNT_KEY_FILE = _resolve_gsc_key_path()

# Required Google API scope. This workflow only reads Search Analytics data, so
# keep the credential at least privilege rather than granting read/write access.
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# --- Data Fetching Parameters ---
# How many days/months of data to fetch? Use relativedelta for months.
FETCH_PERIOD = relativedelta(months=3) # e.g., relativedelta(months=3), relativedelta(days=90)
# GSC data delay. Data for 'today' is usually not available for START_OFFSET_DAYS.
START_OFFSET_DAYS = 2
# Delay between API pagination calls (seconds) to respect rate limits
API_CHECK_DELAY = 0.5

# --- Processing Parameters ---
# How many top keywords to keep per page?
TOP_N_KEYWORDS = 10
# Maximum number of words allowed in a keyword phrase (n-gram limit)
MAX_KEYWORD_WORDS = 4

# --- Output Parameters ---
# Relative path to Jekyll's data directory from this script's location
JEKYLL_DATA_DIR = os.path.join(SCRIPT_DIR, '../../MikeLev.in/_data') # Assumes script is in a subdir like 'scripts'
# Filename for the output JSON
OUTPUT_JSON_FILENAME = 'gsc_top_keywords.json'

# --- End Configuration ---


def authenticate_gsc():
    """Authenticates with Google API using service account credentials."""
    if not os.path.exists(SERVICE_ACCOUNT_KEY_FILE):
        print(f"❌ Error: Service account key file not found at: {SERVICE_ACCOUNT_KEY_FILE}")
        print("Please ensure the file exists and the path is correct.")
        sys.exit(1)
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES)
        webmasters_service = build('webmasters', 'v3', credentials=credentials)
        print("✓ Successfully authenticated with Google Search Console API.")
        return webmasters_service
    except Exception as e:
        print(f"❌ Error during GSC authentication: {e}")
        sys.exit(1)


def fetch_all_gsc_data(service, site_url, request_body):
    """Fetches all available data rows for a given GSC query, handling pagination."""
    all_rows = []
    start_row = request_body.get('startRow', 0)
    row_limit = request_body.get('rowLimit', 25000) # Use max GSC limit
    page_count = 0
    print(f"\n🔄 Fetching data for {site_url}")
    print(f"   Period: {request_body.get('startDate')} to {request_body.get('endDate')}")
    print(f"   Dimensions: {request_body.get('dimensions', [])}")

    while True:
        page_count += 1
        request_body['startRow'] = start_row
        print(f"   Fetching page {page_count} (starting row {start_row})...", end=" ", flush=True)
        try:
            response = service.searchanalytics().query(
                siteUrl=site_url, body=request_body).execute()
            current_rows = response.get('rows', [])
            if not current_rows:
                if page_count == 1:
                    print("No data found for this period/query.")
                else:
                    print("✓ No more data.")
                break
            print(f"✓ Retrieved {len(current_rows)} rows.")
            all_rows.extend(current_rows)
            # Check if the number of rows returned is less than the limit requested.
            # If it is, this indicates the last page.
            # Note: GSC API max rowLimit is 25000. If exactly 25000 are returned,
            # we must make another call to confirm it was the last page.
            if len(current_rows) < row_limit:
                 print("✓ Reached last page of results.")
                 break

            start_row += len(current_rows) # Prepare for the next page
            time.sleep(API_CHECK_DELAY) # Be nice to the API

        except HttpError as e:
            print(f"\n❌ API Error fetching page {page_count}: {e.resp.status} {e.resp.reason}")
            # Handle specific errors if needed (e.g., rate limits 429, permissions 403)
            if e.resp.status == 429:
                print("   Rate limit likely exceeded. Consider increasing API_CHECK_DELAY or reducing fetch frequency.")
            elif e.resp.status == 403:
                 print("   Permission denied. Check service account access to the GSC property.")
            # Decide if you want to retry or abort on error. Here we abort.
            return [] # Return empty list on error
        except Exception as e:
            print(f"\n❌ Unexpected error fetching page {page_count}: {e}")
            return []

    print(f"✓ Finished fetching. Total rows retrieved: {len(all_rows)}")
    return all_rows


def process_gsc_data_to_dataframe(gsc_data_list):
    """Converts raw GSC data list into a processed Pandas DataFrame."""
    if not gsc_data_list:
        print("No raw data to process.")
        return pd.DataFrame()

    df = pd.DataFrame(gsc_data_list)

    # Check if 'keys' column exists (contains dimensions)
    if 'keys' in df.columns and not df['keys'].empty:
        try:
            # Extract dimensions based on the assumption they are [query, page]
            # Make sure this matches the 'dimensions' requested in the API call
            key_data = df['keys'].apply(pd.Series)
            df['query'] = key_data[0]
            df['page'] = key_data[1]
            df = df.drop('keys', axis=1)
            print("✓ Extracted 'query' and 'page' from 'keys'.")
        except Exception as e:
            print(f"⚠️ Warning: Could not reliably extract 'query'/'page' from 'keys' column: {e}")
            print("   Check if 'dimensions' in the API request matches ['query', 'page'].")
            # If extraction fails, return empty DF as further processing depends on these columns
            return pd.DataFrame()
    else:
        print("⚠️ Warning: 'keys' column not found or empty. Cannot extract dimensions.")
        return pd.DataFrame()

    # Ensure standard metric columns exist and convert to numeric, coercing errors
    metric_cols = ['clicks', 'impressions', 'ctr', 'position']
    print("✓ Converting metrics to numeric types...")
    for col in metric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            # If essential metrics like 'impressions' are missing, we might have issues
            print(f"   Note: Metric column '{col}' not found in raw data.")
            if col == 'impressions' or col == 'clicks':
                 df[col] = 0 # Add column with 0 if essential and missing

    # Drop rows where essential columns might have become NaN after coercion
    df.dropna(subset=['query', 'page', 'impressions', 'clicks'], inplace=True)

    # Optional: Convert CTR to percentage if desired (not strictly needed for this task)
    # if 'ctr' in df.columns:
    #     df['ctr'] = df['ctr'] * 100

    print(f"✓ Initial DataFrame processed ({len(df)} rows).")
    return df


def generate_top_keywords_json(df, base_url, top_n=10, max_words=4):
    """
    Processes the DataFrame to find top N keywords (<= max_words) per page
    and returns a dictionary formatted for JSON output.
    """
    if df.empty:
        print("Input DataFrame is empty. Cannot generate keyword data.")
        return {}

    print("\n⚙️ Processing data for top keywords...")

    # 1. Ensure required columns exist
    required_cols = ['page', 'query', 'impressions', 'clicks']
    if not all(col in df.columns for col in required_cols):
        print(f"❌ Error: DataFrame missing one or more required columns: {required_cols}")
        return {}

    # 2. Filter by keyword word count (n-gram limit)
    print(f"   Filtering keywords to max {max_words} words...")
    # Ensure query is string, handle potential NaN/None
    df['query_str'] = df['query'].astype(str).fillna('')
    df['word_count'] = df['query_str'].str.split().str.len()
    df_filtered = df[df['word_count'] <= max_words].copy()
    print(f"   Rows remaining after word count filter: {len(df_filtered)}")
    if df_filtered.empty:
         print("   No keywords found matching the word count criteria.")
         return {}

    # 3. Aggregate data by page and query (summing impressions/clicks over the period)
    print("   Aggregating impressions and clicks per page/query...")
    df_agg = df_filtered.groupby(['page', 'query'], as_index=False)[['impressions', 'clicks']].sum()
    # Convert aggregated impressions/clicks back to integer types
    df_agg['impressions'] = df_agg['impressions'].astype(int)
    df_agg['clicks'] = df_agg['clicks'].astype(int)


    # 4. Sort by impressions within each page group
    print("   Sorting keywords by impressions...")
    # Sort primarily by page, secondarily by impressions descending
    df_sorted = df_agg.sort_values(by=['page', 'impressions'], ascending=[True, False])

    # 5. Select Top N keywords per page
    print(f"   Selecting top {top_n} keywords per page...")
    df_top_n = df_sorted.groupby('page').head(top_n)
    print(f"   Total page/keyword combinations in top {top_n}: {len(df_top_n)}")

    # 6. Format URLs to relative paths for Jekyll keys
    print("   Formatting page URLs to relative paths...")
    def format_url_key(url_str):
        if not isinstance(url_str, str) or not url_str.startswith(base_url):
            return None # Skip URLs not matching the base URL
        # Remove base URL
        relative_path = url_str[len(base_url):]
        # Ensure it starts with '/'
        if not relative_path.startswith('/'):
            relative_path = '/' + relative_path
        # Optional: Remove trailing slash if Jekyll's page.url doesn't have one
        # if relative_path != '/' and relative_path.endswith('/'):
        #     relative_path = relative_path[:-1]
        return relative_path

    df_top_n['jekyll_url_key'] = df_top_n['page'].apply(format_url_key)
    # Drop rows where formatting failed (e.g., external URLs if any were present)
    df_final = df_top_n.dropna(subset=['jekyll_url_key'])
    print(f"   Valid Jekyll URL keys generated: {df_final['jekyll_url_key'].nunique()}")

    # 7. Structure data for JSON output
    print("   Structuring data for JSON output...")
    output_dict = {}
    # Group by the formatted Jekyll URL key
    for key, group in df_final.groupby('jekyll_url_key'):
        # For each group (page), create a list of keyword dictionaries
        output_dict[key] = group[['query', 'impressions', 'clicks']].to_dict('records')

    print("✓ Keyword processing complete.")
    return output_dict

# --- Main Execution ---

def main():
    """Main execution function."""
    print("--- Starting GSC Top Keywords Export ---")
    start_time = time.time()

    # 1. Authenticate
    gsc_service = authenticate_gsc()

    # 2. Determine Date Range
    end_date = datetime.now().date() - timedelta(days=START_OFFSET_DAYS)
    start_date = end_date - FETCH_PERIOD
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # 3. Define API Request Body for the entire period
    request_body = {
        'startDate': start_date_str,
        'endDate': end_date_str,
        'dimensions': ['query', 'page'],
        # Optional: Add 'type': 'web' or other filters if needed
        # 'dimensionFilterGroups': [{...}],
        'rowLimit': 25000, # Max per request page
        'startRow': 0
    }

    # 4. Fetch Data
    raw_gsc_data = fetch_all_gsc_data(gsc_service, SITE_URL, request_body)

    if not raw_gsc_data:
        print("\n❌ No data fetched from GSC. Exiting.")
        sys.exit(1)

    # 5. Process into Initial DataFrame
    df_gsc = process_gsc_data_to_dataframe(raw_gsc_data)

    if df_gsc.empty:
         print("\n❌ DataFrame processing failed or resulted in empty data. Exiting.")
         sys.exit(1)

    # 6. Generate the Top Keywords Dictionary
    top_keywords_data = generate_top_keywords_json(
        df_gsc,
        base_url=BASE_URL,
        top_n=TOP_N_KEYWORDS,
        max_words=MAX_KEYWORD_WORDS
    )

    # 7. Save to JSON File
    if not top_keywords_data:
        print("\n⚠️ No keyword data generated. Skipping JSON file creation.")
    else:
        output_path = os.path.join(JEKYLL_DATA_DIR, OUTPUT_JSON_FILENAME)
        print(f"\n💾 Saving top keywords data to: {output_path}")
        try:
            # Ensure the _data directory exists
            os.makedirs(JEKYLL_DATA_DIR, exist_ok=True)
            # Write the JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(top_keywords_data, f, indent=2, ensure_ascii=False) # indent for readability
            print(f"✓ Successfully saved JSON data.")
        except Exception as e:
            print(f"\n❌ Error saving JSON file: {e}")

    end_time = time.time()
    print(f"\n--- Script finished in {end_time - start_time:.2f} seconds ---")


if __name__ == "__main__":
    # Basic check for SITE_URL placeholder
    if not SITE_URL or SITE_URL == "sc-domain:yourdomain.com":
        print("❌ Error: Please update the 'SITE_URL' variable in the script configuration section.")
        sys.exit(1)
    if not BASE_URL or "example.com" in BASE_URL:
         print("❌ Error: Please update the 'BASE_URL' variable in the script configuration section.")
         sys.exit(1)

    main()
