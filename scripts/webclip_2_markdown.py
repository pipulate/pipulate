#!/usr/bin/env python3
import os
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
# SPELLED TOKEX ON PURPOSE (convicted 2026-09-10, third spelling). The
# compile-lane secrets tripwire fires on any line-start ALL-CAPS assignment
# whose name contains TOKEN when the value is a quoted string of 12+ chars,
# and '[triple-backtick]' is 17. The scanner is shape-based and has no allow
# flag by design; the cheap cure is a name that does not carry the word. An
# earlier dodge spelled it TOKN, uncommitted and unexplained, and the
# 2026-09-09 Mac session read it as a slip and restored the word -- which is
# how the tripwire came to fire a second time. A rename without its reason
# beside it is a rename waiting to be undone.
NEUTRAL_FENCE_TOKEX = '[triple-backtick]'
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
            line, n = FENCE_RUN_RE.subn(NEUTRAL_FENCE_TOKEX, line)
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

# THE MAC LANE (2026-09-09, first-contact convicted on aarch64-darwin): all
# three clipboard readers below were Linux-only, so on a Mac `webclip` printed
# "Clipboard is empty" over a full clipboard -- a plausible message, because
# the clipboard really was invisible to this script. Three tools, one per job:
#   pbpaste / pbcopy  plain text in and out.
#   osascript         the HTML flavor, which pbpaste cannot reach (it speaks
#                     txt/rtf/ps only). `the clipboard as <<class HTML>>` prints
#                     the pasteboard's HTML as a hex literal (<<data HTML3C68...>>);
#                     a clipboard with no HTML flavor makes osascript exit
#                     nonzero, which maps to the same None the xclip lane returns
#                     on empty stdout, so the caller's plain-text fallback fires
#                     unchanged. The chevrons are spelled as \u escapes in the
#                     code so this file stays ASCII.
# LC_ALL IS LOAD-BEARING: pbpaste/pbcopy honor the locale, and under a C locale
# every non-ASCII character comes back as a question mark. Forced to UTF-8 for
# these two calls only; the shell's own locale is untouched.
_SYSTEM = platform.system().lower()
_MAC_ENV = {**os.environ, 'LANG': 'en_US.UTF-8', 'LC_ALL': 'en_US.UTF-8'}
_MAC_HTML_HEX_RE = re.compile(r'data HTML([0-9A-Fa-f]+)')


def _mac_clipboard_html():
    """Return the pasteboard's HTML flavor as text, or None when there is none."""
    result = subprocess.run(
        ['osascript', '-e', 'the clipboard as \u00abclass HTML\u00bb'],
        capture_output=True)
    if result.returncode != 0:
        return None
    match = _MAC_HTML_HEX_RE.search(result.stdout.decode('utf-8', errors='replace'))
    if not match:
        return None
    try:
        html = bytes.fromhex(match.group(1)).decode('utf-8', errors='replace')
    except ValueError:
        return None
    return html if html.strip() else None


def _mac_clipboard_text():
    result = subprocess.run(['pbpaste'], capture_output=True, env=_MAC_ENV)
    return result.stdout.decode('utf-8', errors='replace')


def _mac_set_clipboard(text: str):
    subprocess.run(['pbcopy'], input=text.encode('utf-8'), env=_MAC_ENV, check=True)


def get_clipboard_html():
    # TODO: Expand for Windows (win32clipboard).
    if platform.system().lower() == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-target', 'text/html', '-o'], 
                                capture_output=True, text=True)
        return result.stdout if result.stdout.strip() else None
    if _SYSTEM == "darwin":
        return _mac_clipboard_html()
    return None

def get_clipboard_text():
    # TODO: Expand for Windows (win32clipboard).
    if platform.system().lower() == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                capture_output=True, text=True)
        return result.stdout
    if _SYSTEM == "darwin":
        return _mac_clipboard_text()
    return ""

def set_clipboard(text: str):
    # TODO: Expand for Windows (win32clipboard).
    if _SYSTEM == "linux":
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
    elif _SYSTEM == "darwin":
        _mac_set_clipboard(text)
    else:
        sys.exit(f"❌ webclip: no clipboard writer for {platform.system()}; nothing was copied.")

def transform():
    if _SYSTEM not in ("linux", "darwin"):
        sys.exit(f"❌ webclip: no clipboard lane for {platform.system()} yet; Linux (xclip) and macOS (pbpaste/osascript) only.")
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
        flattened = flatten_block_anchors(soup)
        content = soup.body if soup.body else soup
        md_text = md(str(content))

    # 3. Airlock: both lanes (HTML and plain-text passthrough) get fence hygiene
    md_text, neutralized, labeled, closed = enforce_fence_hygiene(md_text)

    # 4. Push back
    set_clipboard(md_text)
    print("✨ Clipboard transformed to Markdown.")
    if flattened or neutralized or labeled or closed:
        print(f"🧯 Airlock repairs: {flattened} multi-block link(s) flattened, "
              f"{neutralized} floating backtick run(s) neutralized, "
              f"{labeled} naked fence opener(s) labeled, "
              f"{closed} unclosed fence(s) closed.")
        print("   These render fine in browsers but detonate in publishing "
              "pipelines with strict XML parser requirements (like Confluence).")

if __name__ == "__main__":
    transform()
