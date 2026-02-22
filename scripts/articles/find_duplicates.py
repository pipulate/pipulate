#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
from datetime import datetime
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# --- CONFIGURATION ---
POSTS_DIRECTORY = "/home/mike/repos/MikeLev.in/_posts"
SIMILARITY_THRESHOLD = 0.85  # Flag if body text is 85% or more similar

def get_bigrams(text):
    """Chop text into a set of overlapping two-word pairs for lightning-fast comparison."""
    words = text.lower().split()
    return set(zip(words[:-1], words[1:]))

def fast_similarity(text1, text2):
    """Calculates Jaccard similarity using bigrams. O(N) instead of difflib's O(N^2)."""
    b1 = get_bigrams(text1)
    b2 = get_bigrams(text2)
    
    if not b1 or not b2:
        return 0.0
        
    intersection = len(b1 & b2)
    union = len(b1 | b2)
    return intersection / union if union > 0 else 0.0

def get_post_data(posts_dir, progress):
    """Parses Jekyll posts with a progress bar."""
    posts_data = []
    if not os.path.isdir(posts_dir):
        progress.console.print(f"[red]Error: Directory not found at {posts_dir}[/red]")
        return []

    # Get file list first so we know the total for the progress bar
    all_files = [f for f in os.listdir(posts_dir) if f.endswith(('.md', '.markdown'))]
    
    task = progress.add_task("[cyan]Parsing YAML Frontmatter...", total=len(all_files))

    for filename in all_files:
        filepath = os.path.join(posts_dir, filename)
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

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
            pass
            
        progress.advance(task)
            
    return posts_data

def find_adjacent_duplicates(posts, threshold, progress):
    """Checks adjacent posts for high similarity using Bigram Jaccard algorithm."""
    posts_by_day = defaultdict(list)
    for post in posts:
        posts_by_day[post['date']].append(post)

    duplicates = []
    
    # Only days with more than 1 post need comparison
    days_to_check = {d: p for d, p in posts_by_day.items() if len(p) > 1}
    
    task = progress.add_task("[green]Calculating AI Ghost Variations...", total=len(days_to_check))
    
    for date, daily_posts in sorted(days_to_check.items()):
        daily_posts.sort(key=lambda x: x['sort_order'])
        
        for i in range(len(daily_posts) - 1):
            post1 = daily_posts[i]
            post2 = daily_posts[i + 1]
            
            # Use our new lightning-fast math instead of difflib
            similarity = fast_similarity(post1['body'], post2['body'])
            
            if similarity >= threshold:
                duplicates.append({
                    'date': date,
                    'post1': post1,
                    'post2': post2,
                    'similarity': similarity * 100 
                })
                
        progress.advance(task)
                
    return duplicates

def print_report(duplicates):
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

    # The magic of Rich Progress Context Manager
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True  # Clears the progress bar when done!
    ) as progress:
        
        posts = get_post_data(POSTS_DIRECTORY, progress)
        duplicates = find_adjacent_duplicates(posts, args.threshold, progress)
        
    # Print the final report after the progress bars disappear
    print_report(duplicates)