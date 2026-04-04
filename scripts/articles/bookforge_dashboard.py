#!/usr/bin/env python3
import json
from pathlib import Path

# Paths
BOOKFORGE_DIR = Path("/home/mike/repos/bookforge")
OUTLINE_PATH = BOOKFORGE_DIR / "20_outline/outline.json"
LEDGER_PATH = BOOKFORGE_DIR / "00_meta/pass_ledger.jsonl"
CONTEXT_DIR = BOOKFORGE_DIR / "10_context"

def draw_bar(percentage, length=40, fill_char='█', empty_char='░'):
    filled_length = int(length * percentage // 100)
    bar = fill_char * filled_length + empty_char * (length - filled_length)
    return bar

def main():
    print("\n" + "="*60)
    print(" 🏭 THE FOREVER MACHINE : TELEMETRY")
    print("="*60 + "\n")

    # 1. Macro Progress (The Ledger)
    total_passes = 0
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, 'r', encoding='utf-8') as f:
            total_passes = sum(1 for line in f if line.strip())
            
    completed_passes = len(list(CONTEXT_DIR.glob("pass_*.json")))
    
    if total_passes > 0:
        progress_pct = (completed_passes / total_passes) * 100
        print(" 🎯 DISTILLATION PROGRESS")
        print(f"    [{draw_bar(progress_pct)}] {progress_pct:.1f}%")
        print(f"    {completed_passes} of {total_passes} passes completed.\n")

    # 2. Chapter Maturity (The Shards)
    print(" 📖 CHAPTER MATURITY (Concepts Harvested)")
    
    # Load chapter taxonomy
    chapters = {}
    if OUTLINE_PATH.exists():
        with open(OUTLINE_PATH, 'r', encoding='utf-8') as f:
            outline_data = json.load(f)
            for part in outline_data.get("parts", []):
                for ch in part.get("chapters", []):
                    chapters[ch["id"]] = {"title": ch["title"], "concept_count": 0}

    # Harvest counts from shards
    for json_file in CONTEXT_DIR.glob("pass_*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for anchor in data.get("source_anchors", []):
                # Handle both Dict and String schema variations (Anti-Fragile parsing)
                ch_id = None
                concepts_added = 0
                
                if isinstance(anchor, dict):
                    ch_id = anchor.get("chapter_id")
                    concepts = anchor.get("concepts", [])
                    if isinstance(concepts, str): concepts_added = 1
                    else: concepts_added = len(concepts)
                elif isinstance(anchor, str):
                    parts = anchor.split(":", 1)
                    ch_id = parts[0].strip()
                    concepts_added = 1
                
                if ch_id in chapters:
                    chapters[ch_id]["concept_count"] += concepts_added
                    
        except Exception:
            continue # Skip corrupted shards silently in the dashboard

    # Display Chapter Bars
    max_concepts = max((ch["concept_count"] for ch in chapters.values()), default=1)
    max_concepts = max(max_concepts, 1) # Prevent division by zero
    
    for ch_id, ch_data in chapters.items():
        count = ch_data["concept_count"]
        if count > 0:
            rel_pct = (count / max_concepts) * 100
            short_title = (ch_data['title'][:25] + '..') if len(ch_data['title']) > 25 else ch_data['title']
            print(f"    {short_title:<27} | {draw_bar(rel_pct, 20)} {count} ideas")

    print("\n" + "="*60)
    print(" Keep turning the crank. The vats are filling.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
