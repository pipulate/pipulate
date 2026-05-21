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

PROGRESSIVE_REVEAL_CONTINUATION_PROMPT = """Context verified.

You now have the full article context I requested through the progressive-reveal loop.

First, synthesize the articles into a concise explanation of the “organ grinder” philosophy: the idea that the human remains the deliberate operator of a hand-cranked, deterministic machine, while AI acts as the performing monkey only when given precise context, bounded tools, and explicit next-step instructions.

Then identify the three most relevant missing articles from the article index that would deepen this theme. Choose articles that clarify one of these gaps:

1. How the context compiler turns scattered files and articles into a reliable working memory.
2. How deterministic SEARCH/REPLACE patching replaces vague agentic editing.
3. How the clipboard / shell / git loop becomes a safe human-supervised actuator.

End your answer with exactly one TODO block in this format:

[[[TODO_SLUGS]]]
slug-one
slug-two
slug-three
[[[END_SLUGS]]]

Use only clean slugs. Do not include dates, token counts, filenames, markdown extensions, bullets, or commentary inside the TODO block."""


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
            PROGRESSIVE_REVEAL_CONTINUATION_PROMPT,
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