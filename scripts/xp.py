#!/usr/bin/env python3
"""
xp.py - The Clipboard Transformer

Reads the OS clipboard, parses for structured token blocks, and routes to the
appropriate action. Mirrors apply.py but transforms clipboard state instead of
mutating files.

Supported blocks:
  [[[TODO_SLUGS]]] ... [[[END_SLUGS]]]  -> runs prompt_foo.py @PROGRESSIVE_REVEAL_PROMPT --chop CHOP_PROGRESSIVE_REVEAL --slugs

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


def parse_todo_slugs(text: str):
    match = re.search(
        r'\[\[\[TODO_SLUGS\]\]\]\s*\n(.*?)\n\[\[\[END_SLUGS\]\]\]',
        text,
        re.DOTALL
    )
    if not match:
        return None
    raw = match.group(1).strip()
    slugs = re.split(r'[\s,]+', raw)
    return [s.strip() for s in slugs if s.strip()]


def route(text: str) -> bool:
    slugs = parse_todo_slugs(text)
    if slugs is not None:
        print(f"🎯 Found TODO_SLUGS block with {len(slugs)} slug(s):")
        for s in slugs:
            print(f"   • {s}")
        cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "prompt_foo.py"),
            "@PROGRESSIVE_REVEAL_PROMPT",
            "--chop",
            "CHOP_PROGRESSIVE_REVEAL",
            "--no-tree",
            "--slugs",
        ] + slugs
        print(f"\n🚀 Running: {' '.join(cmd)}\n")
        subprocess.run(cmd, cwd=REPO_ROOT)
        return True
    return False


def main():
    text = get_clipboard()
    if not text.strip():
        print("❌ Clipboard is empty.")
        sys.exit(1)
    if not route(text):
        print("❌ No recognized token blocks found in clipboard.")
        print("   Supported: [[[TODO_SLUGS]]] ... [[[END_SLUGS]]]")
        sys.exit(1)


if __name__ == "__main__":
    main()