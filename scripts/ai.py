#!/usr/bin/env python3
"""
AI Operations & Commit Generator for Pipulate

Consolidated tool for:
1. Generic LLM text processing via stdin (used by Neovim/init.lua)
2. Automated git commit generation with analysis (used by release.py)
"""
import sys
import re
import json
import requests
import argparse
import subprocess
import os
from pathlib import Path

# Wire into the central config
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
import config as CFG

try:
    from imports.append_only_conversation import AppendOnlyConversationSystem
    CONVERSATION_SYSTEM_AVAILABLE = True
except ImportError:
    CONVERSATION_SYSTEM_AVAILABLE = False

DEFAULT_MODEL = CFG.DEFAULT_PROMPT_MODEL
OLLAMA_API_URL = "http://localhost:11434/api"

COMMIT_PROMPT_TEMPLATE = """
You are an expert programmer and git contributor for the "Pipulate" project, a local-first AI SEO tool.
Your task is to write a concise, informative, and conventional commit message.

Analyze the following git diff and generate a commit message in the format:
<type>(<scope>): <subject>

<body>

CRITICAL INSTRUCTIONS:
- BE VERY CAREFUL to distinguish between ADDITIONS (+) and DELETIONS (-) in the diff
- DO NOT credit deletions or removed files as "added" features
- For deletions/cleanups, use terms like "remove", "delete", "clean up", "drop"
- For additions, use terms like "add", "implement", "introduce", "create"
- For housekeeping operations, use "chore:" prefix and focus on cleanup nature

CHANGE ANALYSIS:
{change_analysis}

Git diff context:
- Primary action: {primary_action}
- Is housekeeping/cleanup: {is_housekeeping}
- Change summary: {change_summary}

Based on this analysis, choose the appropriate commit type.

The commit message should:
- Use a valid conventional commit type based on the ACTUAL nature of changes
- Have a brief, imperative subject line (max 50 chars)
- Accurately reflect whether content was ADDED, REMOVED, or MODIFIED
- Provide a more detailed body explaining the "what" and "why" of the changes, if necessary
- The entire response should be ONLY the commit message, with no extra text or explanations

Here is the git diff of staged changes:
--- GIT DIFF START ---
{input_text}
--- GIT DIFF END ---
"""

conversation_history = []

def get_best_llama_model(models):
    llama_models = [model for model in models if model.lower().startswith('llama')]
    return max(llama_models, key=lambda x: x.split(':')[0], default=models[0]) if llama_models else models[0]

def get_staged_diff():
    """Gets the diff of currently staged or unstaged files."""
    try:
        result = subprocess.run(['git', 'diff', '--staged'], capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            result = subprocess.run(['git', 'diff'], capture_output=True, text=True, check=True)
            if not result.stdout.strip():
                print("No changes found to generate a commit message.", file=sys.stderr)
                sys.exit(0)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def get_change_analysis():
    """Get change analysis from environment variable if available."""
    analysis_json = os.environ.get('PIPULATE_CHANGE_ANALYSIS')
    if analysis_json:
        try:
            return json.loads(analysis_json)
        except:
            pass
    return {
        'added_files': [], 'deleted_files': [], 'modified_files': [], 'renamed_files': [],
        'lines_added': 0, 'lines_deleted': 0, 'is_housekeeping': False,
        'change_summary': 'Files modified', 'primary_action': 'modified'
    }

def append_commit_to_conversation(commit_message, change_analysis, model_used):
    if not CONVERSATION_SYSTEM_AVAILABLE:
        return
    try:
        conv_system = AppendOnlyConversationSystem()
        formatted_message = f"""📝 **AI Generated Commit Message**

**Commit:** {commit_message}

**Change Analysis:**
- Files added: {len(change_analysis['added_files'])}
- Files deleted: {len(change_analysis['deleted_files'])}
- Files modified: {len(change_analysis['modified_files'])}
- Lines added: +{change_analysis['lines_added']}
- Lines deleted: -{change_analysis['lines_deleted']}
- Primary action: {change_analysis['primary_action']}
- Is housekeeping: {change_analysis['is_housekeeping']}

**Summary:** {change_analysis['change_summary']}

*This commit message was generated using {model_used} and appended to conversation history via append-only system.*"""
        conv_system.append_message('system', formatted_message)
    except Exception as e:
        print(f"⚠️  Error appending to conversation history: {e}", file=sys.stderr)

def chat_with_ollama(input_text, prompt_template, model=DEFAULT_MODEL, timeout=90):
    chosen_model = model if model else DEFAULT_MODEL
    try:
        models_response = requests.get(f"{OLLAMA_API_URL}/tags", timeout=timeout)
        models_response.raise_for_status()
        models = [m['name'] for m in models_response.json()['models']]
        
        target_model = model if model else DEFAULT_MODEL
        if target_model in models:
            chosen_model = target_model
        else:
            partial_matches = [m for m in models if m.startswith(target_model)]
            if partial_matches:
                chosen_model = partial_matches[0]
            else:
                chosen_model = get_best_llama_model(models)
        
        full_prompt = prompt_template.format(input_text=input_text)
        conversation_history.append({"role": "user", "content": full_prompt})

        chat_response = requests.post(
            f"{OLLAMA_API_URL}/chat",
            json={"model": chosen_model, "messages": conversation_history, "stream": False},
            timeout=timeout
        )
        chat_response.raise_for_status()
        
        assistant_reply = chat_response.json()['message']['content'].strip()
        conversation_history.append({"role": "assistant", "content": assistant_reply})
        
        return assistant_reply, chosen_model
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}", chosen_model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Pipulate AI Operations.")
    parser.add_argument("--prompt", help="Prompt template (use {input_text} as placeholder)")
    parser.add_argument("--format", choices=["markdown", "plain"], default="plain", help="Output format")
    parser.add_argument("--model", help=f"Specific model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--auto", action="store_true", help="Automated git release commit mode")
    args = parser.parse_args()

    if args.auto:
        # Release workflow mode
        change_analysis = get_change_analysis()
        staged_diff = get_staged_diff()
        
        # Hydrate verbatim contents for newly added files to cure AI blindspots
        added_files_content = ""
        for filename in change_analysis.get('added_files', []):
            filepath = Path(filename)
            if not filepath.is_absolute():
                filepath = project_root / filepath
            if filepath.exists() and filepath.is_file():
                try:
                    # Skip binaries and cap size to prevent prompt explosion
                    if filepath.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.bin'}:
                        added_files_content += f"\n\n--- NEW FILE: {filename} (binary/skipped) ---"
                        continue
                    content = filepath.read_text(encoding='utf-8')
                    if len(content) > 15000:
                        preview = content[:12000] + "\n\n... [truncated - full content available in working tree] ..."
                        added_files_content += f"\n\n--- NEW FILE VERBATIM CONTENT (truncated): {filename} ---\n{preview}"
                    else:
                        added_files_content += f"\n\n--- NEW FILE VERBATIM CONTENT: {filename} ---\n{content}"
                except Exception as e:
                    added_files_content += f"\n\n--- NEW FILE VERBATIM CONTENT: {filename} (Error reading: {e}) ---"
        
        if added_files_content:
            staged_diff += added_files_content
        
        analysis_text = f"""
- Files added: {len(change_analysis['added_files'])}
- Files deleted: {len(change_analysis['deleted_files'])}
- Files modified: {len(change_analysis['modified_files'])}
- Lines added: +{change_analysis['lines_added']}
- Lines deleted: -{change_analysis['lines_deleted']}
"""
        # We stop replacing here, leaving {input_text} intact in the template
        formatted_prompt = COMMIT_PROMPT_TEMPLATE.replace("{change_analysis}", analysis_text) \
                                                 .replace("{primary_action}", change_analysis['primary_action']) \
                                                 .replace("{is_housekeeping}", str(change_analysis['is_housekeeping'])) \
                                                 .replace("{change_summary}", change_analysis['change_summary'])
        
        # Pass staged_diff directly as input_text so it bypasses .format() vulnerabilities!
        result, used_model = chat_with_ollama(staged_diff, formatted_prompt, model=args.model)

        # Defensive fence-stripping: the local model is non-deterministic about
        # wrapping its reply in a Markdown code fence, and is especially prone to
        # it when the diff is itself mostly Markdown/comment churn. A bare ```
        # opening line is exactly what `head -1` in the m() shell alias grabbed,
        # producing an empty/garbage commit subject. Strip leading and trailing
        # fence lines (with optional language tag) so the real subject survives.
        _lines = result.split('\n')
        if _lines and re.match(r'^\s*```[a-zA-Z0-9]*\s*$', _lines[0]):
            _lines = _lines[1:]
        if _lines and re.match(r'^\s*```\s*$', _lines[-1]):
            _lines = _lines[:-1]
        result = '\n'.join(_lines).strip()

        append_commit_to_conversation(result, change_analysis, used_model)
        
    else:
        # Standard init.lua stdin mode
        if not args.prompt:
            print("Error: --prompt is required when not in --auto mode", file=sys.stderr)
            sys.exit(1)
            
        input_text = sys.stdin.read().strip()
        result, used_model = chat_with_ollama(input_text, args.prompt, model=args.model)
        
        # Ensure single line output for Neovim strictly
        result = result.replace('\n', ' ').strip()
        result = ' '.join(result.split())
        
        if args.format == "markdown":
            result = f"## {result}"

    # Universal delimiter output for robust parsing
    print(f"{result}\n__MODEL_DELIMITER__\n{used_model}", end='')
