#!/usr/bin/env python3
import os
import sys
import yaml
import difflib
import argparse
from datetime import datetime
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich import box

# --- CONFIGURATION ---
POSTS_DIRECTORY = "/home/mike/repos/MikeLev.in/_posts"
SIMILARITY_THRESHOLD = 0.85  # Flag if body text is 85% or more similar

def get_post_data(posts_dir):
    """Parses Jekyll posts, extracting the body separately from the YAML."""
    posts_data = []
    if not os.path.isdir(posts_dir):
        print(f"Error: Directory not found at {posts_dir}", file=sys.stderr)
        return []

    for filename in os.listdir(posts_dir):
        if not filename.endswith(('.md', '.markdown')):
            continue
            
        filepath = os.path.join(posts_dir, filename)
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Strip YAML frontmatter to only compare the actual article body
            if content.startswith('---'):
                parts = content.split('---', 2)
                front_matter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip() if len(parts) > 2 else ""
            else:
                front_matter = {}
                body = content.strip()

            sort_order = int(front_matter.get('sort_order', 0))
            
            posts_data.append({
                'filename': filename,
                'date': post_date,
                'sort_order': sort_order,
                'body': body
            })
        except Exception:
            continue
            
    return posts_data

def find_adjacent_duplicates(posts, threshold):
    """Groups by date, sorts by order, and checks adjacent posts for high similarity."""
    posts_by_day = defaultdict(list)
    for post in posts:
        posts_by_day[post['date']].append(post)

    duplicates = []
    
    for date, daily_posts in sorted(posts_by_day.items()):
        # Sort chronologically within the day using sort_order
        daily_posts.sort(key=lambda x: x['sort_order'])
        
        # Compare adjacent posts
        for i in range(len(daily_posts) - 1):
            post1 = daily_posts[i]
            post2 = daily_posts[i + 1]
            
            # Calculate similarity ratio (0.0 to 1.0)
            similarity = difflib.SequenceMatcher(None, post1['body'], post2['body']).ratio()
            
            if similarity >= threshold:
                duplicates.append({
                    'date': date,
                    'post1': post1,
                    'post2': post2,
                    'similarity': similarity * 100  # Convert to percentage
                })
                
    return duplicates

def print_report(duplicates):
    """Prints a Rich table of the suspected duplicates."""
    console = Console()
    console.print("\n" + "="*70)
    console.print("[bold bright_blue]Article Duplication/Ghost Variation Report[/bold bright_blue]")
    console.print("="*70)

    if not duplicates:
        console.print("✅ [bold green]All Clear![/bold green] No adjacent articles exceed the similarity threshold.")
        return

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("Date", style="magenta")
    table.add_column("Similarity", justify="right", style="bold red")
    table.add_column("Older Version (Lower Sort)", style="dim white")
    table.add_column("Newer Version (Higher Sort)", style="bright_white")

    for dup in duplicates:
        p1 = dup['post1']
        p2 = dup['post2']
        
        table.add_row(
            str(dup['date']),
            f"{dup['similarity']:.1f}%",
            f"[{p1['sort_order']}] {p1['filename']}",
            f"[{p2['sort_order']}] {p2['filename']}"
        )
        
    console.print(table)
    console.print("\n💡 [dim]Recommendation: Usually, you want to keep the Newer Version (Higher Sort) and delete the Older Version.[/dim]")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Find highly similar adjacent articles.")
    parser.add_argument('-t', '--threshold', type=float, default=SIMILARITY_THRESHOLD, 
                        help="Similarity threshold (0.0 to 1.0). Default is 0.85.")
    args = parser.parse_args()

    print("Scanning articles and calculating text similarities. This may take a moment...")
    posts = get_post_data(POSTS_DIRECTORY)
    duplicates = find_adjacent_duplicates(posts, args.threshold)
    print_report(duplicates)