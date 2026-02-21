#!/usr/bin/env python3
# scripts/story_profiler.py

import os
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

if __name__ == "__main__":
    main()