import os
import re
import yaml
import random # <--- Added for the shuffle
from pathlib import Path
from datetime import datetime

# Path to your Jekyll posts on the Honeybot
POSTS_DIR = Path("/home/mike/www/mikelev.in/_posts")
BASE_URL = "https://mikelev.in"

def get_playlist(recent_n=10):
    """
    Returns a playlist: Recent N (sorted date desc) + Rest (shuffled).
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

            # 3. Construct URL
            slug = frontmatter.get('permalink', '').strip('/')
            if not slug:
                slug = filename[11:].rsplit('.', 1)[0]
            url = f"{BASE_URL}/{slug}/"
            
            # 4. Clean Text
            clean_text = clean_markdown(body_text)
            
            all_articles.append({
                'date': post_date,
                'title': frontmatter.get('title', slug.replace('-', ' ')),
                'url': url,
                'content': clean_text
            })

        # Sort ALL by date first to identify the "Recent" block
        all_articles.sort(key=lambda x: x['date'], reverse=True)
        
        # Split the lists
        recent_articles = all_articles[:recent_n]
        archive_articles = all_articles[recent_n:]
        
        # Shuffle the archive to keep it fresh
        random.shuffle(archive_articles)
        
        # Combine them
        return recent_articles + archive_articles

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
    
    # Reflow Logic (The Hard Wrap Fix)
    text = re.sub(r'\n\s*\n', '||PARAGRAPH||', text)
    text = re.sub(r'\n', ' ', text)
    text = text.replace('||PARAGRAPH||', '\n')
    text = re.sub(r' +', ' ', text).strip()
    
    return text