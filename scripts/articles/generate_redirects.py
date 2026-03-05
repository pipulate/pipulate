import csv
import urllib.parse
import os

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
            
            if not old_url.startswith('/'): old_url = '/' + old_url
            if not new_url.startswith('/'): new_url = '/' + new_url
            
            # The final, mathematically perfect Nginx syntax
            outfile.write(f"    {old_url} {new_url};\n")

    print(f"✅ Nginx map forged successfully at {map_output_path}")

if __name__ == "__main__":
    # Point this at your raw CSV and output to your Jekyll root
    build_nginx_map('raw_map.csv', '_redirects.map')