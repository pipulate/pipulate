#!/usr/bin/env python3
import re
import subprocess
import sys
import platform
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# THE WEBCLIP AIRLOCK (2026-07-06): browsers forgive what strict XML parsers
# fatally reject. Two capture-time constructs are known landmines downstream:
#   1. Search-result citation cards arrive as <a> wrapping favicon <img>s and
#      stacked <div>s; markdownify faithfully emits ONE markdown link spanning
#      multiple paragraphs, and per-paragraph inline parsers then orphan the
#      '](url)' tail into a malformed URL.
#   2. Bare mid-line ``` runs (quoted fences inside captured dialogue) desync
#      backtick pairing for the rest of the line, exposing backticked
#      pseudo-tags like `<module>` as live HTML.
# The airlock repairs both BEFORE the text re-enters the copy-paste buffer,
# so nothing leaves this script that cannot survive publishing pipelines with
# strict XML parser requirements (like Confluence). Public-side renderers are
# unaffected: a one-line link and a literal [triple-backtick] token render
# fine everywhere. Same doctrine as apply.py's AST check: validate at the
# actuator boundary, fail nothing downstream.
FENCE_RUN_RE = re.compile(r'`{3,}')
NEUTRAL_FENCE_TOKEN = '[triple-backtick]'
_BLOCKISH_IN_ANCHOR = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                       'br', 'img', 'ul', 'ol', 'table', 'blockquote']


def flatten_block_anchors(soup):
    """Collapse anchors wrapping block content into single-line text links."""
    count = 0
    for anchor in soup.find_all('a'):
        if anchor.find(_BLOCKISH_IN_ANCHOR):
            text = ' '.join(anchor.get_text(separator=' ', strip=True).split())
            anchor.clear()
            anchor.string = text or anchor.get('href', '')
            count += 1
    return count


def enforce_fence_hygiene(md_text):
    """Apply the fence contract at capture time (mirror of sanitizer.py).

    1. A fence is recognized ONLY at column 0; any 3+ backtick run anywhere
       else on a line is neutralized to a literal token.
    2. Naked opening fences get a 'text' language label.
    3. An unclosed fence at EOF gets a bare closing fence appended.
    Returns (text, neutralized, labeled, closed).
    """
    out = []
    in_fence = False
    neutralized = labeled = closed = 0
    for line in md_text.split('\n'):
        if '```' in line and not line.startswith('```'):
            line, n = FENCE_RUN_RE.subn(NEUTRAL_FENCE_TOKEN, line)
            neutralized += n
        if line.startswith('```'):
            if not in_fence:
                if line.strip() == '```':
                    line = '```text'
                    labeled += 1
                in_fence = True
            else:
                in_fence = False
        out.append(line)
    if in_fence:
        out.append('```')
        closed += 1
    return '\n'.join(out), neutralized, labeled, closed

def get_clipboard_html():
    # TODO: Expand for macOS (pbpaste) and Windows (win32clipboard).
    if platform.system().lower() == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-target', 'text/html', '-o'], 
                                capture_output=True, text=True)
        return result.stdout if result.stdout.strip() else None
    return None

def get_clipboard_text():
    # TODO: Expand for macOS (pbpaste) and Windows (win32clipboard).
    if platform.system().lower() == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                capture_output=True, text=True)
        return result.stdout
    return ""

def set_clipboard(text: str):
    # TODO: Expand for macOS (pbcopy) and Windows (win32clipboard).
    if platform.system().lower() == "linux":
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)

def transform():
    html_content = get_clipboard_html()
    flattened = 0
    
    if not html_content:
        md_text = get_clipboard_text()
        if not md_text or not md_text.strip():
            sys.exit("❌ Clipboard is empty or contains no compatible data.")
        print("ℹ️ No HTML found, passing plain text.")
    else:
        # 2. Clean and Convert
        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        content = soup.body if soup.body else soup
        md_text = md(str(content))

    # 3. Push back
    set_clipboard(md_text)
    print("✨ Clipboard transformed to Markdown.")

if __name__ == "__main__":
    transform()
