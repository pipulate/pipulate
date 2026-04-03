#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CONTEXT_DIR = Path("/home/mike/repos/bookforge/10_context")

def main(target_chapter):
    print(f"🔍 Consolidating data for: {target_chapter}...\n")
    
    consolidated_concepts = set()
    consolidated_sources = set()

    for json_file in CONTEXT_DIR.glob("pass_*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            anchors = data.get("source_anchors", [])
            for anchor in anchors:
                
                # SCENARIO A: The AI followed the schema (Object/Dict)
                if isinstance(anchor, dict):
                    if anchor.get("chapter_id") == target_chapter:
                        # Extract Concepts
                        concepts = anchor.get("concepts", [])
                        if isinstance(concepts, str): concepts = [concepts]
                        elif "concept" in anchor: concepts = [str(anchor["concept"])]
                        
                        # Extract Sources
                        sources = anchor.get("sources", [])
                        if isinstance(sources, str): sources = [sources]
                        elif "source_files" in anchor: sources = anchor.get("source_files", [])
                        
                        consolidated_concepts.update(concepts)
                        consolidated_sources.update(sources)
                
                # SCENARIO B: The AI hallucinated a string list (e.g., pass_007)
                elif isinstance(anchor, str):
                    if anchor.startswith(target_chapter):
                        parts = anchor.split(":", 1)
                        if len(parts) > 1:
                            concept_text = parts[1].strip()
                            consolidated_concepts.add(concept_text)
                            consolidated_sources.add(f"Extracted implicitly from {json_file.name}")

        except json.JSONDecodeError:
            print(f"⚠️  Warning: Could not parse {json_file.name}")
            continue

    print(f"📚 Found {len(consolidated_concepts)} concepts across {len(consolidated_sources)} source files.\n")
    
    print("--- KEY CONCEPTS ---")
    for concept in sorted(consolidated_concepts):
        print(f"• {concept}")
        
    print("\n--- SOURCE FILES ---")
    for source in sorted(consolidated_sources):
        print(f"• {source}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python consolidate_chapter_data.py <chapter_id>")
        print("Example: python consolidate_chapter_data.py ch_06_fasthtml_htmx")
        sys.exit(1)
        
    main(sys.argv[1])
