#!/usr/bin/env python3
"""
ls2.py

A utility to list Jekyll markdown files in a directory, outputting their 
absolute paths followed by commented-out telemetry data (Index, Order, 
Tokens, and Bytes) specifically formatted for easy copy-pasting into 
Pipulate's foo_files.py context engine.

Optimized to stream output instantly to the terminal.
"""

import os
import sys
import yaml
import argparse
from datetime import datetime

# Gracefully handle tiktoken if available, fallback to word count if not
try:
    import tiktoken
    def count_tokens(text: str, model: str = "gpt-4o") -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            return len(text.split())
except ImportError:
    def count_tokens(text: str, model: str = "") -> int:
        return len(text.split())

def fast_get_sort_order(filepath):
    """Reads only the YAML frontmatter to extract sort_order extremely fast."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if not first_line.startswith('---'):
                return 0
            
            yaml_content = []
            for line in f:
                if line.startswith('---'):
                    break
                yaml_content.append(line)
                
            fm = yaml.safe_load(''.join(yaml_content)) or {}
            return int(fm.get('sort_order', 0))
    except Exception:
        return 0

def stream_ordered_data(target_dir):
    metadata = []
    target_dir = os.path.abspath(target_dir)
    
    if not os.path.isdir(target_dir):
        print(f"Error: Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # --- PASS 1: FAST METADATA EXTRACTION ---
    for filename in os.listdir(target_dir):
        filepath = os.path.join(target_dir, filename)
        
        if not os.path.isfile(filepath) or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            sort_order = fast_get_sort_order(filepath)
            
            metadata.append({
                'path': filepath,
                'date': post_date,
                'sort_order': sort_order
            })
        except (ValueError, TypeError):
            continue
            
    # Sort first by date, then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']))
    
    # --- PASS 2: HEAVY LIFTING & STREAMING OUTPUT ---
    for idx, item in enumerate(metadata, start=1):
        filepath = item['path']
        
        # Now we read the full file for the expensive calculations
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tokens = count_tokens(content)
            bytes_count = len(content.encode('utf-8'))
            order = item['sort_order']
            
            # flush=True forces the terminal to render the line immediately
            print(f"{filepath}  # [Idx: {idx} | Order: {order} | Tokens: {tokens:,} | Bytes: {bytes_count:,}]", flush=True)
            
        except Exception as e:
            print(f"# Error processing {filepath}: {e}", file=sys.stderr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="List Jekyll posts sorted by date and YAML sort_order with telemetry.")
    parser.add_argument(
        'directory', 
        nargs='?', 
        default=os.getcwd(), 
        help="Target directory (defaults to current directory)"
    )
    args = parser.parse_args()
    
    stream_ordered_data(args.directory)