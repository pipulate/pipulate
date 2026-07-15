#!/usr/bin/env python
# coding: utf-8

"""
Fetches Google Search Console (GSC) data for the 4 most recent days available,
calculates trend slopes for impressions, clicks, and position for each
page/query combination, and identifies top movers. Saves daily data to CSV cache.

Required pip installs:
    pip install google-api-python-client google-auth pandas numpy scipy
"""

import os
import sys
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Need scipy for linregress OR numpy for polyfit - we'll use polyfit here
# from scipy.stats import linregress

# --- Configuration ---

# Set your GSC Property URL here (e.g., "sc-domain:example.com" or "https://www.example.com/")
SITE_URL = "sc-domain:mikelev.in"

# Path to your service account key JSON file — resolved from the wallet, never
# from inside this repo. The old SCRIPT_DIR expectation was a landmine: one
# careless `git add scripts/gsc/` away from shipping a Google credential to a
# public remote. Resolution chain (identical to scripts/connectors/gsc.py):
#   PIPULATE_GSC_KEY env -> connectors.json gsc.paths.service_account
#     -> wallet-path default. Duplicated deliberately (WET, per the
#   connectors README): this file must stay a standalone artifact.
SCRIPT_DIR = os.path.dirname(__file__)


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

# Required Google API scopes
SCOPES = ['https://www.googleapis.com/auth/webmasters']

# GSC data typically has a delay. Start checking this many days before today.
START_OFFSET_DAYS = 2

# Maximum number of past days to check before giving up
MAX_DAYS_TO_CHECK = 31

# Delay between API checks (in seconds) to respect rate limits
API_CHECK_DELAY = 0.5

# Number of consecutive days of data to fetch (ending on the most recent date)
NUM_DAYS_TO_FETCH = 4

# Number of top results to display in each category
TOP_N = 100

# Directory to store/load cached daily GSC data CSV files
CACHE_DIR = os.path.join(SCRIPT_DIR, 'gsc_cache')

# --- End Configuration ---


# --- Functions from previous steps (authenticate_gsc, check_date_has_data, find_most_recent_gsc_data_date, fetch_all_gsc_data, process_gsc_data_to_dataframe, get_gsc_data_for_day) ---
# Include the full definitions of these functions here from the previous code block...

def authenticate_gsc():
    """Authenticates with Google API using service account credentials."""
    if not os.path.exists(SERVICE_ACCOUNT_KEY_FILE):
        print(f"Error: Service account key file not found at: {SERVICE_ACCOUNT_KEY_FILE}")
        sys.exit(1)
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES)
        webmasters_service = build('webmasters', 'v3', credentials=credentials)
        print("✓ Successfully authenticated with Google Search Console API.")
        return webmasters_service
    except Exception as e:
        print(f"Error during GSC authentication: {e}")
        sys.exit(1)


def check_date_has_data(service, site_url, check_date):
    """Checks if GSC has any performance data for the given site and date."""
    date_str = check_date.strftime('%Y-%m-%d')
    request_body = {
        'startDate': date_str, 'endDate': date_str,
        'dimensions': ['query'], 'rowLimit': 1
    }
    try:
        response = service.searchanalytics().query(
            siteUrl=site_url, body=request_body).execute()
        return bool(response.get('rows'))
    except HttpError as e:
        print(f"\nAPI Error checking date {date_str}: {e.resp.status} {e.resp.reason}")
        return False
    except Exception as e:
        print(f"\nUnexpected error checking date {date_str}: {e}")
        return False


def find_most_recent_gsc_data_date(service, site_url):
    """Iterates backward to find the latest date with GSC data."""
    most_recent_data_date = None
    days_checked = 0
    current_date = datetime.now().date() - timedelta(days=START_OFFSET_DAYS)
    print(f"\nFinding most recent data date for site: {site_url}")
    print(f"Starting check from date: {current_date}")
    while days_checked < MAX_DAYS_TO_CHECK:
        print(f"Checking date {current_date}...", end=" ", flush=True)
        if check_date_has_data(service, site_url, current_date):
            print("✓ Data found!")
            most_recent_data_date = current_date
            break
        else:
            print("✗ No data")
            current_date -= timedelta(days=1)
            days_checked += 1
            time.sleep(API_CHECK_DELAY)
    if not most_recent_data_date:
        last_checked_date = current_date + timedelta(days=1)  # Date where check stopped
        print(f"\nWarning: Could not find data within {MAX_DAYS_TO_CHECK} checked days (back to {last_checked_date}).")
    return most_recent_data_date


def fetch_all_gsc_data(service, site_url, request_body):
    """Fetches all available data rows for a given GSC query, handling pagination."""
    all_rows = []
    start_row = request_body.get('startRow', 0)
    row_limit = request_body.get('rowLimit', 25000)  # Use max GSC limit
    page_count = 0
    print(f"\nFetching data with dimensions: {request_body.get('dimensions', [])} for {request_body.get('startDate')}")
    while True:
        page_count += 1
        request_body['startRow'] = start_row
        print(f"Fetching page {page_count} (starting row {start_row})...", end=" ", flush=True)
        try:
            response = service.searchanalytics().query(
                siteUrl=site_url, body=request_body).execute()
            current_rows = response.get('rows', [])
            if not current_rows:
                if page_count == 1:
                    print("No data found for this query.")
                else:
                    print("✓ No more data.")
                break
            print(f"✓ Retrieved {len(current_rows)} rows.")
            all_rows.extend(current_rows)
            if len(current_rows) < row_limit:
                print("✓ Reached last page of results.")
                break
            start_row += len(current_rows)
            time.sleep(API_CHECK_DELAY)
        except HttpError as e:
            print(f"\nAPI Error fetching page {page_count}: {e.resp.status} {e.resp.reason}")
            return []  # Return empty list on error
        except Exception as e:
            print(f"\nUnexpected error fetching page {page_count}: {e}")
            return []
    print(f"✓ Finished fetching {request_body.get('startDate')}. Total rows: {len(all_rows)}")
    return all_rows


def process_gsc_data_to_dataframe(gsc_data_list, data_date):
    """Converts raw GSC data list into a processed Pandas DataFrame."""
    if not gsc_data_list:
        # Keep this print statement for clarity during processing
        # print(f"No data to process into DataFrame for {data_date}.")
        return pd.DataFrame()  # Return empty DF if no raw data
    df = pd.DataFrame(gsc_data_list)
    if 'keys' in df.columns and not df['keys'].empty:
        try:
            df['query'] = df['keys'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None)
            df['page'] = df['keys'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df = df.drop('keys', axis=1)
        except Exception as e:
            print(f"Warning: Could not split 'keys' column for {data_date}: {e}")
    metric_cols = ['clicks', 'impressions', 'ctr', 'position']
    for col in metric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # else: # No need to print this repeatedly if a metric is consistently missing
            # print(f"Note: Metric column '{col}' not found for {data_date}.")
    if 'ctr' in df.columns:
        df['ctr'] = df['ctr'] * 100
    # Don't print success here, wait until after combining DFs if needed
    # print(f"✓ Processed data for {data_date} into DataFrame ({len(df)} rows).")
    return df


def get_gsc_data_for_day(service, site_url, data_date):
    """Fetches GSC data for a specific day, using cache if available."""
    date_str = data_date.strftime('%Y-%m-%d')
    cache_filename = os.path.join(CACHE_DIR, f"gsc_data_{date_str}.csv")
    if os.path.exists(cache_filename):
        try:
            print(f"📂 CACHE: Loading data for {date_str} from cache: {cache_filename}")
            df = pd.read_csv(cache_filename, dtype={
                'clicks': 'Int64', 'impressions': 'Int64', 'ctr': 'float64',
                'position': 'float64', 'query': 'object', 'page': 'object'
            }, parse_dates=False)
            if 'ctr' in df.columns and not df['ctr'].empty and df['ctr'].max() <= 1.0:
                df['ctr'] = df['ctr'] * 100
            return df
        except Exception as e:
            print(f"⚠️ Warning: Could not load cache file {cache_filename}. Error: {e}. Re-fetching.")
    print(f"🔄 API: Fetching data for {date_str} from GSC API...")
    request = {
        'startDate': date_str, 'endDate': date_str,
        'dimensions': ['query', 'page'],
        'rowLimit': 25000, 'startRow': 0
    }
    raw_data = fetch_all_gsc_data(service, site_url, request)
    df = process_gsc_data_to_dataframe(raw_data, date_str)
    if not df.empty:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            df.to_csv(cache_filename, index=False)
            print(f"💾 Saved data for {date_str} to cache: {cache_filename}")
        except Exception as e:
            print(f"⚠️ Warning: Could not save data for {date_str} to cache. Error: {e}")
    return df

# --- New Function for Trend Analysis ---


def analyze_trends(daily_dataframes_dict):
    """
    Combines daily DataFrames and calculates trend slopes and time series.

    Args:
        daily_dataframes_dict (dict): Dict mapping date obj to daily GSC DataFrame.

    Returns:
        pandas.DataFrame: DataFrame with page, query, slopes, and time series lists.
                          Returns empty DataFrame if input is invalid or processing fails.
    """
    if not daily_dataframes_dict or len(daily_dataframes_dict) < 2:
        print("Error: Need at least 2 days of data for trend analysis.")
        return pd.DataFrame()

    # Get sorted dates from the dictionary keys
    dates = sorted(daily_dataframes_dict.keys())
    num_days = len(dates)

    # Prepare list of dataframes to concatenate, adding date column
    dfs_to_concat = []
    for date, df in daily_dataframes_dict.items():
        if not df.empty:
            df_copy = df.copy()  # Work on a copy
            df_copy['date'] = pd.to_datetime(date)  # Ensure date is datetime object
            dfs_to_concat.append(df_copy)

    if not dfs_to_concat:
        print("Error: No valid DataFrames found to combine for trend analysis.")
        return pd.DataFrame()

    # Combine DataFrames
    combined_df = pd.concat(dfs_to_concat, ignore_index=True)
    print(f"\n✓ Combined data for {len(dates)} days into a single DataFrame ({len(combined_df)} rows total).")

    # Add Day Index for regression
    date_to_index = {pd.to_datetime(date): i for i, date in enumerate(dates)}
    combined_df['day_index'] = combined_df['date'].map(date_to_index)

    # Define metrics for trend analysis
    metrics = ['impressions', 'clicks', 'position']

    # --- Inner function to process each page/query group ---
    def analyze_single_group(group):
        # Convert the groupby result to a DataFrame if it's a Series
        if isinstance(group, pd.Series):
            group = group.to_frame().T

        # Ensure date is in datetime format
        if 'date' in group.columns:
            group['date'] = pd.to_datetime(group['date'])
            group = group.set_index('date')

        # Create a complete date range
        full_date_index = pd.to_datetime(dates)

        # Create empty results dictionary
        results = {}

        # Handle each metric
        for metric in metrics:
            # Default values in case metric is missing
            results[f'{metric}_ts'] = [0] * num_days  # Default time series
            results[f'{metric}_slope'] = np.nan       # Default slope

            # Skip processing if metric is not in the group's columns
            if metric not in group.columns:
                continue

            # Get metric values for each date (align with date index)
            metric_by_date = {}
            for _, row in group.reset_index().iterrows():
                if 'date' in row and pd.notnull(row['date']) and metric in row and pd.notnull(row[metric]):
                    dt = pd.to_datetime(row['date'])
                    metric_by_date[dt] = row[metric]

            # Create time series array aligned with full date range
            ts_values = []
            for dt in full_date_index:
                if dt in metric_by_date:
                    value = metric_by_date[dt]
                    # Handle impressions and clicks as integers (filled with 0)
                    if metric in ['impressions', 'clicks']:
                        ts_values.append(int(value) if pd.notnull(value) else 0)
                    # Handle position as float (can be NaN)
                    else:
                        ts_values.append(round(float(value), 1) if pd.notnull(value) else np.nan)
                else:
                    # For missing dates: 0 for counts, NaN for position
                    ts_values.append(0 if metric in ['impressions', 'clicks'] else np.nan)

            results[f'{metric}_ts'] = ts_values

            # Calculate regression slope if we have enough valid data points
            x = np.arange(num_days)
            y = np.array(ts_values)
            valid_mask = ~np.isnan(y)
            valid_count = np.sum(valid_mask)

            if valid_count >= 2:  # Two or more points for regression
                try:
                    # Extract valid x and y values
                    x_valid = x[valid_mask]
                    y_valid = y[valid_mask]
                    # Calculate slope using numpy's polyfit
                    coeffs = np.polyfit(x_valid, y_valid, 1)
                    results[f'{metric}_slope'] = coeffs[0]
                except (np.linalg.LinAlgError, ValueError, TypeError) as e:
                    # Handle computation errors
                    print(f"Warning: Slope calculation error for metric {metric}: {e}")
                    results[f'{metric}_slope'] = np.nan
            elif valid_count == 1:  # Only one valid point
                # For position, we'll use 0 slope if we only have one point
                # This indicates no change rather than unknown
                if metric == 'position':
                    results[f'{metric}_slope'] = 0.0
                else:
                    results[f'{metric}_slope'] = np.nan
            else:  # No valid points
                results[f'{metric}_slope'] = np.nan

            # Format slope for display
            if pd.notnull(results[f'{metric}_slope']):
                results[f'{metric}_slope'] = f"{results[f'{metric}_slope']:8.1f}"
            else:
                results[f'{metric}_slope'] = "       -"

        return pd.Series(results)
    # --- End of inner function ---

    print("✓ Starting trend analysis by grouping page/query combinations...")
    # Apply the analysis function to each group
    # Handle potential errors during apply (e.g., unexpected data types)
    try:
        # Using include_groups=False to avoid deprecation warning
        analysis_results = combined_df.groupby(['page', 'query'], observed=True, dropna=False).apply(
            analyze_single_group, include_groups=False).reset_index()
        print(f"✓ Trend analysis complete. Found {len(analysis_results)} unique page/query combinations.")
    except Exception as e:
        print(f"Error during groupby/apply operation for trend analysis: {e}")
        return pd.DataFrame()  # Return empty DF on error

    # Optional: Round slopes for cleaner display
    for metric in metrics:
        col_name = f'{metric}_slope'
        if col_name in analysis_results.columns:
            analysis_results[col_name] = analysis_results[col_name].round(2)

    # Calculate latest values from time series
    def get_latest_non_zero(series):
        """Get the latest non-zero value from a time series list."""
        try:
            # Convert string representation back to list if needed
            if isinstance(series, str):
                series = eval(series)
            # Return first non-zero value from reversed list, or 0 if none found
            for val in reversed(series):
                if val and val > 0:
                    return val
            return 0
        except:
            return 0

    # Extract latest values for impact score calculation
    analysis_results['latest_impressions'] = analysis_results['impressions_ts'].apply(get_latest_non_zero)
    analysis_results['latest_position'] = analysis_results['position_ts'].apply(get_latest_non_zero)

    # Calculate impact score (higher impressions and better position = higher score)
    # Normalize components to 0-1 range
    max_impressions = analysis_results['latest_impressions'].max()
    max_position = analysis_results['latest_position'].max()
    
    # Avoid division by zero
    if max_impressions > 0 and max_position > 0:
        # Position score is inverted (lower position is better)
        analysis_results['impact_score'] = (
            (analysis_results['latest_impressions'] / max_impressions) * 
            (1 - (analysis_results['latest_position'] / max_position))
        ) * 100  # Scale to 0-100
        # Round impact scores
        analysis_results['impact_score'] = analysis_results['impact_score'].round(1)
    else:
        # If no valid data, set impact scores to 0
        analysis_results['impact_score'] = 0

    return analysis_results


# --- Modify the main() function ---

def main():
    """Main execution function."""
    # 1. Authenticate
    gsc_service = authenticate_gsc()

    # 2. Find most recent date
    latest_date = find_most_recent_gsc_data_date(gsc_service, SITE_URL)
    if not latest_date:
        print("\nCannot proceed without a valid recent date.")
        sys.exit(1)
    print(f"\nSuccess: Most recent GSC data available is for: {latest_date.strftime('%Y-%m-%d')}")

    # 3. Determine dates to fetch
    dates_to_fetch = [latest_date - timedelta(days=i) for i in range(NUM_DAYS_TO_FETCH)][::-1]
    print(f"\nPreparing to fetch/load data for {NUM_DAYS_TO_FETCH} days:")
    print(f"  Dates: {[d.strftime('%Y-%m-%d') for d in dates_to_fetch]}")

    # 4. Fetch/load daily data
    daily_dataframes = {}
    api_calls_made = 0
    cache_loads_made = 0
    all_data_loaded = True
    
    for target_date in dates_to_fetch:
        date_str = target_date.strftime('%Y-%m-%d')
        cache_filename = os.path.join(CACHE_DIR, f"gsc_data_{date_str}.csv")
        cache_exists = os.path.exists(cache_filename)
        
        df_day = get_gsc_data_for_day(gsc_service, SITE_URL, target_date)
        
        # Track which source was used
        if cache_exists and not df_day.empty:
            cache_loads_made += 1
        elif not df_day.empty:
            api_calls_made += 1
            
        # Even if df_day is empty, store it to represent the day
        daily_dataframes[target_date] = df_day
        
        # Check if loading/fetching failed *and* cache doesn't exist
        if df_day.empty and not cache_exists:
             print(f"⚠️ Warning: Data could not be fetched or loaded for {date_str}. Trend analysis might be incomplete.")
             all_data_loaded = False

    if not all_data_loaded:
         print("\n⚠️ Warning: Data loading was incomplete. Proceeding with available data.")
    
    print(f"\n📊 Data source summary: {cache_loads_made} days loaded from cache, {api_calls_made} days fetched from API")

    # --- ADD TREND ANALYSIS STEP ---
    # 5. Perform Trend Analysis
    trend_results_df = analyze_trends(daily_dataframes)

    # 6. Display Trend Analysis Results
    if not trend_results_df.empty:
        # Configure pandas display settings for better table formatting
        pd.set_option('display.max_rows', 30)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.expand_frame_repr', False)
        pd.set_option('display.max_colwidth', None)
        
        # Define column mappings
        main_display_columns = ['Page', 'Query', 'Impressions TS', 'Impressions Slope', 'Clicks TS', 'Clicks Slope', 'Position TS', 'Position Slope']
        main_df_columns = ['page', 'query', 'impressions_ts', 'impressions_slope', 'clicks_ts', 'clicks_slope', 'position_ts', 'position_slope']
        
        # Define impact table column mappings
        impact_display_columns = ['Page', 'Query', 'Latest Position', 'Latest Impressions', 'Impact Score', 'Impressions TS', 'Position TS']
        impact_df_columns = ['page', 'query', 'latest_position', 'latest_impressions', 'impact_score', 'impressions_ts', 'position_ts']

        # Calculate column widths based on data
        def get_column_widths(df, display_columns, df_columns):
            """Calculate required width for each column based on data and header."""
            widths = []
            for display_col, df_col in zip(display_columns, df_columns):
                # Get maximum width of data in column
                data_width = max(len(str(x)) for x in df[df_col])
                # Compare with header width
                widths.append(max(data_width, len(display_col)))
            return widths

        # Function to print markdown table header
        def print_markdown_header(columns, widths):
            """Print markdown table header with specified column widths."""
            # Print header row with padded column names
            header_cells = []
            for col, width in zip(columns, widths):
                header_cells.append(col.ljust(width))
            print("| " + " | ".join(header_cells) + " |")

        # Function to truncate and pad query for all tables
        def truncate_and_pad_query(query, max_length=40):
            """Truncate query string if longer than max_length and pad for alignment."""
            if not query:
                return " " * max_length
            if len(query) > max_length:
                return query[:max_length-3] + "...".ljust(3)
            return query.ljust(max_length)

        # Process the dataframe for display
        display_df = trend_results_df.copy()
        
        # 1. Extract page path from full URL
        if 'page' in display_df.columns:
            display_df['page'] = display_df['page'].str.replace(r'https://mikelev.in/futureproof/', '', regex=True)
            # Further trim endings
            display_df['page'] = display_df['page'].str.replace(r'/$', '', regex=True)
            # Pad page column for alignment
            max_page_len = display_df['page'].str.len().max()
            display_df['page'] = display_df['page'].str.ljust(max_page_len)
            
        # 1.5 Truncate and pad queries
        display_df['query'] = display_df['query'].apply(lambda x: truncate_and_pad_query(x))
            
        # 2. Convert time series lists to more compact string representations with padding
        for col in ['impressions_ts', 'clicks_ts', 'position_ts']:
            if col in display_df.columns:
                # Format time series values with consistent width
                display_df[col] = display_df[col].apply(
                    lambda x: '[' + ','.join([str(int(i)).rjust(3) if isinstance(i, (int, float)) and not pd.isna(i) else '  -' for i in x]) + ']'
                )
                
        # 3. Format slope values with consistent decimal places and padding
        # Note: Slopes are already formatted in analyze_trends, so we don't need to format them again here

        print("\n### Top 20 by Impression Increase")
        top_impressions = display_df.sort_values('impressions_slope', ascending=False, na_position='last').head(TOP_N)
        widths = get_column_widths(top_impressions, main_display_columns, main_df_columns)
        print_markdown_header(main_display_columns, widths)
        for _, row in top_impressions.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['impressions_ts']).rjust(widths[2])} | {str(row['impressions_slope']).rjust(widths[3])} | {str(row['clicks_ts']).rjust(widths[4])} | {str(row['clicks_slope']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} | {str(row['position_slope']).rjust(widths[7])} |")

        print("\n### Top 20 by Impression Decrease")
        bottom_impressions = display_df.sort_values('impressions_slope', ascending=True, na_position='last').head(TOP_N)
        widths = get_column_widths(bottom_impressions, main_display_columns, main_df_columns)
        print_markdown_header(main_display_columns, widths)
        for _, row in bottom_impressions.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['impressions_ts']).rjust(widths[2])} | {str(row['impressions_slope']).rjust(widths[3])} | {str(row['clicks_ts']).rjust(widths[4])} | {str(row['clicks_slope']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} | {str(row['position_slope']).rjust(widths[7])} |")

        print("\n### Top 20 by Position Improvement (Lower is Better)")
        numeric_df = trend_results_df.copy()
        numeric_df = numeric_df.dropna(subset=['position_slope'])
        top_positions_idx = numeric_df.sort_values('position_slope', ascending=True).head(TOP_N).index
        top_positions = display_df.loc[top_positions_idx]
        widths = get_column_widths(top_positions, main_display_columns, main_df_columns)
        print_markdown_header(main_display_columns, widths)
        for _, row in top_positions.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['impressions_ts']).rjust(widths[2])} | {str(row['impressions_slope']).rjust(widths[3])} | {str(row['clicks_ts']).rjust(widths[4])} | {str(row['clicks_slope']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} | {str(row['position_slope']).rjust(widths[7])} |")

        print("\n### Top 20 by Position Decline (Higher is Worse)")
        bottom_positions_idx = numeric_df.sort_values('position_slope', ascending=False).head(TOP_N).index
        bottom_positions = display_df.loc[bottom_positions_idx]
        widths = get_column_widths(bottom_positions, main_display_columns, main_df_columns)
        print_markdown_header(main_display_columns, widths)
        for _, row in bottom_positions.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['impressions_ts']).rjust(widths[2])} | {str(row['impressions_slope']).rjust(widths[3])} | {str(row['clicks_ts']).rjust(widths[4])} | {str(row['clicks_slope']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} | {str(row['position_slope']).rjust(widths[7])} |")

        print("\n### Top 20 High-Impact Queries (Best Position + Most Impressions)")
        # Create a display version of the impact table data
        impact_display_df = display_df.copy()
        # Format numeric columns for the impact tables
        impact_display_df['latest_position'] = impact_display_df['latest_position'].apply(lambda x: f"{x:8.1f}")
        impact_display_df['latest_impressions'] = impact_display_df['latest_impressions'].apply(lambda x: f"{x:8d}")
        impact_display_df['impact_score'] = impact_display_df['impact_score'].apply(lambda x: f"{x:8.1f}")
        
        top_impact_idx = trend_results_df.sort_values('impact_score', ascending=False).head(TOP_N).index
        top_impact = impact_display_df.loc[top_impact_idx]
        widths = get_column_widths(top_impact, impact_display_columns, impact_df_columns)
        print_markdown_header(impact_display_columns, widths)
        for _, row in top_impact.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['latest_position']).rjust(widths[2])} | {str(row['latest_impressions']).rjust(widths[3])} | {str(row['impact_score']).rjust(widths[4])} | {str(row['impressions_ts']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} |")

        print("\n### Bottom 20 Low-Impact Queries (Poor Position + Few Impressions)")
        bottom_impact_idx = trend_results_df[trend_results_df['impact_score'] > 0].sort_values('impact_score', ascending=True).head(TOP_N).index
        bottom_impact = impact_display_df.loc[bottom_impact_idx]
        widths = get_column_widths(bottom_impact, impact_display_columns, impact_df_columns)
        print_markdown_header(impact_display_columns, widths)
        for _, row in bottom_impact.iterrows():
            print(f"| {str(row['page']).ljust(widths[0])} | {str(row['query']).ljust(widths[1])} | {str(row['latest_position']).rjust(widths[2])} | {str(row['latest_impressions']).rjust(widths[3])} | {str(row['impact_score']).rjust(widths[4])} | {str(row['impressions_ts']).rjust(widths[5])} | {str(row['position_ts']).rjust(widths[6])} |")

        # Add analysis prompt with dynamic variables
        start_date = dates_to_fetch[0].strftime('%B %-d')
        end_date = dates_to_fetch[-1].strftime('%-d, %Y')
        
        print(f"""
### Analysis Prompt
[Analysis Parameters: Top {TOP_N} Results Per Category, {NUM_DAYS_TO_FETCH}-Day Trend Period]

Analyze the Google Search Console trend analysis output previously provided for the site `{SITE_URL}` (covering the period {start_date}-{end_date}). Based *only* on that data, provide a prioritized list of actionable traffic growth suggestions and loss mitigation strategies.

Your goal is to identify both opportunities and risks revealed by the trends, including broad strategic directions and specific content pieces. Structure your response to cover the following areas, ensuring each point includes specific examples from the data (pages, queries, metrics) and concrete recommended actions:

1.  **Top Movers Analysis (Gains & Losses):**
    * Identify the most promising opportunities among pages/queries showing strong positive impression growth.
    * Highlight queries gaining significant impressions *and* improving in position simultaneously.
    * **Critically analyze pages/queries showing concerning drops in impressions.** What patterns emerge among the declining content?
    * Recommend specific actions to both capitalize on growth and mitigate concerning losses.

2.  **Position Changes Analysis:**
    * Which pages making significant ranking jumps (large negative `position_slope`) represent the best targets for further optimization?
    * **Identify content experiencing concerning ranking declines (large positive `position_slope`).** Are there common characteristics among declining pages?
    * Are there thematic patterns among both the fastest climbers and steepest decliners that suggest broader content opportunities or risks?
    * Recommend actions to both consolidate ranking improvements and stop/reverse ranking slides.

3.  **High-Impact & Problem Area Analysis:**
    * Based on the "High-Impact Queries" list, which content currently delivers the most value and how can it be reinforced?
    * **Examine the "Low-Impact Queries" list to identify previously better-performing content that may need intervention.**
    * Identify the **top 1-3 individual page/query pairs** representing:
        a) The largest "unrealized potential" (high impressions but poor ranking)
        b) **The most concerning "performance deterioration" (significant drops in both impressions and position)**
    * For each identified pair, clearly state the page, query, metrics, and trend direction.
    * **Critically, based on analyzing both opportunity and problem areas, identify and recommend:**
        a) The single most promising *new article topic* to pursue
        b) The single most important *existing content piece to rescue/improve*
    * Justify why these specific pieces deserve prioritization over other candidates.

4.  **Prioritized Strategic Recommendations:**
    * Synthesize the findings from the above points, balancing growth opportunities with risk mitigation.
    * What are the top 2-3 overarching strategic priorities? Ensure these recommendations explicitly cover:
        a) **Defensive priorities** (stopping losses, rescuing declining content)
        b) **Growth priorities** (both broad themes and specific new content opportunities)
    * Justify these priorities with clear data trends from both positive and negative movement tables.

5.  **Recommendation Summary Table:**
    * Conclude your response with a summary table consolidating the most important actionable recommendations.
    * Use the following columns: `Page URL`, `Query`, `Current Trend`, `Key Observation`, `Recommended Action`, `Priority`.
    * Include both growth opportunities and problem areas requiring intervention.
    * Assign priority (High, Medium, Low) based on both potential impact and urgency of intervention as revealed by the trend data.
    * Ensure the table captures recommendations for:
        a) Content showing positive momentum to amplify
        b) **Content showing concerning declines to address**
        c) New content opportunities to pursue
        d) Technical or structural improvements suggested by the patterns

Please ensure all recommendations are concrete and directly linked to the patterns observed in the provided GSC trend data output, including both positive and negative trends.""")

        print("\n--- End Copy Here ---\n")

        print("\n--- DataFrame Info ---")
        trend_results_df.info()

        # Save the final trend analysis results using the original dataframe (with full URLs)
        final_output_filename = os.path.join(CACHE_DIR, f"gsc_trend_analysis_{dates_to_fetch[0].strftime('%Y%m%d')}_to_{dates_to_fetch[-1].strftime('%Y%m%d')}.csv")
        try:
            # Ensure cache directory exists
            os.makedirs(CACHE_DIR, exist_ok=True)
            trend_results_df.to_csv(final_output_filename, index=False)
            print(f"\n✓ Saved final trend analysis to: {final_output_filename}")
        except Exception as e:
            print(f"\nWarning: Failed to save final trend analysis results. Error: {e}")

    else:
        print("\nTrend analysis could not be completed.")

    print("\nScript finished.")


if __name__ == "__main__":
    if not SITE_URL or SITE_URL == "sc-domain:yourdomain.com":
        print("Error: Please update the 'SITE_URL' variable in the script configuration.")
        sys.exit(1)
    main()
