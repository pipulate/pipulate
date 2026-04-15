# llm_optics.py
# Purpose: The Semantic SIFT Engine. Translates raw DOM into AI-ready 
#          Markdown, JSON registries, and human-readable ASCII structures.
#          Complete Optics Engaged. 👁️

import argparse
import io
import sys
from pathlib import Path
import json

# --- Third-Party Imports ---
from bs4 import BeautifulSoup
from rich.console import Console
from rich.terminal_theme import MONOKAI

# Attempt to import visualization classes
try:
    from tools.dom_tools import _DOMHierarchyVisualizer, _DOMBoxVisualizer
    VIZ_CLASSES_LOADED = True
except ImportError as e:
    VIZ_CLASSES_LOADED = False
    IMPORT_ERROR_MSG = f"Error: Could not import visualization classes from tools.dom_tools. {e}"

try:
    from markdownify import markdownify
    MARKDOWNIFY_AVAILABLE = True
except ImportError:
    MARKDOWNIFY_AVAILABLE = False
    MARKDOWNIFY_ERROR_MSG = "Markdownify library not found. Skipping markdown conversion."
    print(MARKDOWNIFY_ERROR_MSG, file=sys.stderr)

# --- Constants ---
OUTPUT_FILES = {
    "seo_md": "seo.md",
    "source_hierarchy_txt": "source_dom_hierarchy.txt",
    "source_hierarchy_html": "source_dom_hierarchy.html",
    "source_boxes_txt": "source_dom_layout_boxes.txt",
    "source_boxes_html": "source_dom_layout_boxes.html",
    "hydrated_hierarchy_txt": "hydrated_dom_hierarchy.txt",
    "hydrated_hierarchy_html": "hydrated_dom_hierarchy.html",
    "hydrated_boxes_txt": "hydrated_dom_layout_boxes.txt",
    "hydrated_boxes_html": "hydrated_dom_layout_boxes.html",
}
CONSOLE_WIDTH = 180

# --- Path Configuration (Robust sys.path setup) ---
try:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    tools_dir = script_dir

    if not tools_dir.is_dir():
        raise FileNotFoundError(f"'tools' directory not found at expected location: {tools_dir}")

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    if not VIZ_CLASSES_LOADED:
        from tools.dom_tools import _DOMHierarchyVisualizer, _DOMBoxVisualizer
        VIZ_CLASSES_LOADED = True

except (FileNotFoundError, ImportError) as e:
    print(f"Error setting up paths or importing dependencies: {e}", file=sys.stderr)
    VIZ_CLASSES_LOADED = False
    IMPORT_ERROR_MSG = str(e)

# --- Helper Functions ---
def read_html_file(file_path: Path) -> str | None:
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: Input HTML file not found: {file_path}", file=sys.stderr)
        return None
    try:
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading HTML file {file_path}: {e}", file=sys.stderr)
        return None

def write_output_file(output_dir: Path, filename_key: str, content: str, results: dict):
    try:
        file_path = output_dir / OUTPUT_FILES[filename_key]
        file_path.write_text(content, encoding='utf-8')
        results[f'{filename_key}_success'] = True
    except Exception as e:
        print(f"Error writing {OUTPUT_FILES[filename_key]} for {output_dir.parent.name}/{output_dir.name}: {e}", file=sys.stderr)
        results[f'{filename_key}_success'] = False

def generate_visualizations(html_content: str, prefix: str, output_dir: Path, results: dict):
    """Generates the 4 visual artifacts (txt/html for hierarchy/boxes) for a given HTML state."""
    if not VIZ_CLASSES_LOADED:
        print(f"Skipping {prefix} DOM visualizations due to import error: {IMPORT_ERROR_MSG}", file=sys.stderr)
        for key in [f"{prefix}_hierarchy_txt", f"{prefix}_hierarchy_html", f"{prefix}_boxes_txt", f"{prefix}_boxes_html"]:
            results[f'{key}_content'] = "Skipped: Visualization classes failed to load."
        return

    # --- Hierarchy ---
    try:
        hierarchy_visualizer = _DOMHierarchyVisualizer(console_width=CONSOLE_WIDTH)
        tree_object = hierarchy_visualizer.visualize_dom_content(html_content, source_name=prefix, verbose=False)

        record_console_txt_h = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
        record_console_txt_h.print(tree_object)
        results[f'{prefix}_hierarchy_txt_content'] = record_console_txt_h.export_text()

        record_console_html_h = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
        record_console_html_h.print(tree_object)
        results[f'{prefix}_hierarchy_html_content'] = record_console_html_h.export_html(theme=MONOKAI)
    except Exception as e:
        print(f"Error generating {prefix} hierarchy: {e}", file=sys.stderr)

    # --- Boxes ---
    try:
        box_visualizer = _DOMBoxVisualizer(console_width=CONSOLE_WIDTH)
        box_object = box_visualizer.visualize_dom_content(html_content, source_name=prefix, verbose=False)

        if box_object:
            record_console_txt_b = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
            record_console_txt_b.print(box_object)
            results[f'{prefix}_boxes_txt_content'] = record_console_txt_b.export_text()

            record_console_html_b = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
            record_console_html_b.print(box_object)
            results[f'{prefix}_boxes_html_content'] = record_console_html_b.export_html(theme=MONOKAI)
    except Exception as e:
        print(f"Error generating {prefix} boxes: {e}", file=sys.stderr)

# --- Main Processing Logic ---
def main(target_dir_path: str):
    """
    Orchestrates extraction for both raw source and hydrated DOM.
    """
    output_dir = Path(target_dir_path).resolve()
    results = {} 

    source_path = output_dir / "source.html"
    rendered_path = output_dir / "rendered_dom.html"

    source_content = read_html_file(source_path)
    rendered_content = read_html_file(rendered_path)

    if not source_content or not rendered_content:
        print("Error: Both source.html and rendered_dom.html must exist in the target directory.", file=sys.stderr)
        sys.exit(1)

    # --- 1. Generate SEO.md (Using Rendered DOM for accuracy) ---
    soup = BeautifulSoup(rendered_content, 'html.parser')
    try:
        page_title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_description = meta_desc_tag['content'].strip() if meta_desc_tag and 'content' in meta_desc_tag.attrs else "No Meta Description Found"
        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
        
        canonical_tag = soup.find('link', rel='canonical')
        canonical_url = canonical_tag['href'].strip() if canonical_tag and 'href' in canonical_tag.attrs else "Not Found"

        meta_robots_tag = soup.find('meta', attrs={'name': 'robots'})
        meta_robots_content = meta_robots_tag['content'].strip() if meta_robots_tag and 'content' in meta_robots_tag.attrs else "Not Specified"

        markdown_content = "# Markdown Content\n\nSkipped: Markdownify library not installed."
        if MARKDOWNIFY_AVAILABLE:
            try:
                body_tag = soup.body
                if body_tag:
                     markdown_text = markdownify(str(body_tag), heading_style="ATX")
                     markdown_content = f"# Markdown Content\n\n{markdown_text}"
                else:
                     markdown_content = "# Markdown Content\n\nError: Could not find body tag."
            except Exception as md_err:
                 markdown_content = f"# Markdown Content\n\nError converting HTML to Markdown: {md_err}"

        seo_md_content = f"""---
title: {json.dumps(page_title)}
meta_description: {json.dumps(meta_description)}
h1_tags: {json.dumps(h1_tags)}
h2_tags: {json.dumps(h2_tags)}
canonical_url: {json.dumps(canonical_url)}
---

{markdown_content}
"""
        write_output_file(output_dir, "seo_md", seo_md_content, results)
    except Exception as e:
        print(f"Error creating seo.md: {e}", file=sys.stderr)

    # --- 2. Generate Visualizations for Both States ---
    print(f"Generating visualizations for source.html...", file=sys.stderr)
    generate_visualizations(source_content, "source", output_dir, results)
    
    print(f"Generating visualizations for rendered_dom.html...", file=sys.stderr)
    generate_visualizations(rendered_content, "hydrated", output_dir, results)

    # --- 3. Save Visualization Files ---
    for prefix in ["source", "hydrated"]:
        for v_type in ["hierarchy_txt", "hierarchy_html", "boxes_txt", "boxes_html"]:
            file_key = f"{prefix}_{v_type}"
            content = results.get(f"{file_key}_content", "")
            if content:
                write_output_file(output_dir, file_key, content, results)

    print(f"Successfully generated optical artifacts for {output_dir.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="The LLM Optics Engine: Generates semantic and visual representations for both raw and hydrated DOMs.",
        epilog="Complete Optics Engaged."
        )
    parser.add_argument("target_dir", help="Path to the directory containing source.html and rendered_dom.html")
    args = parser.parse_args()
    main(args.target_dir)