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

    chapters = {}
    current_chapter = None
    in_story_section = False
    all_claimed_files = set()

    for line in lines:
        line = line.strip()

        if "THE LIVING CODEX" in line:
            in_story_section = True

        if not in_story_section:
            continue

        if line.startswith("# # CHAPTER") or line.startswith("# # PREFACE"):
            current_chapter = line.lstrip("# ").strip()
            chapters[current_chapter] = []

        elif current_chapter and line.startswith("# ") and not line.startswith("# #"):
            file_path = line.lstrip("# ").strip().split()[0]
            if file_path:
                chapters[current_chapter].append(file_path)
                if os.path.isabs(file_path) and file_path.startswith(repo_root):
                    all_claimed_files.add(os.path.relpath(file_path, repo_root))
                elif not os.path.isabs(file_path):
                    all_claimed_files.add(file_path)

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

    # ── Orphan Report ────────────────────────────────────────────────────
    repo_files = collect_repo_files(repo_root)
    orphans = sorted(repo_files - all_claimed_files)

    if not orphans:
        print("\n---")
        print("### 🏠 Orphan Report: All story-worthy files are claimed by a chapter. Nice work.")
        return

    print("\n---")
    print(f"### 👻 Orphan Report: {len(orphans)} tracked files appear in NO chapter\n")
    print("*These files are tracked by git but not referenced by any chapter in `foo_files.py`.")
    print("Decide for each: include in a chapter, or intentionally exclude.*\n")

    print("| File | Tokens | Bytes | Suggested Chapter |")
    print("|---|---|---|---|")

    orphan_total_tokens = 0
    orphan_total_bytes = 0

    for orphan_path in orphans:
        full_path = os.path.join(repo_root, orphan_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            tokens = count_tokens(content)
            b_size = len(content.encode('utf-8'))
            orphan_total_tokens += tokens
            orphan_total_bytes += b_size
        except Exception:
            tokens = 0
            b_size = 0

        # Heuristic suggestions based on path
        if orphan_path.startswith("apps/"):
            suggestion = "Ch 5 (Apps) or Ch 6 (SEO)"
        elif orphan_path.startswith("imports/"):
            suggestion = "Ch 3 (Spells) or Ch 5 (Apps)"
        elif orphan_path.startswith("tools/"):
            suggestion = "Ch 3 (Spells)"
        elif orphan_path.startswith("assets/"):
            suggestion = "Ch 4 (UI) or Ch 1 (Bootstrap)"
        elif orphan_path.startswith("scripts/"):
            suggestion = "Ch 1 (CLI) or Preface"
        elif orphan_path.startswith("pipulate/"):
            suggestion = "Ch 2 (Monolith)"
        elif orphan_path.startswith("Notebooks/") or orphan_path.startswith("assets/nbs/"):
            suggestion = "Ch 8 (Notebooks)"
        elif orphan_path.startswith("remotes/"):
            suggestion = "Maybe Ch 1 (Deploy)"
        else:
            suggestion = "—"

        print(f"| `{orphan_path}` | {tokens:,} | {b_size:,} | {suggestion} |")

    orphan_kb = orphan_total_bytes / 1024
    print(f"| **ORPHAN TOTAL** | **{orphan_total_tokens:,}** | **{orphan_total_bytes:,} ({orphan_kb:.1f} KB)** | |")

if __name__ == "__main__":
    main()