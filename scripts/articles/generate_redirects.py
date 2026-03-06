#!/usr/bin/env python3
import csv
import urllib.parse
import os
import sys
from pathlib import Path

def build_nginx_map(csv_input_path, map_output_path):
    print(f"🛠️ Forging Nginx map from {csv_input_path}...")
    
    if not os.path.exists(csv_input_path):
        print(f"❌ Error: {csv_input_path} not found.")
        return

    with open(csv_input_path, 'r') as infile, open(map_output_path, 'w') as outfile:
        reader = csv.reader(infile)
        outfile.write("# AI-Generated Semantic Redirects\n")

        for row in reader:
            if len(row) != 2:
                continue # Skip hallucinated or malformed rows
                
            old_url = row[0].strip()
            new_url = row[1].strip()
            
            # Deterministic sanitization
            old_url = urllib.parse.quote(old_url, safe='/%')
            
            # THE BOUNCER: Preserve Nginx default map_hash_bucket_size
            if len(old_url) > 60:
                print(f"⚠️ Dropping oversized URL (>{len(old_url)} chars): {old_url[:30]}...")
                continue
            
            if not old_url.startswith('/'): old_url = '/' + old_url
            if not new_url.startswith('/'): new_url = '/' + new_url
            
            # THE REGEX FORGER: Add ~^ and /? to handle trailing slash variations
            outfile.write(f"    ~^{old_url}/?$ {new_url};\n")

    print(f"✅ Nginx map forged successfully at {map_output_path}")

if __name__ == "__main__":
    # Fallback to defaults if no arguments provided
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/home/mike/repos/trimnoir/_raw_map.csv'
    output_file = sys.argv[2] if len(sys.argv) > 2 else '/home/mike/repos/trimnoir/_redirects.map'
    
    build_nginx_map(input_file, output_file)
