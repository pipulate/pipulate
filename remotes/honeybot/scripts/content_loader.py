import os
import re
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

def check_for_updates():
    """
    Checks if the _posts directory has changed since the last playlist generation.
    Returns True if updates are detected.
    """
    global _last_scan_time, _last_file_count
    
    try:
        # Get directory stats
        stat = POSTS_DIR.stat()
        current_mtime = stat.st_mtime
        
        # Also check file count (sometimes mtime on dir doesn't update on all FS)
        current_files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
        current_count = len(current_files)
        
        # First run logic
        if _last_scan_time == 0:
            _last_scan_time = current_mtime
            _last_file_count = current_count
            return False

        # Detection logic
        if current_mtime > _last_scan_time or current_count != _last_file_count:
            # Update cache
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
        
        global _last_scan_time, _last_file_count
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

    # --- Strip Liquid Tags ({% ... %}) ---
    # This removes {% raw %}, {% endraw %}, {% include ... %}, etc.
    text = re.sub(r'\{%.*?%\}', '', text)
    
    # --- Strip Liquid Variables ({{ ... }}) ---
    # Optional, but good practice if you use them in text
    text = re.sub(r'\{\{.*?\}\}', '', text)

    # Remove Code Blocks
    text = re.sub(r'```.*?```', ' [Skipping code block] ', text, flags=re.DOTALL)
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
            return f" URL from {hostname} "
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
    
    return text