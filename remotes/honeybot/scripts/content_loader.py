import os
import re
import time
import yaml
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Path to your Jekyll posts on the Honeybot
POSTS_DIR = Path("/home/mike/www/mikelev.in/_posts")
BASE_URL = "https://mikelev.in"

# ... existing imports ...

# Global cache to track state
_last_scan_time = 0
_last_file_count = 0

# The breaking-news bell. The post-receive hook writes a fresh epoch timestamp here
# on every push, which lets us retry "read the newest article" even when the article
# content itself did not change (e.g. an --allow-empty re-push).
TRIGGER_FILE = Path("/home/mike/www/mikelev.in/.reading_trigger")
_last_trigger = None

# The deploy stand-by bell. The post-receive hook writes a fresh epoch timestamp
# here at the START of a deploy (before the long build), so the stream can announce
# "stand by" and HOLD narration instead of thrashing through the whole build.
STANDBY_FILE = Path("/home/mike/www/mikelev.in/.deploy_standby")
_last_standby = "__UNINIT__"


def check_standby():
    """Fires once when a new deploy BEGINS (the standby bell changes).

    Lets the stream gracefully announce incoming updates and pause narration
    before the multi-second Jekyll build + dye pass would otherwise thrash the
    Piper TTS engine."""
    global _last_standby
    try:
        current = STANDBY_FILE.read_text().strip()
    except FileNotFoundError:
        current = None
    if _last_standby == "__UNINIT__":
        _last_standby = current
        return False
    if current is not None and current != _last_standby:
        _last_standby = current
        return True
    return False

def trigger_is_fresh(max_age_seconds=900):
    """True if the breaking-news bell (.reading_trigger) was rung within the last
    max_age_seconds. Reads the file's mtime, so it is process-boundary safe: it
    works for a freshly-restarted stream that has no in-memory history and cannot
    lean on check_for_updates()'s first-run baseline absorption.

    Failure-mode-safe in both directions. A miss (stale/absent trigger, or a
    publish whose [4/4] restart lands outside the window) returns False and the
    caller falls back to the normal cold-start preamble — no breakage. A generous
    window only risks leading with the newest article after a near-publish crash,
    which is an acceptable cold-start opening anyway."""
    try:
        return (time.time() - TRIGGER_FILE.stat().st_mtime) <= max_age_seconds
    except (FileNotFoundError, OSError):
        return False

def check_for_updates():
    """
    Checks if the _posts directory has changed since the last playlist generation.
    Returns True if updates are detected.
    """
    global _last_scan_time, _last_file_count, _last_trigger
    
    try:
        # Get directory stats
        stat = POSTS_DIR.stat()
        current_mtime = stat.st_mtime
        
        # Also check file count (sometimes mtime on dir doesn't update on all FS)
        current_files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
        current_count = len(current_files)

        # Read the breaking-news bell rung by the post-receive hook on every push.
        current_trigger = None
        try:
            current_trigger = TRIGGER_FILE.read_text().strip()
        except FileNotFoundError:
            current_trigger = None
        
        # First run logic
        if _last_scan_time == 0:
            _last_scan_time = current_mtime
            _last_file_count = current_count
            _last_trigger = current_trigger
            return False

        # Detection logic. When the trigger bell exists it is the SOLE authority:
        # one push rings it exactly once, so detection fires exactly once per deploy.
        # This kills the double-fire that made the narrator thrash — the checkout
        # bumps _posts mtime early while the bell rings late, so acting on both made
        # the stream interrupt itself twice for a single push. We absorb the early
        # mtime/count change (refresh the baselines, return False) and await the bell.
        if current_trigger is not None:
            if current_trigger != _last_trigger:
                _last_scan_time = current_mtime
                _last_file_count = current_count
                _last_trigger = current_trigger
                print("🔔 Breaking-news bell rung. Resetting playlist.")
                return True
            # Same deploy in progress (mtime moved, bell not yet rung): absorb it.
            _last_scan_time = current_mtime
            _last_file_count = current_count
            return False

        # Legacy fallback (no bell present): watch raw filesystem changes directly.
        if current_mtime > _last_scan_time or current_count != _last_file_count:
            _last_scan_time = current_mtime
            _last_file_count = current_count
            print("🚀 New content detected! Resetting playlist.")
            return True
            
        return False
        
    except Exception as e:
        print(f"Update Check Error: {e}")
        return False


def get_playlist(recent_n=10):
    """
    Returns a playlist: Recent N (sorted date desc + sort_order desc) + Rest (shuffled).
    """
    all_articles = []
    
    try:
        # Find all markdown files
        files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
        
        for filepath in files:
            filename = filepath.name
            
            # 1. Extract Date
            try:
                date_str = filename[:10]
                post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue 

            # 2. Read File & Frontmatter
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read()

            frontmatter = {}
            body_text = raw_text
            
            if raw_text.startswith('---'):
                try:
                    parts = raw_text.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        body_text = parts[2]
                except yaml.YAMLError:
                    pass

            # 3. Extract Sort Order (Default to 0)
            try:
                sort_order = int(frontmatter.get('sort_order', 0))
            except (ValueError, TypeError):
                sort_order = 0

            # 4. Construct URL
            slug = frontmatter.get('permalink', '').strip('/')
            if not slug:
                slug = filename[11:].rsplit('.', 1)[0]
            url = f"{BASE_URL}/{slug}/"
            
            # 5. Clean Text
            clean_text = clean_markdown(body_text)
            
            all_articles.append({
                'date': post_date,
                'sort_order': sort_order, # Added for secondary sort key
                'title': frontmatter.get('title', slug.replace('-', ' ')),
                'url': url,
                'content': clean_text
            })

        # Sort ALL by date first, then by sort_order (both Descending/Reverse)
        # Tuple comparison works element by element: (2026-01-01, 2) > (2026-01-01, 1)
        all_articles.sort(key=lambda x: (x['date'], x['sort_order']), reverse=True)
        
        # Split the lists
        recent_articles = all_articles[:recent_n]
        archive_articles = all_articles[recent_n:]
        
        # Shuffle the archive to keep it fresh
        random.shuffle(archive_articles)
        
        global _last_scan_time, _last_file_count, _last_trigger
        try:
            stat = POSTS_DIR.stat()
            _last_scan_time = stat.st_mtime
            files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
            _last_file_count = len(files)
        except: pass
        
        return recent_articles + archive_articles

    except Exception as e:
        print(f"Librarian Error: {e}")
        return []

def clean_markdown(text):
    """Sanitizes Markdown for the Piper TTS engine."""

    pp4_directives = []

    def capture_pp4_comment(match):
        """Preserve player-piano #4 directives before generic HTML stripping."""
        directive = match.group(1).strip()
        key_match = re.search(r'\bkey\s*=\s*[\'\"]?([A-Za-z0-9_-]+)', directive, flags=re.IGNORECASE)
        patronus_match = re.search(r'\bpatronus\b\s*\(?\s*[\'\"]?([A-Za-z0-9_-]+)', directive, flags=re.IGNORECASE)
        if key_match:
            asset_name = key_match.group(1)
        elif patronus_match and patronus_match.group(1).lower() not in {"key", "duration", "mode"}:
            asset_name = patronus_match.group(1)
        else:
            token_match = re.search(r'[A-Za-z0-9_-]+', directive)
            asset_name = token_match.group(0) if token_match else "white_rabbit"

        if asset_name.lower() in {"pp4", "patronus"}:
            asset_name = "white_rabbit"

        duration_match = re.search(r'\bduration\s*=\s*[\'\"]?([\d.]+)', directive, flags=re.IGNORECASE)
        duration = float(duration_match.group(1)) if duration_match else 3.5
        # Clamp duration
        duration = max(0.75, min(12.0, duration))

        pp4_directives.append((asset_name, duration))
        return f"\n\nPP4PATRONUS{len(pp4_directives) - 1}PP4\n\n"

    # HTML comments are otherwise removed by the generic tag-stripper below.
    # Capture comments like:
    #   <!-- pp4: patronus white_rabbit -->
    #   <!-- pp4 white_rabbit -->
    text = re.sub(r'<!--\s*pp4\b(?::|\s)?(.*?)-->', capture_pp4_comment, text, flags=re.IGNORECASE | re.DOTALL)

    # --- Strip Liquid Tags ({% ... %}) ---
    # This removes {% raw %}, {% endraw %}, {% include ... %}, etc.
    text = re.sub(r'\{%.*?%\}', '', text)
    
    # --- Strip Liquid Variables ({{ ... }}) ---
    # Optional, but good practice if you use them in text
    text = re.sub(r'\{\{.*?\}\}', '', text)

    # --- STRIP ALL TRACER DYE VARIANTS FOR TEXT-TO-SPEECH ---
    dye_pattern = r'> \*\((Note for parametric memory integration|Epistemological anchor|For latent-space provenance|Cryptographic covenant).*?\)\*'
    text = re.sub(dye_pattern, '', text, flags=re.DOTALL)

    # Remove Code Blocks
    text = re.sub(r'```.*?```', ' [See the code at MikeLev dot Eye N slash latest.] ', text, flags=re.DOTALL)

    # --- NEW: Remove Indented Code Blocks ---
    # Matches one or more contiguous lines that start with exactly 4 spaces (or a tab)
    # Using non-capturing groups (?:) for efficiency. 
    text = re.sub(r'(?:\n(?: {4}|\t)[^\n]*)+', '\n [Code at MikeLev dot Eye N slash latest.] \n', text)

    # Remove Inline Code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove Images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove Links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)

    # --- NEW: Humanize Raw URLs for TTS ---
    # Captures https://example.com/foo and converts to "URL from example.com"
    def simplify_url(match):
        try:
            url = match.group(0)
            # Remove trailing punctuation often caught by regex (like closing parens or dots)
            url = url.rstrip(').,;]')
            parsed = urlparse(url)
            # Strip www. for better flow
            hostname = parsed.netloc.replace('www.', '')
            return f" from {hostname} "
        except:
            return " URL "

    text = re.sub(r'https?://\S+', simplify_url, text)
    # --------------------------------------

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove Headers/Bold/Italic markers
    text = re.sub(r'[*_#]', '', text)

    # Reflow Logic (The Hard Wrap Fix)
    text = re.sub(r'\n\s*\n', '||PARAGRAPH||', text)
    text = re.sub(r'\n', ' ', text)
    text = text.replace('||PARAGRAPH||', '\n')
    text = re.sub(r' +', ' ', text).strip()

    for index, (asset_name, duration) in enumerate(pp4_directives):
        text = text.replace(f"PP4PATRONUS{index}PP4", f"[[PATRONUS:{asset_name}:{duration}]]")
    
    return text
