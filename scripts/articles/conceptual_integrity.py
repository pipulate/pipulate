#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

CONTEXT_DIR = Path("/home/mike/repos/bookforge/10_context")

def main():
    all_concepts = []
    pass_counts = {}

    for json_file in CONTEXT_DIR.glob("pass_*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            pass_id = json_file.stem
            current_pass_concepts = []
            
            for anchor in data.get("source_anchors", []):
                concepts = []
                if isinstance(anchor, dict):
                    concepts = anchor.get("concepts", [])
                    if isinstance(concepts, str): concepts = [concepts]
                    elif "concept" in anchor: concepts = [anchor["concept"]]
                elif isinstance(anchor, str):
                    parts = anchor.split(":", 1)
                    concepts = [parts[1].strip()] if len(parts) > 1 else [anchor]
                
                for c in concepts:
                    norm = str(c).strip().lower()
                    if norm:
                        all_concepts.append(norm)
                        current_pass_concepts.append(norm)
            
            pass_counts[pass_id] = len(set(current_pass_concepts))
                        
        except Exception:
            continue

    total_extractions = len(all_concepts)
    unique_concepts = set(all_concepts)
    unique_count = len(unique_concepts)
    
    ratio = (unique_count / total_extractions * 100) if total_extractions > 0 else 0
    
    print("\n" + "="*60)
    print(" 🧠 CONCEPTUAL INTEGRITY REPORT")
    print("="*60 + "\n")
    print(f" 📊 Metrics:")
    print(f"    Total Extractions:  {total_extractions}")
    print(f"    Unique Concepts:    {unique_count}")
    print(f"    Uniqueness Ratio:   {ratio:.1f}%")
    
    if ratio < 50:
        print("\n ⚠️  WARNING: High redundancy detected. The Genie is repeating itself.")
    else:
        print("\n ✅ SIGNAL STRENGTH: The pipeline is harvesting fresh material.")

    print("\n 🌪️  HEAVY ROTORS (Frequent concepts across passes):")
    counts = Counter(all_concepts)
    for concept, count in counts.most_common(10):
        if count > 2:
            print(f"    [{count}x] {concept}")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
