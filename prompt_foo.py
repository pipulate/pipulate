#!/usr/bin/env python3
# prompt_foo.py

# > We've got content, it's groovy context
# > Our concatenation just won't stop
# > Making stories art for a super-smart
# > AI-Phooey chop (Hi-Ya!)

import os
import re
import sys
import pydot
import yaml
import argparse
import tiktoken
import subprocess
import tempfile
import shutil
import json
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

try:
    import jupytext
    JUPYTEXT_AVAILABLE = True
except ImportError:
    JUPYTEXT_AVAILABLE = False


CONFIG_DIR = Path.home() / ".config" / "articleizer"
TARGETS_FILE = CONFIG_DIR / "targets.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Local Project (Default)",
        "path": "/home/mike/repos/trimnoir/_posts" # Updated default fallback
    }
}

# ============================================================================
# --- Logging & Capture ---
# ============================================================================
class Logger:
    """Captures stdout for inclusion in the generated prompt."""
    def __init__(self):
        self.logs = []

    def print(self, *args, **kwargs):
        # Construct the string exactly as print would
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        text = sep.join(map(str, args)) + end
        
        # Capture it
        self.logs.append(text)
        
        # Actually print it to stdout
        print(*args, **kwargs)

    def get_captured_text(self):
        return "".join(self.logs)

# Global logger instance
logger = Logger()

def load_url_map():
    """Loads the URL mapping configuration from .config/url_map.json"""
    config_path = os.path.expanduser("~/.config/articleizer/url_map.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.print(f"Warning: Could not decode JSON from {config_path}")
    return {}

def load_targets():
    """Loads publishing targets from external config."""
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.print(f"Warning: {TARGETS_FILE} is corrupt. Using defaults.")
    return DEFAULT_TARGETS

# Initialize with defaults, but allow override
CONFIG = {
    "PROJECT_NAME": "pipulate",
    "POSTS_DIRECTORY": DEFAULT_TARGETS["1"]["path"] 
}

URL_MAP = load_url_map()

# ============================================================================
# --- Configuration ---
# ============================================================================
def find_repo_root(start_path: str) -> str:
    """Find the git repository root from a starting path."""
    path = os.path.abspath(start_path)
    while path != os.path.dirname(path):
        if os.path.isdir(os.path.join(path, '.git')):
            return path
        path = os.path.dirname(path)
    raise FileNotFoundError("Could not find the repository root (.git directory).")

REPO_ROOT = find_repo_root(os.path.dirname(__file__))

CONFIG = {
    "PROJECT_NAME": "pipulate",
    "POSTS_DIRECTORY": "/home/mike/repos/MikeLev.in/_posts"
}

# ============================================================================
# --- Literary Size Scale & Token/Word Counting ---
# ============================================================================
LITERARY_SIZE_SCALE = [
    (3000, "Short Essay"), (7500, "Short Story"), (20000, "Novelette"),
    (50000, "Novella or a Master's Dissertation"),
    (80000, "Average Paperback Novel or a Ph.D. Dissertation"),
    (120000, "Long Novel"), (200000, "Epic Fantasy Novel"),
    (500000, "Seriously Long Epic (like 'Infinite Jest')"),
]

def get_literary_perspective(word_count: int, token_word_ratio: float) -> str:
    description = f"Longer than {LITERARY_SIZE_SCALE[-1][1]}"
    for words, desc in LITERARY_SIZE_SCALE:
        if word_count <= words:
            description = desc
            break
    density_warning = ""
    if token_word_ratio > 1.8:
        density_warning = (
            f" (Note: With a token/word ratio of {token_word_ratio:.2f}, "
            f"this content is far denser and more complex than typical prose of this length)."
        )
    return f"📚 Equivalent in length to a **{description}**{density_warning}"

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        return len(text.split())

def count_words(text: str) -> int:
    return len(text.split())

# ============================================================================
# --- Auto-Context Generation (UML, Tree, Narrative) ---
# ============================================================================
def add_holographic_shards(builder, articles: List[Dict]):
    """Finds and injects JSON context shards for a specific list of articles."""
    shards = {}
    found_count = 0
    
    for article in articles:
        # Resolve path: _posts/filename.md -> _posts/_context/filename.json
        article_path = article['path']
        parent_dir = os.path.dirname(article_path)
        stem = os.path.splitext(os.path.basename(article_path))[0]
        json_path = os.path.join(parent_dir, "_context", f"{stem}.json")
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    # Load as object to consolidate
                    shard_data = json.load(f)
                    shards[stem] = shard_data
                    found_count += 1
            except Exception as e:
                logger.print(f"Warning: Could not read context shard {json_path}: {e}")

    if shards:
        title = "Holographic Context Shards"
        # Dense serialization to save tokens
        consolidated_json = json.dumps(shards, separators=(',', ':'))
        content = f"--- START: Holographic Context Shards (Consolidated) ---\n{consolidated_json}\n--- END: Holographic Context Shards ---"
        
        builder.add_auto_context(title, content)
        cdata = builder.auto_context.get(title, {})
        logger.print(f"Matched context shards: ({found_count} files | {cdata.get('tokens',0):,} tokens)")


def generate_uml_and_dot(target_file: str, project_name: str) -> Dict:
    pyreverse_exec = shutil.which("pyreverse")
    plantuml_exec = shutil.which("plantuml")
    if not pyreverse_exec or not plantuml_exec:
        msg = []
        if not pyreverse_exec: msg.append("`pyreverse` (from pylint)")
        if not plantuml_exec: msg.append("`plantuml`")
        return {"ascii_uml": f"Skipping: Required command(s) not found: {', '.join(msg)}."}

    target_path = target_file if os.path.isabs(target_file) else os.path.join(REPO_ROOT, target_file)
    if not os.path.exists(target_path):
        return {"ascii_uml": f"Skipping: Target file for UML generation not found: {target_path}"}

    with tempfile.TemporaryDirectory() as temp_dir:
        dot_file_path = os.path.join(temp_dir, "classes.dot")
        puml_file_path = os.path.join(temp_dir, "diagram.puml")
        try:
            pyreverse_cmd = [pyreverse_exec, "-f", "dot", "-o", "dot", "-p", project_name, target_path]
            subprocess.run(pyreverse_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
            generated_dot_name = f"classes_{project_name}.dot"
            os.rename(os.path.join(temp_dir, generated_dot_name), dot_file_path)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
            return {"ascii_uml": f"Error: pyreverse failed. {error_msg}", "dot_graph": None}

        try:
            graphs = pydot.graph_from_dot_file(dot_file_path)
            if not graphs:
                return {"ascii_uml": f"Note: No classes found in {target_file} to generate a diagram.", "dot_graph": None}
            graph = graphs[0]
            dot_content = graph.to_string()
            puml_lines = ["@startuml", "skinparam linetype ortho", ""]
            def sanitize_line(line):
                clean = re.sub(r'<br[^>]*>', '', line)
                clean = re.sub(r'<[^>]+>', '', clean)
                return clean.strip()
            for node in graph.get_nodes():
                label = node.get_label()
                if not label: continue
                parts = label.strip('<>{} ').split('|')
                class_name = sanitize_line(parts[0])
                puml_lines.append(f"class {class_name} {{")
                if len(parts) > 1:
                    for attr in re.split(r'<br[^>]*>', parts[1]):
                        clean_attr = sanitize_line(attr).split(':')[0].strip()
                        if clean_attr: puml_lines.append(f"  - {clean_attr}")
                if len(parts) > 2:
                    method_block = parts[2].strip()
                    for method_line in re.split(r'<br[^>]*>', method_block):
                        clean_method = sanitize_line(method_line)
                        if clean_method: puml_lines.append(f"  + {clean_method}")
                puml_lines.append("}\n")
            for edge in graph.get_edges():
                source_name = edge.get_source().strip('"').split('.')[-1]
                dest_name = edge.get_destination().strip('"').split('.')[-1]
                puml_lines.append(f"{source_name} ..> {dest_name}")
            puml_lines.append("@enduml")
            with open(puml_file_path, 'w') as f: f.write('\n'.join(puml_lines))
        except Exception as e:
            with open(dot_file_path, 'r') as f: dot_content_on_error = f.read()
            return {"ascii_uml": f"Error: DOT to PUML conversion failed. {str(e)}", "dot_graph": dot_content_on_error}

        try:
            plantuml_cmd = ["plantuml", "-tutxt", puml_file_path]
            subprocess.run(plantuml_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
            utxt_file_path = puml_file_path.replace(".puml", ".utxt")
            with open(utxt_file_path, 'r') as f: ascii_uml = f.read()
            lines = ascii_uml.splitlines()
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip(' ')) for line in non_empty_lines)
                dedented_lines = [line[min_indent:] for line in lines]
                stripped_lines = [line.rstrip() for line in dedented_lines]
                ascii_uml = '\n'.join(stripped_lines)
                if ascii_uml: ascii_uml = '\n' + ascii_uml
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
            return {"ascii_uml": f"Error: plantuml failed. {error_msg}", "dot_graph": dot_content}

    return {"ascii_uml": ascii_uml, "dot_graph": dot_content}

def _get_article_list_data(posts_dir: str = CONFIG["POSTS_DIRECTORY"]) -> List[Dict]:
    posts_data = []
    if not os.path.isdir(posts_dir):
        logger.print(f"Warning: Article directory not found at {posts_dir}", file=sys.stderr)
        return []

    url_config = URL_MAP.get(posts_dir)

    for filename in os.listdir(posts_dir):
        if not filename.endswith((".md", ".markdown")): continue
        filepath = os.path.join(posts_dir, filename)
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            if content.startswith('---'):
                parts = content.split('---', 2)
                front_matter = yaml.safe_load(parts[1]) or {}

                full_url = ""
                if url_config:
                    slug = front_matter.get('permalink', '').strip('/')
                    if not slug:
                        raw_slug = os.path.splitext(filename)[0]
                        if re.match(r'\d{4}-\d{2}-\d{2}-', raw_slug):
                             raw_slug = raw_slug[11:]
                        style = url_config.get('permalink_style', '/:slug/')
                        slug_path = style.replace(':slug', raw_slug)
                    else:
                          slug_path = "/" + slug.lstrip('/')

                    full_url = f"{url_config['base_url']}{slug_path}"

                article_tokens = count_tokens(content)
                article_bytes = len(content.encode('utf-8'))
                posts_data.append({
                    'path': filepath,
                    'date': post_date,
                    'sort_order': int(front_matter.get('sort_order', 0)),
                    'title': front_matter.get('title', 'Untitled'),
                    'summary': front_matter.get('meta_description', ''),
                    'url': full_url,
                    'tokens': article_tokens,
                    'bytes': article_bytes
                })
        except (ValueError, yaml.YAMLError, IndexError): continue
    return sorted(posts_data, key=lambda p: (p['date'], p['sort_order']))

def parse_slice_arg(arg_str: str):
    if not arg_str or not arg_str.startswith('[') or not arg_str.endswith(']'): return None
    content = arg_str[1:-1].strip()
    if ':' in content:
        parts = content.split(':', 1)
        start = int(parts[0].strip()) if parts[0].strip() else None
        end = int(parts[1].strip()) if parts[1].strip() else None
        return slice(start, end)
    elif content: return int(content)
    return slice(None, None)

def run_tree_command() -> str:
    eza_exec = shutil.which("eza")
    if not eza_exec: return "Skipping: `eza` command not found."
    try:
        # Added --level 3 to keep the tree from exploding if the repo grows deeper
        result = subprocess.run(
            [eza_exec, '--tree', '--level', '3', '--git-ignore', '--color=never'],
            capture_output=True, text=True, cwd=REPO_ROOT, check=True
        )
        return result.stdout
    except Exception as e: return f"Error running eza command: {e}"

# ============================================================================
# --- Helper Functions (File Parsing, Clipboard) ---
# ============================================================================
def parse_file_list_from_config() -> List[Tuple[str, str]]:
    try:
        import foo_files
        files_raw = foo_files.AI_PHOOEY_CHOP
    except (ImportError, AttributeError):
        logger.print("ERROR: foo_files.py not found or doesn't contain AI_PHOOEY_CHOP.")
        sys.exit(1)
    lines = files_raw.strip().splitlines()
    seen_files, parsed_files = set(), []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'): continue
        parts = re.split(r'\s*<--\s*|\s*#\s*', line, 1)
        file_path = parts[0].strip()
        comment = parts[1].strip() if len(parts) > 1 else ""
        if file_path and file_path not in seen_files:
            seen_files.add(file_path)
            parsed_files.append((file_path, comment))
    return parsed_files

def copy_to_clipboard(text: str):
    if not shutil.which('xclip'):
        logger.print("\nWarning: 'xclip' not found. Cannot copy to clipboard.")
        return
    try:
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
        logger.print("Markdown output copied to clipboard")
    except Exception as e:
        logger.print(f"\nWarning: Could not copy to clipboard: {e}")

def check_dependencies():
    logger.print("Checking for required external dependencies...")
    dependencies = {
        "pyreverse": "Provided by `pylint`. Install with: pip install pylint",
        "plantuml": "A Java-based tool. See https://plantuml.com/starting",
        "eza": "A modern replacement for `ls`. See https://eza.rocks/install",
        "xclip": "Clipboard utility for Linux. Install with your package manager (e.g., sudo apt-get install xclip)",
    }
    missing = []
    for tool, instructions in dependencies.items():
        if not shutil.which(tool):
            missing.append((tool, instructions))
    
    if not missing:
        logger.print("✅ All dependencies found.")
    else:
        logger.print("\n❌ Missing dependencies detected:")
        for tool, instructions in missing:
            logger.print(f"  - Command not found: `{tool}`")
            logger.print(f"    ↳ {instructions}")
        logger.print("\nPlease install the missing tools and ensure they are in your system's PATH.")
        sys.exit(1)

# ============================================================================
# --- Refined PromptBuilder Class ---
# ============================================================================
class PromptBuilder:
    """
    Builds a complete, structured Markdown prompt with consistent START/END markers.
    Includes a convergence loop to ensure the Summary section reflects the final token count.
    """
    def __init__(self, processed_files: List[Dict], prompt_text: str, context_only: bool = False, list_arg: Optional[str] = None):
        self.processed_files = processed_files
        self.prompt_text = prompt_text
        self.context_only = context_only
        self.list_arg = list_arg
        self.auto_context = {}
        self.all_sections = {}
        self.command_line = " ".join(sys.argv)
        self.manifest_key = "Manifest (Table of Contents)"

    def add_auto_context(self, title: str, content: str):
        is_narrative = (title == "Recent Narrative Context")
        is_article = (title == "Full Article Content")
        is_shard = (title == "Holographic Context Shards")
        content_is_valid = bool(content)
        filter_passed = "error" not in content.lower() and "skipping" not in content.lower()

        if content_is_valid and (is_narrative or is_article or is_shard or filter_passed):
            self.auto_context[title] = {
                'content': content, 'tokens': count_tokens(content), 'words': count_words(content)
            }

    def _build_manifest_content(self) -> str:
        lines = []
        # Added Summary to section order
        section_order = ["Story", "File Tree", "UML Diagrams", "Articles", "Codebase", "Summary", "Context Recapture", "Prompt"]
        for section_name in section_order:
            if section_name in self.all_sections:
                data = self.all_sections[section_name]
                token_str = f"({data['tokens']:,} tokens)" if data['tokens'] > 0 else ""
                lines.append(f"- {section_name} {token_str}")
                
                # Detailed list for Codebase for searching (absolute paths)
                if section_name == "Codebase" and not self.context_only and self.processed_files:
                     for f in self.processed_files:
                         byte_len = len(f['content'].encode('utf-8'))
                         lines.append(f"  - {f['path']} ({f['tokens']:,} tokens | {byte_len:,} bytes)")
                         
        return "\n".join(lines)

    def _build_story_content(self) -> str:
        title = "Recent Narrative Context"
        return self.auto_context.get(title, {}).get('content', '').strip()

    def _build_tree_content(self) -> str:
        title = "Codebase Structure (eza --tree)"
        if title in self.auto_context:
            content = self.auto_context[title]['content'].strip()
            return f"```text\n{content}\n```"
        return ""

    def _build_uml_content(self) -> str:
        uml_parts = []
        for title, data in self.auto_context.items():
            if "UML Class Diagram" in title:
                uml_parts.append(f"## {title}\n```text\n{data['content']}\n```")
        return "\n\n".join(uml_parts)

    def _build_articles_content(self) -> str:
        parts = []

        # 1. Grab Full Article Content if it exists
        if "Full Article Content" in self.auto_context:
            parts.append(self.auto_context["Full Article Content"]['content'].strip())
            
        # 2. Grab Holographic Shards if they exist
        if "Holographic Context Shards" in self.auto_context:
            parts.append(self.auto_context["Holographic Context Shards"]['content'].strip())
            
        return "\n\n".join(parts).strip()


    def _build_codebase_content(self) -> str:
        if self.context_only: return ""
        if not self.processed_files: return ""
        
        lines = []
        for f in self.processed_files:
            # Using Absolute Paths in markers
            lines.append(f"--- START: {f['path']} ({f['tokens']:,} tokens) ---")
            lines.append(f"```{f['lang']}:{f['path']}")
            lines.append(f['content'])
            lines.append("```")
            lines.append(f"--- END: {f['path']} ---\n")
        return "\n".join(lines).strip()

    def _build_recapture_content(self) -> str:
        """Generates the commented-out variable block for reconstructing this context."""
        lines = ["```python", "# # PURPOSE OF CONTEXT: ", '# AI_PHOOEY_CHOP = """\\']
        for f in self.processed_files:
            path_str = f['path']
            # Keep relative if inside repo, absolute if outside
            if path_str.startswith(REPO_ROOT):
                path_str = os.path.relpath(path_str, REPO_ROOT)
            lines.append(f"# {path_str}")
        lines.append('# """')
        lines.append("```")
        return "\n".join(lines)

    def _build_prompt_content(self) -> str:
        checklist = self._generate_ai_checklist()
        return f"{checklist}\n\n{self.prompt_text}"

    def _generate_ai_checklist(self) -> str:
        return '''# AI Self-Correction Checklist

Before addressing the user's prompt, perform the following verification steps:

1.  **Review the Manifest vs. Codebase Structure:** Compare the file list in the manifest against the `eza --tree` output. Are there any obviously related, critical files missing from the manifest that would be necessary to understand the user's request? (e.g., if `core.py` is present, is `__init__.py` also present?).
2.  **Analyze Import Statements:** Briefly scan the `import` statements in the provided Python files. Do they suggest dependencies on local files that were *not* included in the manifest?
3.  **Check for Incompleteness:** If you determine that critical files are missing, do not proceed. Instead, your **primary task** is to inform me of the missing files and recommend adding them to `foo_files.py` to create a more complete context.
4.  **Confirm Understanding:** If the context appears complete, state "Context verified." and then proceed with the user's request.
5.  **Descriptions:** When describing the passion represented here, you may refer to it as a blueprint, treatise, soliloquy, methodology, philosophy or way. NEVER refer to it as a manifesto which has a negative connotation.
'''

    def _generate_summary_content(self, verified_token_count: int) -> str:
        """Generates the content for the Summary section."""
        lines = []
        
        # Command Line
        lines.append(f"**Command:** `{self.command_line}`\n")

        # Execution Log (Captured from Logger)
        logs = logger.get_captured_text().strip()
        if logs:
            lines.append("--- Processing Log ---")
            lines.append(f"```\n{logs}\n```\n")

        # Files Included
        lines.append("--- Files Included ---")
        for f in self.processed_files:
            if self.context_only:
                lines.append(f"• {f['path']} (content omitted)")
            else:
                byte_len = len(f['content'].encode('utf-8'))
                lines.append(f"• {f['path']} ({f['tokens']:,} tokens | {byte_len:,} bytes)")
        
        if self.auto_context:
            lines.append("\n--- Auto-Context Included ---")
            for title, data in self.auto_context.items():
                byte_len = len(data['content'].encode('utf-8'))
                lines.append(f"• {title} ({data['tokens']:,} tokens | {byte_len:,} bytes)")

        # Metrics
        total_tokens = sum(v.get('tokens', 0) for k, v in self.all_sections.items() if k != self.manifest_key)
        
        total_words = 0
        final_content_for_metrics = ""
        for section, data in self.all_sections.items():
            content_part = data.get('content', '')
            final_content_for_metrics += content_part
            if section != "Prompt":
                total_words += count_words(content_part)

        char_count = len(final_content_for_metrics)
        byte_count = len(final_content_for_metrics.encode('utf-8'))

        lines.append("\n--- Prompt Summary ---")
        if self.context_only:
            lines.append("NOTE: Running in --context-only mode. File contents are excluded.")
        
        lines.append(f"Summed Tokens:    {total_tokens:,} (from section parts)")
        lines.append(f"Verified Tokens: {verified_token_count:,} (from final output)")
        
        if total_tokens != verified_token_count:
            diff = verified_token_count - total_tokens
            lines.append(f"  (Difference: {diff:+,})")
            
        lines.append(f"Total Words:      {total_words:,} (content only)")
        lines.append(f"Total Chars:      {char_count:,}")
        lines.append(f"Total Bytes:      {byte_count:,} (UTF-8)")

        # Literary Perspective
        ratio = verified_token_count / total_words if total_words > 0 else 0
        perspective = get_literary_perspective(total_words, ratio)
        lines.append("\n--- Size Perspective ---")
        lines.append(perspective)

        return "\n".join(lines)

    def build_final_prompt(self) -> str:
        """Assembles all parts into the final Markdown string with convergence loop for accuracy."""
        
        # 1. Build static sections
        story_content = self._build_story_content()
        tree_content = self._build_tree_content()
        uml_content = self._build_uml_content()
        articles_content = self._build_articles_content()
        codebase_content = self._build_codebase_content()
        recapture_content = self._build_recapture_content()
        prompt_content = self._build_prompt_content()

        # Placeholders
        placeholders = {
            "Story": f"# Narrative context not requested. Use the -l or --list flag to include recent articles.",
            "File Tree": "# File tree generation failed or was skipped.",
            "UML Diagrams": "# No Python files with classes were included, or UML generation failed.",
            "Articles": "# No full articles requested. Use the -a or --article flag to include full article content.",
            "Codebase": ("# No files were specified for inclusion in the codebase." if not self.processed_files 
                         else "# Running in --context-only mode. File contents are omitted."),
        }

        # Store basic sections
        self.all_sections["Story"] = {'content': story_content, 'tokens': count_tokens(story_content)}
        self.all_sections["File Tree"] = {'content': tree_content, 'tokens': count_tokens(tree_content)}
        self.all_sections["UML Diagrams"] = {'content': uml_content, 'tokens': count_tokens(uml_content)}
        self.all_sections["Articles"] = {'content': articles_content, 'tokens': count_tokens(articles_content)}
        self.all_sections["Codebase"] = {'content': codebase_content, 'tokens': sum(f['tokens'] for f in self.processed_files) if not self.context_only else 0}
        self.all_sections["Context Recapture"] = {'content': recapture_content, 'tokens': count_tokens(recapture_content)}
        self.all_sections["Prompt"] = {'content': prompt_content, 'tokens': count_tokens(prompt_content)}

        # Helper to assemble text
        def assemble_text(manifest_txt, summary_txt):
            parts = [f"# KUNG FU PROMPT CONTEXT\n\nWhat you will find below is:\n\n- {self.manifest_key}\n- Story\n- File Tree\n- UML Diagrams\n- Articles\n- Codebase\n- Summary\n- Context Recapture\n- Prompt"]
            
            def add(name, content, placeholder):
                final = content.strip() if content and content.strip() else placeholder
                parts.append(f"--- START: {name} ---\n{final}\n--- END: {name} ---")

            add(self.manifest_key, manifest_txt, "# Manifest generation failed.")
            add("Story", story_content, placeholders["Story"] if self.list_arg is None else "# No articles found for the specified slice.")
            add("File Tree", tree_content, placeholders["File Tree"])
            add("UML Diagrams", uml_content, placeholders["UML Diagrams"])
            add("Articles", articles_content, placeholders["Articles"])
            add("Codebase", codebase_content, placeholders["Codebase"])
            add("Summary", summary_txt, "# Summary generation failed.")
            add("Context Recapture", recapture_content, "# Context Recapture failed.")
            add("Prompt", prompt_content, "# No prompt was provided.")
            
            return "\n\n".join(parts)

        # 2. Convergence Loop
        # We need the Summary to contain the final token count, but the Summary is part of the text.
        # We iterate to allow the numbers to stabilize.
        
        current_token_count = 0
        final_output_text = ""
        
        # Initial estimate (sum of static parts)
        current_token_count = sum(v['tokens'] for v in self.all_sections.values())
        
        for _ in range(3): # Max 3 iterations, usually converges in 2
            # Generate Summary with current count
            summary_content = self._generate_summary_content(current_token_count)
            self.all_sections["Summary"] = {'content': summary_content, 'tokens': count_tokens(summary_content)}
            
            # Generate Manifest (might change if Summary token count changes length like 999->1000)
            manifest_content = self._build_manifest_content()
            self.all_sections[self.manifest_key] = {'content': manifest_content, 'tokens': count_tokens(manifest_content)}
            
            # Assemble full text
            final_output_text = assemble_text(manifest_content, summary_content)
            
            # Verify count
            new_token_count = count_tokens(final_output_text)
            
            if new_token_count == current_token_count:
                break # Converged
            
            current_token_count = new_token_count

        return final_output_text

# ============================================================================
# --- Main Execution Logic ---
# ============================================================================
def main():
    """Main function to parse args, process files, and generate output."""
    parser = argparse.ArgumentParser(description='Generate a Markdown context file for AI code assistance.')
    parser.add_argument('prompt', nargs='?', default=None, help='A prompt string or path to a prompt file (e.g., prompt.md).')
    parser.add_argument('-o', '--output', type=str, help='Optional: Output filename.')
    parser.add_argument('--no-clipboard', action='store_true', help='Disable copying output to clipboard.')
    parser.add_argument('--check-dependencies', action='store_true', help='Verify that all required external tools are installed.')
    parser.add_argument('--context-only', action='store_true', help='Generate a context-only prompt without file contents.')
    parser.add_argument('-n', '--no-tree', action='store_true', help='Suppress file tree and UML generation.')
    parser.add_argument(
        '-l', '--list',
        nargs='?', const='[-5:]', default=None,
        help='Include a list of recent articles. Optionally provide a slice, e.g., "[:]". Defaults to "[-5:]".'
    )
    parser.add_argument(
        '-a', '--article',
        nargs='?', const='[-1:]', default=None,
        help='Include FULL CONTENT of recent articles. Provide a slice, e.g., "[-5:]". Defaults to "[-1:]".'
    )
    parser.add_argument(
        '-c', '--context',
        action='store_true',
        help='Include matching Holographic Context JSONs for any articles listed/included.'
    )
    parser.add_argument(
        '-t', '--target', 
        type=str, 
        help='Specify a target ID from targets.json to set the article source.'
    )
    args = parser.parse_args()

    # Handle Target Selection
    targets = load_targets()
    if args.target:
        if args.target in targets:
            selected = targets[args.target]
            CONFIG["POSTS_DIRECTORY"] = selected["path"]
            logger.print(f"🎯 Target set to: {selected['name']} ({selected['path']})")
        else:
            logger.print(f"❌ Invalid target key: {args.target}. Using default.")

    if args.check_dependencies:
        check_dependencies()
        sys.exit(0)

    targets = load_targets()
    if args.target is not None:
        target_id_str = str(args.target)
        if targets and target_id_str in targets:
            selected_target = targets[target_id_str]
            CONFIG["POSTS_DIRECTORY"] = selected_target["path"]
            logger.print(f"🎯 Target set to: {selected_target['name']}")
        else:
            logger.print(f"Error: Target ID '{args.target}' not found in configuration.", file=sys.stderr)
            sys.exit(1)

    # 1. Handle user prompt
    prompt_content = "Please review the provided context and assist with the codebase."
    if args.prompt:
        if os.path.exists(args.prompt):
            with open(args.prompt, 'r', encoding='utf-8') as f: prompt_content = f.read()
        else:
            prompt_content = args.prompt
    elif os.path.exists("prompt.md"):
        with open("prompt.md", 'r', encoding='utf-8') as f: prompt_content = f.read()

    # 2. Process all specified files
    files_to_process = parse_file_list_from_config()
    processed_files_data = []

    logger.print("--- Processing Files ---")
    for path, comment in files_to_process:
        # HANDLE REMOTE URLS
        if path.startswith(('http://', 'https://')):
            try:
                logger.print(f"   -> Fetching URL: {path}")
                with urllib.request.urlopen(path) as response:
                    content = response.read().decode('utf-8')
                ext = os.path.splitext(path.split('?')[0])[1].lower()
                lang_map = {'.py': 'python', '.js': 'javascript', '.html': 'html', '.css': 'css', '.md': 'markdown', '.json': 'json', '.nix': 'nix', '.sh': 'bash'}
                lang = lang_map.get(ext, 'text')
                processed_files_data.append({
                    "path": path, "comment": comment, "content": content,
                    "tokens": count_tokens(content), "words": count_words(content), "lang": lang
                })
            except Exception as e:
                logger.print(f"Error fetching URL {path}: {e}")
            continue

        # ABSOLUTE PATH CERTAINTY: Resolve to absolute path immediately
        full_path = os.path.join(REPO_ROOT, path) if not os.path.isabs(path) else path
        
        if not os.path.exists(full_path):
            logger.print(f"Warning: File not found and will be skipped: {full_path}")
            continue
        content, lang = "", "text"
        ext = os.path.splitext(full_path)[1].lower()
        if ext == '.ipynb':
            if JUPYTEXT_AVAILABLE:
                logger.print(f"   -> Converting notebook: {full_path}")
                try:
                    notebook = jupytext.read(full_path)
                    content = jupytext.writes(notebook, fmt='py:percent')
                    lang = 'python'
                except Exception as e:
                    content = f"# FAILED TO CONVERT NOTEBOOK: {full_path}\n# ERROR: {e}"
                    logger.print(f"Warning: Failed to convert {full_path}: {e}")
            else:
                content = f"# SKIPPING NOTEBOOK CONVERSION: jupytext not installed for {full_path}"
                logger.print(f"Warning: `jupytext` library not found. Skipping conversion for {full_path}.")
        else:
            try:
                with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
                lang_map = {'.py': 'python', '.js': 'javascript', '.html': 'html', '.css': 'css', '.md': 'markdown', '.json': 'json', '.nix': 'nix', '.sh': 'bash'}
                lang = lang_map.get(ext, 'text')
            except Exception as e:
                logger.print(f"ERROR: Could not read or process {full_path}: {e}")
                sys.exit(1)
        
        # Store using full_path for the key to ensure uniqueness and absolute reference
        processed_files_data.append({
            "path": full_path, "comment": comment, "content": content,
            "tokens": count_tokens(content), "words": count_words(content), "lang": lang
        })

    # 3. Build the prompt and add auto-generated context
    builder = PromptBuilder(processed_files_data, prompt_content, context_only=args.context_only, list_arg=args.list)

    # Only generate the codebase tree if .py files are explicitly included AND --no-tree is not set.
    # This avoids clutter when only .md, .nix, or .ipynb files are present, or when explicitly disabled.
    include_tree = any(f['path'].endswith('.py') for f in processed_files_data) and not args.no_tree
    
    if include_tree:
        logger.print("Python file(s) detected. Generating codebase tree diagram...", end='', flush=True)
        tree_output = run_tree_command()
        title = "Codebase Structure (eza --tree)"
        builder.add_auto_context(title, tree_output)
        
        # Calculate sizes for live display
        tree_data = builder.auto_context.get(title, {})
        t_count = tree_data.get('tokens', 0)
        b_count = len(tree_data.get('content', '').encode('utf-8'))
        logger.print(f" ({t_count:,} tokens | {b_count:,} bytes)")
    elif args.no_tree:
        logger.print("Skipping codebase tree (--no-tree flag detected).")
    else:
        logger.print("Skipping codebase tree (no .py files included).")

    if args.list is not None:
        logger.print("Adding narrative context from articles...", end='', flush=True)
        all_articles = _get_article_list_data(CONFIG["POSTS_DIRECTORY"])
        sliced_articles = []
        try:
            slice_or_index = parse_slice_arg(args.list)
            if isinstance(slice_or_index, int): sliced_articles = [all_articles[slice_or_index]]
            elif isinstance(slice_or_index, slice): sliced_articles = all_articles[slice_or_index]
        except (ValueError, IndexError):
            logger.print(f" (invalid slice '{args.list}')")
            sliced_articles = []

        if sliced_articles:
            # COMPRESSED FORMAT: Base Path Header + Filenames Only
            narrative_content = f"**Base Path:** {CONFIG['POSTS_DIRECTORY']}\n\n"
            for article in sliced_articles:
                # We normalize to filename because the base path is declared above
                filename = os.path.basename(article['path'])
                narrative_content += f"### {article['title']} ({article['date']} | {article['tokens']:,} tok)\n"
                if article.get('url'):
                    narrative_content += f"URL: {article['url']}\n"
                narrative_content += f"File: {filename}\n"
                narrative_content += f"Sum: {article['summary']}\n\n"
            
            title = "Recent Narrative Context"
            builder.add_auto_context(title, narrative_content.strip())
            
            # Calculate sizes for live display
            narrative_data = builder.auto_context.get(title, {})
            t_count = narrative_data.get('tokens', 0)
            b_count = len(narrative_data.get('content', '').encode('utf-8'))
            logger.print(f" ({len(sliced_articles)} articles | {t_count:,} tokens | {b_count:,} bytes)")
        else:
            logger.print(" (no articles found or invalid slice)")
    
    if args.article is not None:
        logger.print("Adding full article content...", end='', flush=True)
        all_articles = _get_article_list_data(CONFIG["POSTS_DIRECTORY"])
        sliced_articles = []
        try:
            slice_or_index = parse_slice_arg(args.article)
            if isinstance(slice_or_index, int):
                sliced_articles = [all_articles[slice_or_index]]
            elif isinstance(slice_or_index, slice):
                sliced_articles = all_articles[slice_or_index]
        except (ValueError, IndexError):
            logger.print(f" (invalid slice '{args.article}')")

        if sliced_articles:
            full_content_parts = []
            for article in sliced_articles:
                try:
                    with open(article['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                    full_content_parts.append(f"--- START: Article: {os.path.basename(article['path'])} ---\n{content.strip()}\n--- END: Article ---\n")
                except Exception as e:
                    logger.print(f"\nWarning: Could not read article {article['path']}: {e}")
            
            if full_content_parts:
                full_article_content = "\n".join(full_content_parts)
                title = "Full Article Content"
                builder.add_auto_context(title, full_article_content)
                
                # Calculate sizes for live display
                article_data = builder.auto_context.get(title, {})
                t_count = article_data.get('tokens', 0)
                b_count = len(article_data.get('content', '').encode('utf-8'))
                logger.print(f" ({len(sliced_articles)} full articles | {t_count:,} tokens | {b_count:,} bytes)")
        else:
            logger.print(" (no articles found or invalid slice)")

    # After slicing articles for -l or -a...
    if args.context and sliced_articles:
        logger.print("Pairing holographic context shards...", end='', flush=True)
        add_holographic_shards(builder, sliced_articles)

    python_files_to_diagram = [f['path'] for f in processed_files_data if f['path'].endswith('.py')]
    if python_files_to_diagram and not args.no_tree:
        logger.print("Python file(s) detected. Generating UML diagrams...")
        for py_file_path in python_files_to_diagram:
            logger.print(f"   -> Generating for {py_file_path}...", end='', flush=True)
            uml_context = generate_uml_and_dot(py_file_path, CONFIG["PROJECT_NAME"])
            uml_content = uml_context.get("ascii_uml")
            title = f"UML Class Diagram (ASCII for {py_file_path})"
            builder.add_auto_context(title, uml_content)
            
            if title in builder.auto_context:
                uml_data = builder.auto_context[title]
                b_count = len(uml_data['content'].encode('utf-8'))
                logger.print(f" ({uml_data['tokens']:,} tokens | {b_count:,} bytes)")
            elif uml_content and "note: no classes" in uml_content.lower():
                logger.print(" (skipped, no classes)")
            else:
                logger.print(" (skipped)")
        logger.print("...UML generation complete.\n")
    
    # 4. Generate final output with convergence loop
    final_output = builder.build_final_prompt()
    
    # 5. Print the Summary section to console for immediate feedback
    if "Summary" in builder.all_sections:
        print(builder.all_sections["Summary"]["content"])
    
    # 6. Handle output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f: f.write(final_output)
        print(f"\nOutput written to '{args.output}'")
    if not args.no_clipboard:
        copy_to_clipboard(final_output)

if __name__ == "__main__":
    main()
