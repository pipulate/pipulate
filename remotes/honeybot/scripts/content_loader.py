import os
import re
import yaml
from pathlib import Path
from datetime import datetime

# Path to your Jekyll posts on the Honeybot
POSTS_DIR = Path("/home/mike/www/mikelev.in/_posts")
BASE_URL = "https://mikelev.in"

def get_playlist(limit=10):
    """
    Returns a list of articles sorted Newest -> Oldest.
    Structure: [{'title', 'date', 'url', 'content'}, ...]
    """
    articles = []
    
    try:
        # Find all markdown files
        files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
        
        for filepath in files:
            filename = filepath.name
            
            # 1. Extract Date from filename (YYYY-MM-DD-title.md)
            try:
                date_str = filename[:10]
                post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue # Skip non-conforming files

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

            # 3. Construct URL
            # Priority: Frontmatter permalink > Filename slug
            slug = frontmatter.get('permalink', '').strip('/')
            if not slug:
                # Remove date (first 11 chars) and extension
                slug = filename[11:].rsplit('.', 1)[0]
            
            url = f"{BASE_URL}/{slug}/"
            
            # 4. Clean Text for TTS
            clean_text = clean_markdown(body_text)
            
            articles.append({
                'date': post_date,
                'title': frontmatter.get('title', slug.replace('-', ' ')),
                'url': url,
                'content': clean_text
            })

        # Sort Reverse Chronological (Newest First)
        articles.sort(key=lambda x: x['date'], reverse=True)
        
        return articles[:limit]

    except Exception as e:
        print(f"Librarian Error: {e}")
        return []

def clean_markdown(text):
    """Sanitizes Markdown for the Piper TTS engine."""
    # Remove Code Blocks
    text = re.sub(r'```.*?```', ' [Code block omitted] ', text, flags=re.DOTALL)
    # Remove Inline Code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove Images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove Links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove Headers/Bold/Italic markers
    text = re.sub(r'[*_#]', '', text)
    # Collapse whitespace
    text = re.sub(r'\n+', '\n', text).strip()
    return text