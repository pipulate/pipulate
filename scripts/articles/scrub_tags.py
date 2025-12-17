import os
import argparse
from pathlib import Path

def scrub_files(directory, dry_run=True):
    target_dir = Path(directory).resolve()
    print(f"--- 🧹 Scrubbing Liquid Tags in: {target_dir} ---")
    if dry_run:
        print("⚠️  DRY RUN MODE: No files will be modified.\n")

    count = 0
    for file_path in target_dir.glob("**/*.md"):
        try:
            original_content = file_path.read_text(encoding="utf-8")
            
            # The removal logic
            new_content = original_content.replace("{% raw %}", "")
            new_content = new_content.replace("{% endraw %}", "")
            
            # Clean up potential double empty lines left behind? 
            # Optional, but keeping it simple is safer for now.
            
            if original_content != new_content:
                print(f"found tags in: {file_path.name}")
                if not dry_run:
                    file_path.write_text(new_content, encoding="utf-8")
                count += 1
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    action = "Would have modified" if dry_run else "Modified"
    print(f"\n✨ {action} {count} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove all {% raw %} tags from markdown files.")
    parser.add_argument("dir", help="Directory to scan (e.g., _posts)")
    parser.add_argument("--do-it", action="store_true", help="Actually perform the changes (disable dry run)")
    args = parser.parse_args()

    scrub_files(args.dir, dry_run=not args.do_it)