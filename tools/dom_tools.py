#!/usr/bin/env python3
"""
DOM Visualization Tools

Provides functions to render DOM structures as ASCII art, either as a
hierarchical tree or as nested boxes. These are exposed as auto-discoverable
tools for AI and CLI usage.
"""

import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.tree import Tree
from rich.box import ROUNDED, DOUBLE, HEAVY, ASCII
import json


# This makes the 'tools' package importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import auto_tool

_TRUNCATION_LENGTH = 60 # Default truncation length for display

# Note: The classes are kept internal to this module, and the async functions
# below are the public-facing tools.

class _DOMHierarchyVisualizer:
    # ... (All the code from the original DOMHierarchyVisualizer class)
    def __init__(self, console_width=180):
        self.console = Console(record=True, width=console_width)
        self.level_colors = ["bright_red", "bright_green", "bright_yellow", "bright_blue", "bright_magenta", "bright_cyan", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

    def get_color_for_level(self, level):
        return self.level_colors[level % len(self.level_colors)]

    def extract_element_info(self, element):
        info = {'tag': element.name, 'id': element.get('id'), 'class': element.get('class'), 'aria_label': element.get('aria-label'), 'data_testid': element.get('data-testid'), 'href': element.get('href'), 'src': element.get('src'), 'text': None}
        if element.string:
            text = element.string.strip()
            if text: info['text'] = text[:_TRUNCATION_LENGTH] + "..." if len(text) > _TRUNCATION_LENGTH else text
        return info

    def format_element_display(self, info, level):
        color = self.get_color_for_level(level)
        display_parts = [f"<{info['tag']}>"]
        if info['id']: display_parts.append(f"id='{info['id']}'")
        if info['class']: display_parts.append(f"class='{' '.join(info['class'])}'")
        if info['data_testid']: display_parts.append(f"data-testid='{info['data_testid']}'")
        if info['aria_label']: display_parts.append(f"aria-label='{info['aria_label']}'")
        if info['href']:
            href = info['href'][:_TRUNCATION_LENGTH] + "..." if len(info['href']) > _TRUNCATION_LENGTH else info['href']
            display_parts.append(f"href='{href}'")
        if info['src']:
            src = info['src'][:_TRUNCATION_LENGTH] + "..." if len(info['src']) > _TRUNCATION_LENGTH else info['src']
            display_parts.append(f"src='{src}'")
        if info['text']: display_parts.append(f'"{info["text"]}"')
        return Text(" ".join(display_parts), style=color)

    def build_tree_structure(self, element, tree_node, level=0, max_depth=50):
        # Recursion fuse, not a token-budget cap: 50 exceeds any sane real-world
        # DOM (~30-40 worst case) but keeps pathological trees from hitting
        # Python's recursion limit. Truncation is recorded, never silent.
        if level > max_depth:
            tree_node.add(Text("... (max depth reached)", style="dim white"))
            return
        info = self.extract_element_info(element)
        display_text = self.format_element_display(info, level)
        current_node = tree_node.add(display_text)
        for child in element.children:
            if hasattr(child, 'name') and child.name:
                self.build_tree_structure(child, current_node, level + 1, max_depth)

    def visualize_dom_content(self, html_content, source_name="DOM"):
        soup = BeautifulSoup(html_content, 'html.parser')
        tree = Tree(Text("🌐 Document Root", style="bold white"), style="dim")
        root_element = soup.find('html') or soup
        if root_element and hasattr(root_element, 'name'):
            self.build_tree_structure(root_element, tree, 0)
        self.console.print(tree)  # Print to the internal recording console for export
        return self.console.export_text()

class _DOMBoxVisualizer:
    # ... (All the code from the original DOMBoxVisualizer class)
    def __init__(self, console_width=180):
        self.console = Console(record=True, width=console_width)
        self.level_colors = ["bright_red", "bright_green", "bright_yellow", "bright_blue", "bright_magenta", "bright_cyan", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        self.box_styles = [DOUBLE, HEAVY, ROUNDED, ASCII]
        self.max_content_width = int(console_width * 0.9)
        self.max_children_to_show = 8

    def get_color_for_level(self, level):
        return self.level_colors[level % len(self.level_colors)]

    def get_box_style_for_level(self, level):
        return self.box_styles[level % len(self.box_styles)]

    def extract_element_info(self, element):
        info = {'tag': element.name, 'id': element.get('id'), 'class': element.get('class'), 'aria_label': element.get('aria-label'), 'data_testid': element.get('data-testid'), 'href': element.get('href'), 'src': element.get('src'), 'text': None}
        if element.string:
            text = element.string.strip()
            if text: info['text'] = text[:_TRUNCATION_LENGTH] + "..." if len(text) > _TRUNCATION_LENGTH else text
        else:
            texts = []
            for child in element.children:
                if isinstance(child, str):
                    child_text = child.strip()
                    if child_text: texts.append(child_text)
                elif hasattr(child, 'string') and child.string:
                    child_text = child.string.strip()
                    if child_text: texts.append(child_text)
            if texts:
                combined_text = ' '.join(texts)
                info['text'] = combined_text[:_TRUNCATION_LENGTH] + "..." if len(combined_text) > _TRUNCATION_LENGTH else combined_text
        return info

    def format_element_title(self, info, level):
        color = self.get_color_for_level(level)
        title_parts = [f"<{info['tag']}>"]
        if info['id']: title_parts.append(f"#{info['id']}")
        if info['data_testid']: title_parts.append(f"[testid={info['data_testid']}]")
        if info['aria_label']:
            # 15-char cap is deliberate (panel titles are narrow); ellipsis only when true
            aria = info['aria_label'][:15] + "..." if len(info['aria_label']) > 15 else info['aria_label']
            title_parts.append(f"[aria={aria}]")
        return Text(" ".join(title_parts), style=f"bold {color}")

    def format_element_content(self, info, children_count, level):
        color = self.get_color_for_level(level)
        content_lines = []
        if info['class']:
            classes = ' '.join(info['class']) if isinstance(info['class'], list) else info['class']
            if len(classes) > _TRUNCATION_LENGTH: classes = classes[:_TRUNCATION_LENGTH] + "..."
            content_lines.append(Text(f"class: {classes}", style=f"dim {color}"))
        if info['href']:
            href = info['href'][:_TRUNCATION_LENGTH] + "..." if len(info['href']) > _TRUNCATION_LENGTH else info['href']
            content_lines.append(Text(f"href: {href}", style=f"dim {color}"))
        if info['src']:
            src = info['src'][:_TRUNCATION_LENGTH] + "..." if len(info['src']) > _TRUNCATION_LENGTH else info['src']
            content_lines.append(Text(f"src: {src}", style=f"dim {color}"))
        if info['text']: content_lines.append(Text(f'"{info["text"]}"', style=f"italic {color}"))
        if children_count > 0:
            child_info = f"[{children_count} child element{'s' if children_count != 1 else ''}]"
            if children_count > self.max_children_to_show: child_info += f" (showing first {self.max_children_to_show})"
            content_lines.append(Text(child_info, style=f"dim {color}"))
        return content_lines

    def build_nested_boxes(self, element, level=0, max_depth=6):
        if level > max_depth: return Text("... (max depth reached)", style="dim white")
        info = self.extract_element_info(element)
        child_elements = [child for child in element.children if hasattr(child, 'name') and child.name]
        children_to_show = child_elements[:self.max_children_to_show]
        title = self.format_element_title(info, level)
        content_lines = self.format_element_content(info, len(child_elements), level)
        if children_to_show and level < max_depth:
            child_boxes = [self.build_nested_boxes(child, level + 1, max_depth) for child in children_to_show if child]
            all_content = content_lines + ([Text("")] if content_lines and child_boxes else [])
            for i, child_box in enumerate(child_boxes):
                all_content.append(child_box)
                if i < len(child_boxes) - 1: all_content.append(Text(""))
        else:
            all_content = content_lines
        if not all_content: all_content = [Text("(empty element)", style="dim")]
        
        from rich.console import Group
        panel_content = Group(*all_content) if len(all_content) > 1 or not isinstance(all_content[0], (Text, Panel)) else all_content[0]

        width_reduction = int(self.max_content_width * 0.08 * level)
        min_width = max(int(self.max_content_width * 0.25), 40)
        calculated_width = max(self.max_content_width - width_reduction, min_width)
        
        return Panel(panel_content, title=title, border_style=self.get_color_for_level(level), box=self.get_box_style_for_level(level), padding=(0, 1), width=calculated_width)

    def visualize_dom_content(self, html_content, source_name="DOM"):
        soup = BeautifulSoup(html_content, 'html.parser')
        root_element = soup.find('html') or soup
        if root_element and hasattr(root_element, 'name'):
            max_depth = 6 if len(soup.find_all()) > 100 else 12
            nested_layout = self.build_nested_boxes(root_element, 0, max_depth)
            self.console.print(nested_layout)  # Print to the internal recording console for export
        return self.console.export_text()


# In tools/dom_tools.py

@auto_tool
async def visualize_dom_hierarchy(params: dict) -> dict:
    """Renders the DOM from a file as a hierarchical tree."""
    file_path = params.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        visualizer = _DOMHierarchyVisualizer()
        output = visualizer.visualize_dom_content(html_content, source_name=file_path)
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}

@auto_tool
async def visualize_dom_boxes(params: dict) -> dict:
    """Renders the DOM from a file as nested boxes."""
    file_path = params.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        visualizer = _DOMBoxVisualizer()
        output = visualizer.visualize_dom_content(html_content, source_name=file_path)
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}


# A11Y NOISE FILTER: InlineTextBox nodes are line-wrap rendering artifacts —
# they duplicate the StaticText directly above them, chopped at whatever
# viewport width the scrape happened to run at. They carry zero structural,
# facet, or selector signal and can account for half the outline's tokens on
# templated pages. Treated as ignored: the node is dropped, children (none
# in practice) are promoted.
_AX_NOISE_ROLES = {"InlineTextBox"}


class _AXTreeSummarizer:
    """Parses a raw accessibility tree JSON into a simplified text outline."""

    def __init__(self):
        self.output_lines = []
        self.node_map = {}

    def _walk_node(self, node_id: str, level: int = 0):
            """Recursively walks the tree, skipping ignored containers but processing their children."""
            node = self.node_map.get(node_id)
            if not node:
                return

            is_ignored = node.get("ignored", False)
            if node.get("role", {}).get("value", "") in _AX_NOISE_ROLES:
                is_ignored = True

            # Only process and print the node if it's NOT ignored.
            if not is_ignored:
                indent = "  " * level
                role = node.get("role", {}).get("value", "unknown")
                name = node.get("name", {}).get("value", "").strip()

                line = f"{indent}[{role}]"

                properties = []
                for prop in node.get("properties", []):
                    if prop.get("name") == "level":
                        properties.append(f"level: {prop['value']['value']}")
                    if prop.get("name") == "url":
                        properties.append(f"url: {prop['value']['value']}")

                if properties:
                    line += f" ({', '.join(properties)})"

                if name:
                    line += f' "{name}"'

                self.output_lines.append(line)

            # ALWAYS recurse, but adjust the indentation level.
            # If the current node was ignored, its children stay at the same level.
            # If it was printed, its children are indented.
            next_level = level if is_ignored else level + 1
            for child_id in node.get("childIds", []):
                self._walk_node(child_id, next_level)


    def summarize_tree(self, ax_tree_data: dict) -> str:
        """
        Processes the full accessibility tree data and returns the summary.
        
        Args:
            ax_tree_data: The loaded JSON data from an accessibility_tree.json file.

        Returns:
            A string containing the formatted, indented semantic outline.
        """
        nodes = ax_tree_data.get("accessibility_tree", [])
        if not nodes:
            return "No accessibility nodes found in the provided file."

        # Create a map for quick node lookup by ID
        self.node_map = {node["nodeId"]: node for node in nodes}
        
        # Find the root node(s) (nodes without a parentId)
        root_ids = [node["nodeId"] for node in nodes if "parentId" not in node]

        if not root_ids:
             # Fallback for trees that might not have a clear root defined
            if nodes: root_ids = [nodes[0]['nodeId']]
            else: return "Could not determine the root of the accessibility tree."

        for root_id in root_ids:
            self._walk_node(root_id)
            
        return "\n".join(self.output_lines)


@auto_tool
async def summarize_accessibility_tree(params: dict) -> dict:
    """Parses a raw accessibility_tree.json file into a simplified text outline."""
    file_path = params.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data.get("success", True): # Check for success flag from scrape
             return {"success": False, "error": f"Accessibility tree file indicates a previous failure: {data.get('error')}"}

        summarizer = _AXTreeSummarizer()
        summary_output = summarizer.summarize_tree(data)
        
        return {"success": True, "output": summary_output}
    except Exception as e:
        return {"success": False, "error": str(e)}
