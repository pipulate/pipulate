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
    """Checks adjacent posts and tracks ALL comparisons to establish a baseline."""
    posts_by_day = defaultdict(list)
    for post in posts:
        posts_by_day[post['date']].append(post)

    duplicates = []
    all_comparisons = []
    
    days_to_check = {d: p for d, p in posts_by_day.items() if len(p) > 1}
    task = progress.add_task("[green]Calculating AI Ghost Variations...", total=len(days_to_check))
    
    for date, daily_posts in sorted(days_to_check.items()):
        daily_posts.sort(key=lambda x: x['sort_order'])
        
        for i in range(len(daily_posts) - 1):
            post1 = daily_posts[i]
            post2 = daily_posts[i + 1]
            
            similarity = fast_similarity(post1['body'], post2['body'])
            sim_percentage = similarity * 100
            
            comp_data = {
                'date': date,
                'post1': post1,
                'post2': post2,
                'similarity': sim_percentage 
            }
            
            all_comparisons.append(comp_data)
            
            if sim_percentage >= (threshold * 100):
                duplicates.append(comp_data)
                
        progress.advance(task)
                
    return duplicates, all_comparisons

def print_report(duplicates, all_comparisons, threshold):
    console = Console()
    
    # 1. THE DUPLICATE REPORT
    console.print("\n" + "="*70)
    console.print(f"[bold bright_blue]Article Duplication Report (Threshold: {threshold*100:.1f}%)[/bold bright_blue]")
    console.print("="*70)

    if not duplicates:
        console.print("✅ [bold green]All Clear![/bold green] No adjacent articles exceed the similarity threshold.")
    else:
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

    # 2. THE DATA PROBE (Top 5 Closest Matches)
    console.print("\n" + "="*70)
    console.print("[bold bright_yellow]Data Probe: Top 5 Closest Adjacent Matches[/bold bright_yellow]")
    console.print("="*70)
    
    if not all_comparisons:
        console.print("[dim]Not enough multiple-post days to perform comparisons.[/dim]")
        return
        
    # Sort all comparisons by highest similarity
    all_comparisons.sort(key=lambda x: x['similarity'], reverse=True)
    top_matches = all_comparisons[:5]
    
    probe_table = Table(box=box.ROUNDED, show_lines=True)
    probe_table.add_column("Date", style="magenta")
    probe_table.add_column("Similarity", justify="right")
    probe_table.add_column("Post 1", style="dim white")
    probe_table.add_column("Post 2", style="bright_white")
    
    for match in top_matches:
        p1 = match['post1']
        p2 = match['post2']
        
        # Color code the similarity based on how close it is to the threshold
        sim_val = match['similarity']
        sim_str = f"{sim_val:.1f}%"
        
        if sim_val >= (threshold * 100):
            sim_str = f"[bold red]{sim_str}[/bold red]"
        elif sim_val >= (threshold * 100) - 15: # Within 15% of threshold (Near Miss)
            sim_str = f"[bold yellow]{sim_str}[/bold yellow]"
        else:
            sim_str = f"[cyan]{sim_str}[/cyan]"
            
        probe_table.add_row(
            str(match['date']),
            sim_str,
            f"[{p1['sort_order']}] {p1['filename']}",
            f"[{p2['sort_order']}] {p2['filename']}"
        )
        
    console.print(probe_table)
    console.print(f"\n💡 [dim]This shows the natural similarity of your articles. If the top matches are low (e.g., 20%), your dataset is very clean.[/dim]\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Find highly similar adjacent articles.")
    parser.add_argument('-t', '--threshold', type=float, default=SIMILARITY_THRESHOLD, 
                        help="Similarity threshold (0.0 to 1.0). Default is 0.85.")
    args = parser.parse_args()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True 
    ) as progress:
        posts = get_post_data(POSTS_DIRECTORY, progress)
        duplicates, all_comparisons = find_adjacent_duplicates(posts, args.threshold, progress)
        
    print_report(duplicates, all_comparisons, args.threshold)