# seo_gadget.py
# Purpose: Extracts SEO data, generates DOM visualizations (hierarchy, boxes),
#          and creates a markdown summary from a rendered HTML file.
#          Go Gadget Go! ⚙️

import argparse
import io
import sys
from pathlib import Path
import json # Added for potential future structured data output

# --- Third-Party Imports ---
from bs4 import BeautifulSoup
from rich.console import Console
from rich.terminal_theme import MONOKAI

# Attempt to import visualization classes
try:
    # Assuming tools package is accessible via sys.path modification below
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
    "hierarchy_txt": "dom_hierarchy.txt",
    "hierarchy_html": "dom_hierarchy.html",
    "boxes_txt": "dom_layout_boxes.txt",
    "boxes_html": "dom_layout_boxes.html",
}
CONSOLE_WIDTH = 180

# --- Path Configuration (Robust sys.path setup) ---
try:
    script_dir = Path(__file__).resolve().parent # Notebooks/imports
    project_root = script_dir.parent.parent # Assumes script is in Notebooks/imports
    tools_dir = project_root / 'tools'

    if not tools_dir.is_dir():
        raise FileNotFoundError(f"'tools' directory not found at expected location: {tools_dir}")

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Re-check import status after path setup
    if not VIZ_CLASSES_LOADED:
        # Try importing again now that path is set
        from tools.dom_tools import _DOMHierarchyVisualizer, _DOMBoxVisualizer
        VIZ_CLASSES_LOADED = True

except (FileNotFoundError, ImportError) as e:
    print(f"Error setting up paths or importing dependencies: {e}", file=sys.stderr)
    # Allow script to continue for basic SEO extraction, but log the issue
    VIZ_CLASSES_LOADED = False
    IMPORT_ERROR_MSG = str(e) # Store specific error

# --- Helper Functions ---
def read_html_file(file_path: Path) -> str | None:
    """Reads HTML content from a file path."""
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: Input HTML file not found: {file_path}", file=sys.stderr)
        return None
    try:
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading HTML file {file_path}: {e}", file=sys.stderr)
        return None

def write_output_file(output_dir: Path, filename_key: str, content: str, results: dict):
    """Writes content to a file in the output directory and updates results."""
    try:
        file_path = output_dir / OUTPUT_FILES[filename_key]
        file_path.write_text(content, encoding='utf-8')
        results[f'{filename_key}_success'] = True
    except Exception as e:
        print(f"Error writing {OUTPUT_FILES[filename_key]} for {output_dir.parent.name}/{output_dir.name}: {e}", file=sys.stderr)
        results[f'{filename_key}_success'] = False

# --- Main Processing Logic ---
def main(html_file_path: str):
    """
    Orchestrates the extraction and generation of all output files.
    """
    input_path = Path(html_file_path).resolve()
    output_dir = input_path.parent
    results = {} # To track success/failure of each part

    # 1. Read Input HTML (Crucial first step)
    html_content = read_html_file(input_path)
    if html_content is None:
        sys.exit(1) # Exit if file reading failed

    # 2. Initialize BeautifulSoup (Foundation for SEO Extraction)
    soup = BeautifulSoup(html_content, 'html.parser')

    # --- 3. Generate SEO.md ---
    print(f"Attempting to write SEO data to: {output_dir / OUTPUT_FILES['seo_md']}", file=sys.stderr)
    try:
        # Extract basic SEO fields
        page_title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_description = meta_desc_tag['content'].strip() if meta_desc_tag and 'content' in meta_desc_tag.attrs else "No Meta Description Found"
        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
        # Canonical URL
        canonical_tag = soup.find('link', rel='canonical')
        canonical_url = canonical_tag['href'].strip() if canonical_tag and 'href' in canonical_tag.attrs else "Not Found"

        # Meta Robots
        meta_robots_tag = soup.find('meta', attrs={'name': 'robots'})
        meta_robots_content = meta_robots_tag['content'].strip() if meta_robots_tag and 'content' in meta_robots_tag.attrs else "Not Specified"
        # Add more extractions here (canonical, etc.) as needed

        # --- Markdown Conversion ---
        markdown_content = "# Markdown Content\n\nSkipped: Markdownify library not installed."
        if MARKDOWNIFY_AVAILABLE:
            try:
                # --- Select main content ---
                # For MVP, let's just use the body tag. Refine selector later if needed.
                body_tag = soup.body
                if body_tag:
                     # Convert selected HTML to Markdown
                     # Add options like strip=['script', 'style'] if needed later
                     markdown_text = markdownify(str(body_tag), heading_style="ATX")
                     markdown_content = f"# Markdown Content\n\n{markdown_text}"
                else:
                     markdown_content = "# Markdown Content\n\nError: Could not find body tag."
            except Exception as md_err:
                 print(f"Error during markdown conversion: {md_err}", file=sys.stderr)
                 markdown_content = f"# Markdown Content\n\nError converting HTML to Markdown: {md_err}"
        # --- End Markdown Conversion ---

        # Prepare content
        seo_md_content = f"""---
title: {json.dumps(page_title)}
meta_description: {json.dumps(meta_description)}
h1_tags: {json.dumps(h1_tags)}
h2_tags: {json.dumps(h2_tags)}
#canonical_tag: {json.dumps(str(canonical_tag))}
canonical_url: {json.dumps(canonical_url)}
#meta_robots_tag: {json.dumps(str(meta_robots_tag))}
#meta_robots_content: {json.dumps(meta_robots_content)}
---

{markdown_content}

"""
        # Write the file directly
        write_output_file(output_dir, "seo_md", seo_md_content, results)
        if results.get("seo_md_success"):
             print(f"Successfully created basic {OUTPUT_FILES['seo_md']} for {input_path}")

    except Exception as e:
        print(f"Error creating {OUTPUT_FILES['seo_md']} for {input_path}: {e}", file=sys.stderr)
        results['seo_md_success'] = False

    # --- 4. Generate Visualizations (If classes loaded) ---
    if VIZ_CLASSES_LOADED:
        # --- Generate Hierarchy ---
        try:
            hierarchy_visualizer = _DOMHierarchyVisualizer(console_width=CONSOLE_WIDTH)
            tree_object = hierarchy_visualizer.visualize_dom_content(html_content, source_name=str(input_path), verbose=False)

            # --- FIX: Create two separate, dedicated consoles ---

            # 1. Console for TEXT export
            record_console_txt_h = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
            record_console_txt_h.print(tree_object)
            results['hierarchy_txt_content'] = record_console_txt_h.export_text() # Use export_text()

            # 2. Console for HTML export
            record_console_html_h = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
            record_console_html_h.print(tree_object)
            results['hierarchy_html_content'] = record_console_html_h.export_html(theme=MONOKAI)

        except Exception as e:
            print(f"Error generating hierarchy visualization for {input_path}: {e}", file=sys.stderr)
            results['hierarchy_txt_content'] = f"Error generating hierarchy: {e}"
            results['hierarchy_html_content'] = f"<h1>Error generating hierarchy</h1><p>{e}</p>"

        # --- Generate Boxes ---
        try:
            box_visualizer = _DOMBoxVisualizer(console_width=CONSOLE_WIDTH)
            box_object = box_visualizer.visualize_dom_content(html_content, source_name=str(input_path), verbose=False)

            if box_object:
                # --- FIX: Create two separate, dedicated consoles ---

                # 1. Console for TEXT export
                record_console_txt_b = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
                record_console_txt_b.print(box_object)
                results['boxes_txt_content'] = record_console_txt_b.export_text() # Use export_text()

                # 2. Console for HTML export
                record_console_html_b = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
                record_console_html_b.print(box_object)
                results['boxes_html_content'] = record_console_html_b.export_html(theme=MONOKAI)
            else:
                results['boxes_txt_content'] = "Error: Could not generate box layout object."
                results['boxes_html_content'] = "<h1>Error: Could not generate box layout object.</h1>"

        except Exception as e:
            print(f"Error generating box visualization for {input_path}: {e}", file=sys.stderr)
            results['boxes_txt_content'] = f"Error generating boxes: {e}"
            results['boxes_html_content'] = f"<h1>Error generating boxes</h1><p>{e}</p>"
    else:
        # Log that visualizations were skipped
        print(f"Skipping DOM visualizations due to import error: {IMPORT_ERROR_MSG}", file=sys.stderr)
        results['hierarchy_txt_content'] = "Skipped: Visualization classes failed to load."
        results['hierarchy_html_content'] = "<h1>Skipped: Visualization classes failed to load.</h1>"
        results['boxes_txt_content'] = "Skipped: Visualization classes failed to load."
        results['boxes_html_content'] = "<h1>Skipped: Visualization classes failed to load.</h1>"


    # --- 5. Save All Generated Files ---
    # Note: seo.md was already written directly in its section
    write_output_file(output_dir, "hierarchy_txt", results.get('hierarchy_txt_content', ''), results)
    write_output_file(output_dir, "hierarchy_html", results.get('hierarchy_html_content', ''), results)
    write_output_file(output_dir, "boxes_txt", results.get('boxes_txt_content', ''), results)
    write_output_file(output_dir, "boxes_html", results.get('boxes_html_content', ''), results)

    # Final success message check
    success_flags = [results.get(f'{key}_success', False) for key in OUTPUT_FILES]
    if all(success_flags):
        print(f"Successfully generated all output files for {input_path}")
    elif any(success_flags):
         print(f"Successfully generated some output files for {input_path} (check errors above)")
    else:
         print(f"Failed to generate any output files for {input_path}")
         sys.exit(1) # Exit with error if nothing worked

# --- Standard Script Execution Guard ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract SEO data and generate DOM visualizations from an HTML file.",
        epilog="Go Gadget Go!"
        )
    parser.add_argument("html_file", help="Path to the input rendered_dom.html file.")
    args = parser.parse_args()
    main(args.html_file)
