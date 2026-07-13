# tools/llm_optics.py
# Purpose: The Semantic SIFT Engine. Translates raw DOM into AI-ready 
#          Markdown, JSON registries, and human-readable ASCII structures.
#          Complete Optics Engaged. 👁️

import argparse
import io
import sys
from pathlib import Path
import json
import difflib
from urllib.parse import urljoin, urlparse

# --- Third-Party Imports ---
from bs4 import BeautifulSoup
from rich.console import Console
from rich.syntax import Syntax
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
    "diff_hierarchy_txt": "diff_hierarchy.txt",
    "diff_hierarchy_html": "diff_hierarchy.html",
    "diff_boxes_txt": "diff_boxes.txt",
    "diff_boxes_html": "diff_boxes.html",
    "diff_simple_txt": "diff_simple_dom.txt",
    "diff_simple_html": "diff_simple_dom.html",
    "links_md": "links.md",
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

def generate_diff(source_text: str, hydrated_text: str, prefix: str, results: dict):
    """Generates a unified diff of the two ASCII representations and bottles it in Rich HTML."""
    if not source_text and not hydrated_text:
        return

    source_lines = source_text.splitlines()
    hydrated_lines = hydrated_text.splitlines()

    diff_iterator = difflib.unified_diff(
        source_lines, hydrated_lines,
        fromfile=f"source_dom_{prefix}.txt",
        tofile=f"hydrated_dom_{prefix}.txt",
        lineterm=''
    )
    diff_text = '\n'.join(diff_iterator)

    if not diff_text.strip():
        diff_text = "No structural differences detected between source and hydrated DOM."

    try:
        # 1. Raw Text Export
        results[f'diff_{prefix}_txt_content'] = diff_text

        # 2. HTML Export via Rich Syntax
        syntax = Syntax(diff_text, "diff", theme="monokai", word_wrap=True)
        record_console = Console(record=True, file=io.StringIO(), width=CONSOLE_WIDTH)
        record_console.print(syntax)
        results[f'diff_{prefix}_html_content'] = record_console.export_html(theme=MONOKAI)
    except Exception as e:
        print(f"Error generating diff for {prefix}: {e}", file=sys.stderr)

def _extract_links(html_content: str, base_url: str) -> list:
    """Extracts every anchor as an objective fact row. No nav-vs-body opinion, just what the page hands out."""
    soup = BeautifulSoup(html_content, 'html.parser')
    base_host = urlparse(base_url).netloc
    rows = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        resolved = urljoin(base_url, href)
        img = a.find('img')
        if img is not None and not a.get_text(strip=True):
            label = f"[image] alt={img.get('alt', '')!r} src={img.get('src', '')!r}"
        else:
            label = a.get_text(strip=True) or "(no text)"
        rel_val = a.get('rel', [])
        rel = " ".join(rel_val) if isinstance(rel_val, list) else str(rel_val)
        rows.append({
            "href_raw": href,
            "href_resolved": resolved,
            "label": label,
            "rel": rel or "—",
            "target": a.get('target', '—'),
            "same_host": (urlparse(resolved).netloc == base_host) if base_host else False,
        })
    return rows


def _format_link_rows(rows: list) -> list:
    """Renders link rows grouped along the one objective axis: same-host vs external."""
    first_party = [r for r in rows if r["same_host"]]
    external = [r for r in rows if not r["same_host"]]

    def render_row(r):
        meta = []
        if r["rel"] != "—":
            meta.append(f"rel={r['rel']}")
        if r["target"] != "—":
            meta.append(f"target={r['target']}")
        meta_str = ("  " + " ".join(meta)) if meta else ""
        return f'    {r["href_resolved"]}    "{r["label"]}"{meta_str}'

    lines = [f"  first-party (same host): {len(first_party)}"]
    lines.extend(render_row(r) for r in first_party)
    lines.append(f"  external: {len(external)}")
    lines.extend(render_row(r) for r in external)
    return lines


def _parameter_census(rows: list) -> list:
    """Tabulates the query-string grammar across anchors: parameter -> arguments.

    On templated pages the query grammar IS the navigation model, so this is
    the facet-space X-ray: every named slot (parameter), how many distinct
    bound values (arguments) it takes, and how often each binding occurs.
    Repeated keys on one URL (multi-select encoding) surface as extra
    bindings. Purely objective — no judgment about which slots deserve
    indexable URLs; that's the human's call downstream.
    """
    from collections import defaultdict
    from urllib.parse import parse_qsl
    census = defaultdict(lambda: defaultdict(int))
    for r in rows:
        query = urlparse(r["href_resolved"]).query
        if not query:
            continue
        for key, value in parse_qsl(query, keep_blank_values=True):
            census[key][value] += 1
    if not census:
        return ["  (no query parameters found)"]
    lines = []
    for key in sorted(census, key=lambda k: -sum(census[k].values())):
        values = census[key]
        total = sum(values.values())
        lines.append(f"  {key}: {len(values)} distinct argument(s) across {total} binding(s)")
        for v, n in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))[:12]:
            shown = v if len(v) <= 60 else v[:57] + "..."
            lines.append(f"    = '{shown}' x{n}")
        if len(values) > 12:
            lines.append(f"    ... {len(values) - 12} more argument(s)")
    return lines


def generate_link_lens(source_html: str, hydrated_html: str, base_url: str, results: dict):
    """Builds the objective Link Lens: source anchors, hydrated anchors, and the hydration diff.

    The diff is the intelligence: anchors that appear only after JavaScript runs reveal a
    client-side-injected link graph without anyone reading a line of script. Grouping is by
    same-host vs external only, because nav-vs-content is an editorial judgment, not an observation.
    """
    source_rows = _extract_links(source_html, base_url)
    hydrated_rows = _extract_links(hydrated_html, base_url)

    source_keys = {r["href_resolved"] for r in source_rows}
    hydrated_keys = {r["href_resolved"] for r in hydrated_rows}
    added = sorted(hydrated_keys - source_keys)
    removed = sorted(source_keys - hydrated_keys)

    md = ["# Link Lens", f"base: {base_url or '(unknown)'}", ""]

    md.append(f"## SOURCE HTML — {len(source_rows)} anchors")
    md.extend(_format_link_rows(source_rows))
    md.append("")

    md.append(f"## HYDRATED DOM — {len(hydrated_rows)} anchors (delta view)")
    hydrated_new = [r for r in hydrated_rows if r["href_resolved"] not in source_keys]
    md.append(f"  shared with source: {len(hydrated_rows) - len(hydrated_new)} anchor(s) — listed once above")
    md.append(f"  present only after hydration: {len(hydrated_new)} anchor(s)")
    md.extend(_format_link_rows(hydrated_new) if hydrated_new else ["  (none)"])
    md.append("")

    md.append("## PARAMETER CENSUS — source anchors")
    md.extend(_parameter_census(source_rows))
    md.append("")

    md.append("## PARAMETER CENSUS — hydrated anchors")
    md.extend(_parameter_census(hydrated_rows))
    md.append("")

    md.append("## ADDED BY HYDRATION")
    md.extend(added if added else ["  (none)"])
    md.append("")

    md.append("## REMOVED BY HYDRATION")
    md.extend(removed if removed else ["  (none)"])

    results['links_md_content'] = "\n".join(md)

# --- Main Processing Logic ---
def main(target_dir_path: str):
    """
    Orchestrates extraction for both raw source and hydrated DOM, and diffs them.
    """
    output_dir = Path(target_dir_path).resolve()
    results = {} 

    source_path = output_dir / "source.html"
    hydrated_dom_path = output_dir / "hydrated_dom.html"
    simple_source_path = output_dir / "simple_source_html.html"
    simple_hydrated_path = output_dir / "simple_hydrated_dom.html"

    hydrated_dom_content = read_html_file(hydrated_dom_path)

    simple_source_content = read_html_file(simple_source_path)
    simple_hydrated_content = read_html_file(simple_hydrated_path)

    if not simple_source_content or not simple_hydrated_content:
        print("Error: Both simple_source_html.html and simple_hydrated_dom.html must exist in the target directory.", file=sys.stderr)
        sys.exit(1)

    # --- 1. Generate SEO.md (Using Rendered DOM for accuracy) ---
    soup = BeautifulSoup(hydrated_dom_content, 'html.parser')
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
    print(f"Generating visualizations for simple_source.html...", file=sys.stderr)
    generate_visualizations(simple_source_content, "source", output_dir, results)

    print(f"Generating visualizations for simple_hydrated.html...", file=sys.stderr)
    generate_visualizations(simple_hydrated_content, "hydrated", output_dir, results)

    # --- 3. Generate Diffs ---
    print(f"Generating structural diffs...", file=sys.stderr)
    source_hier = results.get('source_hierarchy_txt_content', '')
    hydrated_hier = results.get('hydrated_hierarchy_txt_content', '')
    generate_diff(source_hier, hydrated_hier, 'hierarchy', results)

    source_boxes = results.get('source_boxes_txt_content', '')
    hydrated_boxes = results.get('hydrated_boxes_txt_content', '')
    generate_diff(source_boxes, hydrated_boxes, 'boxes', results)

    # --- 3.5 Generate Simple HTML Diff ---
    print(f"Generating simple HTML diff...", file=sys.stderr)
    generate_diff(simple_source_content, simple_hydrated_content, 'simple', results)

    # --- 3.6 Generate Link Lens (Objective anchor accounting) ---
    print(f"Generating link lens...", file=sys.stderr)
    base_url = ""
    headers_path = output_dir / "headers.json"
    if headers_path.exists():
        try:
            base_url = json.loads(headers_path.read_text(encoding='utf-8')).get("url", "")
        except Exception as e:
            print(f"Error reading headers.json for base URL: {e}", file=sys.stderr)
    raw_source_content = read_html_file(source_path) or ""
    generate_link_lens(raw_source_content, hydrated_dom_content or "", base_url, results)

    # --- 4. Save Visualization Files ---
    # We need to handle the new 'simple' v_type specifically for the 'diff' prefix
    # Save source and hydrated visualizations
    for prefix in ["source", "hydrated"]:
        for v_type in ["hierarchy_txt", "hierarchy_html", "boxes_txt", "boxes_html"]:
            file_key = f"{prefix}_{v_type}"
            content = results.get(f"{file_key}_content", "")
            if content:
                write_output_file(output_dir, file_key, content, results)
                
    # Save diffs (now including 'simple_txt' and 'simple_html')
    for v_type in ["hierarchy_txt", "hierarchy_html", "boxes_txt", "boxes_html", "simple_txt", "simple_html"]:
        file_key = f"diff_{v_type}"
        content = results.get(f"{file_key}_content", "")
        if content:
            write_output_file(output_dir, file_key, content, results)

    # Save the Link Lens
    links_content = results.get("links_md_content", "")
    if links_content:
        write_output_file(output_dir, "links_md", links_content, results)

    print(f"Successfully generated optical artifacts for {output_dir.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="The LLM Optics Engine: Generates semantic and visual representations for both raw and hydrated DOMs.",
        epilog="Complete Optics Engaged."
        )
    parser.add_argument("target_dir", help="Path to the directory containing source.html and hydrated_dom.html")
    args = parser.parse_args()
    main(args.target_dir)
