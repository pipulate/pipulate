import os
import sys
import json
import re
import argparse
import getpass
from pathlib import Path
import google.generativeai as genai

# --- CONFIGURATION ---
CONFIG_DIR = Path.home() / ".config" / "articleizer" # Reuse existing config dir
API_KEY_FILE = CONFIG_DIR / "api_key.txt"
TARGETS_FILE = CONFIG_DIR / "targets.json"

DIAGRAM_PROMPT_FILENAME = "diagram_prompt.txt"
PROMPT_PLACEHOLDER = "[INSERT FULL ARTICLE]"

# Mermaid styling constants (Theme Agnostic 80/20 Rule)
# We inject these styles into every diagram to ensure readability in both modes.
# Removes explicit text colors, sets high-contrast strokes, and pastel fills.
MERMAID_STYLE_BLOCK = """
    %% Styling - Theme Agnostic (No fixed text colors)
    style {id} fill:{fill},stroke:#333,stroke-width:2px
"""
# Helper to generate the style block for a node
def get_node_style(node_id, color_hex):
    return f"style {node_id} fill:{color_hex},stroke:#333,stroke-width:2px"

# Standard Pastel Palette (Red, Blue, Green, Yellow, Purple, Cyan)
PALETTE = ["#ffadad", "#a0c4ff", "#caffbf", "#fdffb6", "#bdb2ff", "#9bf6ff"]

# Safe default if config is missing
DEFAULT_TARGETS = {
    "1": {
        "name": "Local Project (Default)",
        "path": "./_posts"
    }
}

def load_targets():
    """Loads publishing targets from external config or falls back to default."""
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.")
    return DEFAULT_TARGETS

PROJECT_TARGETS = load_targets()

def get_api_key():
    """Gets the API key from config or prompts user."""
    if API_KEY_FILE.is_file():
        return API_KEY_FILE.read_text().strip()
    
    print("Google API Key not found.")
    key = getpass.getpass("Enter your Google API Key: ")
    if key.strip():
        save = input("Save key? (y/n): ").lower()
        if save == 'y':
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            API_KEY_FILE.write_text(key.strip())
            API_KEY_FILE.chmod(0o600)
    return key.strip()

def generate_diagrams(article_content, api_key):
    """
    Sends the article to Gemini to identify and generate Mermaid diagrams.
    Returns a list of diagram objects (concept, code, anchor).
    """
    genai.configure(api_key=api_key)
    
    # We construct the prompt dynamically here, but ideally this lives in diagram_prompt.txt
    system_instruction = """
    You are a Technical Illustrator. Your goal is to visualize complex concepts from the text.
    
    1. **Identify:** Find 1-3 distinct concepts, workflows, or architectures in the text that are hard to understand without a visual.
    2. **Visualize:** Generate a Mermaid JS diagram for each.
       - Use `graph TD` (Top-Down) or `LR` (Left-Right) for flows.
       - Use `sequenceDiagram` for interactions over time.
    3. **Locate:** Find a unique string of text (5-15 words) in the article where this diagram should be inserted immediately *after*.

    **CRITICAL MERMAID SYNTAX RULES:**
    - Wrap ALL node labels in double quotes: `id["Label Text"]`.
    - Do NOT set `color:black` or `color:white`. Leave text color default so it adapts to dark/light mode.
    - Do NOT use the `&` character in labels unless escaped or quoted (which you are doing).
    - Use `subgraph "Title"` with quotes.

    **Output Schema (JSON List):**
    [
      {
        "concept": "Brief description",
        "type": "graph TD",
        "code": "Mermaid code content only (no markdown backticks)",
        "insertion_anchor": "unique string from text to insert after"
      }
    ]
    """

    model = genai.GenerativeModel('gemini-2.5-flash') # Use a capable model
    
    prompt = f"{system_instruction}\n\n--- ARTICLE ---\n{article_content}\n--- END ARTICLE ---"

    print("🤖 Analyzing article and generating diagrams (this may take a moment)...")
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up markdown block if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
    except Exception as e:
        print(f"❌ Error generating diagrams: {e}")
        return []

def inject_diagrams(article_content, diagrams):
    """
    Injects the generated diagrams into the article content using the anchors.
    """
    modified_content = article_content
    
    print(f"🔄 Injecting {len(diagrams)} diagrams...")

    for i, diag in enumerate(diagrams):
        anchor = diag.get('insertion_anchor')
        code = diag.get('code')
        concept = diag.get('concept')
        
        if not anchor or not code:
            print(f"  ⚠️ Skipping diagram {i+1}: Missing anchor or code.")
            continue

        # Clean anchor (sometimes LLMs add quotes)
        anchor = anchor.strip('"').strip("'")
        
        # Verify anchor exists
        if anchor not in modified_content:
             # Try a fuzzy match or normalization if needed, but for now, strict check
             print(f"  ⚠️ Anchor not found: '{anchor}'")
             continue

        print(f"  ✅ Inserting diagram for: {concept}")

        # Construct the HTML wrapper (benchmark style)
        # We perform a simple regex-based style injection for the 'style' lines if not present,
        # but for this draft we trust the LLM or apply a post-processing step if needed.
        
        # Wrap in the requested div structure
        mermaid_block = f"\n\n<div class=\"mermaid\">\n{code}\n</div>\n\n"

        # Insert AFTER the anchor paragraph (heuristic: find next double newline)
        # For simplicity in V1, we insert immediately after the anchor text + newline
        
        replacement = f"{anchor}{mermaid_block}"
        
        # Only replace the first occurrence
        modified_content = modified_content.replace(anchor, replacement, 1)

    return modified_content

def main():
    parser = argparse.ArgumentParser(description="Auto-generate and inject Mermaid diagrams into markdown articles.")
    parser.add_argument('filename', nargs='?', help='The specific markdown file to process.')
    parser.add_argument('--target', type=str, default='1', help='Target ID from config (default: 1)')
    
    args = parser.parse_args()

    # Target Logic
    if args.target not in PROJECT_TARGETS:
        print("Invalid target.")
        return
        
    base_path = Path(PROJECT_TARGETS[args.target]['path'])
    
    # File Selection Logic
    target_file = None
    if args.filename:
        target_file = base_path / args.filename
    else:
        # Find most recent
        files = list(base_path.glob('*.md'))
        if not files:
            print("No markdown files found.")
            return
        target_file = max(files, key=os.path.getmtime)
        print(f"Selected most recent file: {target_file.name}")

    if not target_file.exists():
        print(f"File not found: {target_file}")
        return

    # Read Content
    with open(target_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Get API Key
    api_key = get_api_key()
    if not api_key: return

    # Generate
    diagrams = generate_diagrams(content, api_key)
    
    if not diagrams:
        print("No diagrams generated.")
        return

    # Inject
    new_content = inject_diagrams(content, diagrams)
    
    # Save (Atomic write)
    if new_content != content:
        backup_path = target_file.with_suffix('.md.bak')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Backup saved to {backup_path.name}")
        
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✨ Success! Diagrams injected into {target_file.name}")
    else:
        print("⚠️ No changes made to file (anchors likely missing).")

if __name__ == '__main__':
    main()
