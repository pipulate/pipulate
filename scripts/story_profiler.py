#!/usr/bin/env python3
# scripts/story_profiler.py

import os
import re
import subprocess
import tiktoken
from pathlib import Path

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Uses tiktoken to count tokens, falling back to word count approximation."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        return len(text.split())

def find_repo_root(start_path: str) -> str:
    """Find the git repository root from a starting path."""
    path = os.path.abspath(start_path)
    while path != os.path.dirname(path):
        if os.path.isdir(os.path.join(path, '.git')):
            return path
        path = os.path.dirname(path)
    raise FileNotFoundError("Could not find the repository root (.git directory).")

# File extensions we consider "story-worthy" (code, config, docs)
STORY_EXTENSIONS = {
    '.py', '.js', '.css', '.html', '.md', '.markdown', '.txt',
    '.json', '.nix', '.sh', '.ipynb', '.toml', '.in', '.cfg',
    '.svg', '.xsd',
}

def collect_repo_files(repo_root: str) -> set:
    """Use `git ls-files` to get only tracked, non-ignored files.
    Falls back to os.walk if git is unavailable."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            capture_output=True, text=True, cwd=repo_root, check=True
        )
        repo_files = set()
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            ext = os.path.splitext(line)[1].lower()
            if ext in STORY_EXTENSIONS:
                repo_files.add(line)
        return repo_files
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: manual walk (less accurate, doesn't respect .gitignore)
        print("⚠️  `git ls-files` failed. Falling back to directory walk (may include gitignored files).\n")
        return _collect_repo_files_fallback(repo_root)

def _collect_repo_files_fallback(repo_root: str) -> set:
    """Fallback file collector using os.walk. Less accurate than git ls-files."""
    SKIP_DIRS = {
        '.git', '.venv', '.cursor', '.jupyter', '.ipynb_checkpoints',
        '.ssh', '.nix-profile', '.nix-defexpr',
        'node_modules', '__pycache__',
        'browser_cache', 'piper_models',
        'data', 'downloads', 'logs', 'temp',
        'build', 'dist',
        'Client_Work', 'deliverables',
    }
    SKIP_FILES = {
        'favicon.ico', 'LICENSE', 'requirements.txt', 'requirements.in',
        'pyproject.toml', 'release.py',
    }
    repo_files = set()
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, repo_root)
        for filename in filenames:
            if filename in SKIP_FILES:
                continue
            if filename.startswith('.') and filename != '.gitignore':
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in STORY_EXTENSIONS:
                continue
            rel_path = filename if rel_dir == '.' else os.path.join(rel_dir, filename)
            repo_files.add(rel_path)
    return repo_files

def main():
    try:
        repo_root = find_repo_root(os.path.dirname(__file__))
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    foo_file = os.path.join(repo_root, "foo_files.py")

    if not os.path.exists(foo_file):
        print(f"❌ Could not find {foo_file} at {repo_root}")
        return

    with open(foo_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    chapters = {"Root / Uncategorized": []}
    current_chapter = "Root / Uncategorized"
    in_story_section = False
    all_claimed_files = set()

    for line in lines:
        line = line.strip()

        # Start parsing once we hit the string variable assignment
        if "AI_PHOOEY_CHOP =" in line:
            in_story_section = True
            continue

        if not in_story_section:
            continue

        # Stop parsing once we reach the auto-generated Orphanage block to avoid recursion
        if "VIII. THE ORPHANAGE" in line:
            break

        # Detect our Roman numeral structural headers (e.g., "# II. THE CORE MACHINE")
        m_chap = re.match(r'^#\s*([IVX]+\.\s+.*)', line)
        if m_chap:
            current_chapter = m_chap.group(1).strip()
            if current_chapter not in chapters:
                chapters[current_chapter] = []
            continue

        # Clean the line of comment hashes and whitespace
        clean_line = line.lstrip("#").strip()
        
        # Skip empty lines, visual dividers, sub-headers, chisel-strikes, and raw URLs
        if (not clean_line or clean_line.startswith("=") or 
            clean_line.startswith("CHAPTER") or clean_line.startswith("THE 404") or
            clean_line.startswith("!") or clean_line.startswith("http")):
            continue

        # The first word on the remaining lines should be the file path
        file_path = clean_line.split()[0]
        
        # Verify it looks like a file
        ext = os.path.splitext(file_path)[1].lower()
        if ext in STORY_EXTENSIONS or ('/' in file_path and '.' in file_path):
            chapters[current_chapter].append(file_path)
            
            # Path Normalization for the Orphan Delta (The core fix)
            if os.path.isabs(file_path):
                if file_path.startswith(repo_root):
                    rel_path = os.path.relpath(file_path, repo_root)
                    all_claimed_files.add(os.path.normpath(rel_path))
            else:
                all_claimed_files.add(os.path.normpath(file_path))

    # Remove empty chapters before printing
    chapters = {k: v for k, v in chapters.items() if v}

    # ── Chapter Size Report ──────────────────────────────────────────────
    print("# 📊 Pipulate Story Size Profile (Claude/Gemini Optimized)\n")
    print("*Goal: Keep individual chapters under ~350KB for optimal Claude/Gemini ingestion.*\n")

    total_story_tokens = 0
    total_story_bytes = 0

    for chapter, files in chapters.items():
        print(f"### {chapter}")
        chapter_tokens = 0
        chapter_bytes = 0

        print("| File | Tokens | Bytes |")
        print("|---|---|---|")

        for file_path in files:
            full_path = file_path if os.path.isabs(file_path) else os.path.join(repo_root, file_path)

            if not os.path.exists(full_path):
                print(f"| ❌ `{file_path}` | Not Found | Not Found |")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                tokens = count_tokens(content)
                b_size = len(content.encode('utf-8'))

                chapter_tokens += tokens
                chapter_bytes += b_size

                print(f"| `{file_path}` | {tokens:,} | {b_size:,} |")
            except Exception as e:
                print(f"| ❌ `{file_path}` | Error | Error |")

        kb_size = chapter_bytes / 1024
        print(f"| **CHAPTER TOTAL** | **{chapter_tokens:,}** | **{chapter_bytes:,} ({kb_size:.1f} KB)** |\n")

        if kb_size > 400:
            print(f"> ⚠️ **WARNING: DANGER ZONE.** This chapter is {kb_size:.1f} KB. It will likely choke Claude.\n")
        elif kb_size > 300:
            print(f"> 🟡 *Note: Getting heavy. You are at {kb_size:.1f} KB.*\n")
        else:
            print(f"> ✅ *Safe for Claude/Gemini UIs.*\n")

        total_story_tokens += chapter_tokens
        total_story_bytes += chapter_bytes

    print("---")
    print(f"### 📈 Grand Total: {total_story_tokens:,} tokens | {total_story_bytes / 1024 / 1024:.2f} MB")

    # ── The Orphanage (Idempotent Injection) ─────────────────────────────
    repo_files = collect_repo_files(repo_root)
    orphans = sorted(repo_files - all_claimed_files)

    # Read the current foo_files.py
    with open(foo_file, "r", encoding="utf-8") as f:
        foo_content = f.read()

    # Define our idempotent marker
    ORPHAN_MARKER = "# ============================================================================\n# VIII. THE ORPHANAGE (Uncovered Files)\n# ============================================================================"

    # Strip out the old Orphanage (and the closing quotes) if it exists
    marker_index = foo_content.find(ORPHAN_MARKER)
    if marker_index != -1:
        base_content = foo_content[:marker_index].rstrip() + "\n\n"
    else:
        # If it doesn't exist, just slice off the closing quotes to make room
        end_quote_idx = foo_content.rfind('"""')
        base_content = foo_content[:end_quote_idx].rstrip() + "\n\n"

    if not orphans:
        print("\n---")
        print("### 🏠 Orphan Report: All story-worthy files are claimed! No orphans found.")
        # Restore closing quotes cleanly
        with open(foo_file, "w", encoding="utf-8") as f:
            f.write(base_content + '\n"""\n')
        return

    # Build the new Orphanage block
    orphan_lines = [
        ORPHAN_MARKER, 
        "# Files tracked by git but not listed in any chapter above.",
        "# Move these into the active chapters to grant the AI visibility.\n"
    ]
    
    print(f"\n---")
    print(f"### 👻 Writing {len(orphans)} orphans to foo_files.py...")

    for orphan_path in orphans:
        full_path = os.path.join(repo_root, orphan_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            tokens = count_tokens(content)
            b_size = len(content.encode('utf-8'))
            orphan_lines.append(f"# {orphan_path}  # [{tokens:,} tokens | {b_size:,} bytes]")
        except Exception:
            orphan_lines.append(f"# {orphan_path}  # [Error reading file]")

    orphan_block = "\n".join(orphan_lines) + "\n"

    # Reassemble with the closing quotes
    final_content = base_content + orphan_block + '"""\n'

    with open(foo_file, "w", encoding="utf-8") as f:
        f.write(final_content)
        
    print("✨ foo_files.py updated with the latest uncovered files.")

if __name__ == "__main__":
    main()
