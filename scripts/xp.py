#!/usr/bin/env python3
"""
xp.py - The Clipboard Transformer

Reads the OS clipboard, parses for structured token blocks, and routes to the
appropriate action. Mirrors apply.py but transforms clipboard state instead of
mutating files.

Supported blocks:
  [[[TODO_SLUGS]]] ... [[[END_SLUGS]]]  -> request full article context by clean semantic slug
  [[[TODO_FILES]]] ... [[[END_FILES]]]  -> request codebase files by repo-relative path
  [[[APPLY_PATCH]]] ... [[[END_APPLY_PATCH]]]  -> pipe an explicit patch payload to apply.py

Flow:
  1. LLM responds with a structured block
  2. Copy the response
  3. Type `xp` in the terminal
  4. This script parses, acts, and leaves the compiled context in your clipboard

Usage: xp
"""

import sys
import re
import os
import subprocess
import platform

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROGRESSIVE_REVEAL_CONTINUATION_PROMPT = "Context verified. Please address the operator instructions or steering details below."


def get_clipboard() -> str:
    if os.getenv("SSH_CLIENT"):
        bridge = "/tmp/clipboard_bridge.txt"
        if os.path.exists(bridge):
            with open(bridge, "r", encoding="utf-8") as f:
                return f.read()
        print("❌ SSH session detected but no bridge file found at /tmp/clipboard_bridge.txt")
        sys.exit(1)
    system = platform.system().lower()
    if system == "darwin":
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    elif system == "linux":
        result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
    else:
        print(f"❌ Unsupported OS: {system}")
        sys.exit(1)
    return result.stdout


def _parse_block(text: str, start: str, end: str):
    match = re.search(
        rf'\[\[\[{re.escape(start)}\]\]\]\s*\n(.*?)\n\[\[\[{re.escape(end)}\]\]\]',
        text,
        re.DOTALL
    )
    if not match:
        return None
    return match.group(1).strip()


def _parse_items(raw: str):
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        line = re.sub(r'^\s*[-*]\s+', '', line)
        items.extend(part.strip() for part in re.split(r'[\s,]+', line) if part.strip())
    return items


def parse_todo_slugs(text: str):
    raw = _parse_block(text, "TODO_SLUGS", "END_SLUGS")
    if raw is None:
        return None
    return _parse_items(raw)


def parse_todo_files(text: str):
    raw = _parse_block(text, "TODO_FILES", "END_FILES")
    if raw is None:
        return None
    return _parse_items(raw)


def parse_todo_prompt(text: str):
    return _parse_block(text, "TODO_PROMPT", "END_PROMPT")


def parse_apply_patch(text: str):
    return _parse_block(text, "APPLY_PATCH", "END_APPLY_PATCH")


def route(text: str) -> bool:
    did_something = False

    patch_payload = parse_apply_patch(text)
    if patch_payload is not None:
        apply_path = os.path.join(REPO_ROOT, "apply.py")
        if not os.path.exists(apply_path):
            print(f"❌ APPLY_PATCH requested but apply.py was not found at {apply_path}")
            sys.exit(1)
        print("🩹 Found APPLY_PATCH block; piping inner payload to apply.py\n")
        result = subprocess.run([sys.executable, apply_path], input=patch_payload, text=True, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"❌ APPLY_PATCH failed with exit code {result.returncode}; stopping before any follow-up context compile.")
            sys.exit(result.returncode)
        
        # Show the results of the patch
        print("\n--- Patch Diff ---")
        subprocess.run(['git', '--no-pager', 'diff', 'HEAD'], cwd=REPO_ROOT)
        print("------------------\n")
        did_something = True


    slugs = parse_todo_slugs(text)
    files = parse_todo_files(text)
    todo_prompt = parse_todo_prompt(text)

    # Check for local prompt.md steering file in repo root
    prompt_md_path = os.path.join(REPO_ROOT, "prompt.md")
    local_prompt = ""
    if os.path.exists(prompt_md_path):
        with open(prompt_md_path, "r", encoding="utf-8") as f:
            local_prompt = f.read().strip()
        if local_prompt:
            print(f"📖 Found local prompt.md steering ({len(local_prompt)} chars)")
    if slugs is not None or files is not None or todo_prompt is not None or local_prompt:
        slugs = slugs or []
        files = files or []

        if slugs:
            print(f"🎯 Found TODO_SLUGS block with {len(slugs)} slug(s):")
            for s in slugs:
                print(f"    • {s}")

        if files:
            print(f"📁 Found TODO_FILES block with {len(files)} file(s):")
            for f in files:
                print(f"    • {f}")

        if todo_prompt:
            print(f"📝 Found TODO_PROMPT block:\n   {todo_prompt}")

        if not slugs and not files and not todo_prompt and not local_prompt:
            print("⚠ Context request blocks and prompt.md were empty; no prompt_foo.py compile was run.")
            return True

        cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "prompt_foo.py"),
            PROGRESSIVE_REVEAL_CONTINUATION_PROMPT,
            "--chop",
            "CHOP_PROGRESSIVE_REVEAL",
            "--no-tree",
        ]

        if files:
            cmd += ["--files"] + files
        if slugs:
            cmd += ["--slugs"] + slugs

        # Assemble combined extra prompt from clipboard and local prompt.md
        prompt_parts = []
        if todo_prompt:
            prompt_parts.append(todo_prompt)
        if local_prompt:
            prompt_parts.append(f"### Operator Steering (from prompt.md):\n{local_prompt}")

        if prompt_parts:
            cmd += ["--extra-prompt", "\n\n".join(prompt_parts)]

        print(f"\n🚀 Running: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"❌ prompt_foo.py failed with exit code {result.returncode}; compiled context was not completed.")
            sys.exit(result.returncode)
        did_something = True

    return did_something


def main():
    # Read clipboard gracefully
    text = get_clipboard()
    
    # Run the core router logic
    did_something = route(text)
    
    if not did_something:
        print("❌ No actionable blocks found in clipboard and no prompt.md steering file was detected.")
        print("   Supported clipboard formats:")
        print("   • [[[TODO_SLUGS]]] ... [[[END_SLUGS]]]")
        print("   • [[[TODO_FILES]]] ... [[[END_FILES]]]")
        print("   • [[[APPLY_PATCH]]] ... [[[END_APPLY_PATCH]]]")
        sys.exit(1)


if __name__ == "__main__":
    main()
