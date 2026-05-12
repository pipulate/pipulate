#!/usr/bin/env python3
"""
AI Commit Message Generator for Pipulate

This script uses a local LLM (via Ollama) to generate a conventional
commit message based on the currently staged git changes.

🧹 LEGACY PURGED: Now uses append-only conversation system
- Generated commit messages are appended to conversation history
- Bulletproof persistence across restarts and releases
- No vulnerable JSON blob overwrites

Usage:
    python scripts/release/ai_commit.py
"""
import subprocess
import requests
import json
import sys
import os
from pathlib import Path

# Add the scripts directory to sys.path for imports
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Add project root to sys.path to access config
project_root = scripts_dir.parent
sys.path.insert(0, str(project_root))
import config as CFG

try:
    from append_only_conversation import AppendOnlyConversationSystem
    CONVERSATION_SYSTEM_AVAILABLE = True
except ImportError:
    CONVERSATION_SYSTEM_AVAILABLE = False
    print("⚠️  Warning: Append-only conversation system not available", file=sys.stderr)

# Configuration for the local LLM
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = CFG.DEFAULT_PROMPT_MODEL.split(':')[0]

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

Based on this analysis, choose the appropriate commit type:
- "chore" for housekeeping, cleanup, deletions of test/temp files
- "feat" for genuine new features or capabilities  
- "fix" for bug fixes
- "docs" for documentation changes
- "refactor" for code restructuring
- "perf" for performance improvements
- "test" for test-related changes
- "style" for formatting changes

The commit message should:
- Use a valid conventional commit type based on the ACTUAL nature of changes
- Have a brief, imperative subject line (max 50 chars)
- Accurately reflect whether content was ADDED, REMOVED, or MODIFIED
- Provide a more detailed body explaining the "what" and "why" of the changes, if necessary
- The entire response should be ONLY the commit message, with no extra text or explanations

Here is the git diff of staged changes:
--- GIT DIFF START ---
{git_diff}
--- GIT DIFF END ---

Generate the commit message now, being especially careful to accurately represent additions vs deletions.
"""

def get_change_analysis():
    """Get change analysis from environment variable if available."""
    analysis_json = os.environ.get('PIPULATE_CHANGE_ANALYSIS')
    if analysis_json:
        try:
            return json.loads(analysis_json)
        except:
            pass
    
    # Fallback default analysis
    return {
        'added_files': [],
        'deleted_files': [],
        'modified_files': [],
        'renamed_files': [],
        'lines_added': 0,
        'lines_deleted': 0,
        'is_housekeeping': False,
        'change_summary': 'Files modified',
        'primary_action': 'modified'
    }

def get_staged_diff():
    """Gets the diff of currently staged files."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--staged'],
            capture_output=True,
            text=True,
            check=True
        )
        if not result.stdout.strip():
            # If no staged changes, check for unstaged changes
            result = subprocess.run(
                ['git', 'diff'],
                capture_output=True,
                text=True,
                check=True
            )
            if not result.stdout.strip():
                print("No changes found to generate a commit message.")
                sys.exit(0)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def generate_commit_message(diff_content, change_analysis):
    """Sends the diff to a local LLM to generate a commit message with change analysis context."""
    
    # Format the change analysis for the prompt
    analysis_text = f"""
- Files added: {len(change_analysis['added_files'])} ({', '.join(change_analysis['added_files'][:3])}{'...' if len(change_analysis['added_files']) > 3 else ''})
- Files deleted: {len(change_analysis['deleted_files'])} ({', '.join(change_analysis['deleted_files'][:3])}{'...' if len(change_analysis['deleted_files']) > 3 else ''})
- Files modified: {len(change_analysis['modified_files'])} ({', '.join(change_analysis['modified_files'][:3])}{'...' if len(change_analysis['modified_files']) > 3 else ''})
- Lines added: +{change_analysis['lines_added']}
- Lines deleted: -{change_analysis['lines_deleted']}
"""

    prompt = COMMIT_PROMPT_TEMPLATE.format(
        git_diff=diff_content,
        change_analysis=analysis_text,
        primary_action=change_analysis['primary_action'],
        is_housekeeping=change_analysis['is_housekeeping'],
        change_summary=change_analysis['change_summary']
    )
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,  # Low temperature for factual, consistent output
            "top_p": 0.8,
        }
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        return response_data.get("response", "chore: Update project files").strip()
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama API at {OLLAMA_API_URL}: {e}", file=sys.stderr)
        print("Please ensure Ollama is running and the model is available.", file=sys.stderr)
        print(f"To pull the model, run: ollama pull {OLLAMA_MODEL}", file=sys.stderr)
        sys.exit(1)

def append_commit_to_conversation(commit_message, change_analysis):
    """Append the generated commit message to conversation history using append-only system."""
    if not CONVERSATION_SYSTEM_AVAILABLE:
        print("⚠️  Skipping conversation append: conversation system not available", file=sys.stderr)
        return
    
    try:
        # Initialize conversation system
        conv_system = AppendOnlyConversationSystem()
        
        # Create a formatted message about the commit
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

*This commit message was generated using {OLLAMA_MODEL} and appended to conversation history via append-only system.*"""
        
        # Append to conversation history
        message_id = conv_system.append_message('system', formatted_message)
        
        print(f"✅ Commit message appended to conversation history (ID: {message_id})", file=sys.stderr)
        
    except Exception as e:
        print(f"⚠️  Error appending to conversation history: {e}", file=sys.stderr)

if __name__ == "__main__":
    change_analysis = get_change_analysis()
    staged_diff = get_staged_diff()
    commit_message = generate_commit_message(staged_diff, change_analysis)
    
    # 🧹 NEW: Append commit message to conversation history using append-only system
    append_commit_to_conversation(commit_message, change_analysis)
    
    # Print only the commit message to stdout so it can be captured by publish.py
    print(commit_message) 
