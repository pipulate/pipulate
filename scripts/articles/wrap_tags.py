import os
import argparse
from pathlib import Path

def wrap_files(directory, dry_run=True):
    target_dir = Path(directory).resolve()
    print(f"--- 🎁 Wrapping Posts in Liquid Raw Tags: {target_dir} ---")
    if dry_run:
        print("⚠️  DRY RUN MODE: No files will be modified.\n")

    count = 0
    for file_path in target_dir.glob("**/*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check for Valid Front Matter
            if not content.startswith("---"):
                print(f"Skipping (no front matter): {file_path.name}")
                continue

            parts = content.split("---", 2)
            
            # parts[0] is empty (before first ---)
            # parts[1] is the YAML content
            # parts[2] is the body
            if len(parts) < 3:
                print(f"Skipping (malformed front matter): {file_path.name}")
                continue

            yaml_block = parts[1]
            body = parts[2]

            # Idempotency Check: Don't wrap if it already looks wrapped
            # We check the trimmed start of the body
            if body.strip().startswith("{% raw %}"):
                # print(f"Skipping (already wrapped): {file_path.name}")
                continue

            # Construct the new content
            # We ensure there is a newline after the YAML block, then the raw tag
            new_body = f"\n\n{{% raw %}}\n{body}\n{{% endraw %}}\n"
            
            # Reassemble
            final_content = f"---{yaml_block}---{new_body}"

            print(f"Wrapping: {file_path.name}")
            if not dry_run:
                file_path.write_text(final_content, encoding="utf-8")
            count += 1

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    action = "Would have modified" if dry_run else "Modified"
    print(f"\n✨ {action} {count} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wrap markdown bodies in {% raw %} tags.")
    parser.add_argument("dir", help="Directory to scan (e.g., _posts)")
    parser.add_argument("--do-it", action="store_true", help="Actually perform the changes (disable dry run)")
    args = parser.parse_args()

    wrap_files(args.dir, dry_run=not args.do_it)