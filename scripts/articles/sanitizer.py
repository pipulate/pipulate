import re
import argparse
from pathlib import Path
import common

# Paths
ARTICLE_FILE = Path(__file__).parent / "article.txt"
PII_FILE = Path.home() / ".config" / "pipulate" / "pii_substitutions.txt"

# Safe IPs that don't need redaction (localhost, common DNS, etc.)
SAFE_IPS = {'127.0.0.1', '0.0.0.0', '8.8.8.8', '1.1.1.1'}

# Fence labels whose ENTIRE fenced block is dropped before publication.
# The real content survives only at the original source (your journal / neovim
# buffer); after a public sanitize it is gone from article.txt and never
# reaches the AI editing pass, the generated markdown, or any blog target.
PRIVATE_FENCE_LABELS = {'private', 'journal-only', 'redact', 'internal-only', 'no-publish'}


def strip_prompt_boundary(content: str) -> str:
    """Eradicate the prompt-injection artifact and collapse surrounding whitespace."""
    return re.sub(r'\n*^--- BEGIN NEW ARTICLE ---$\n*', '\n\n', content, flags=re.MULTILINE)


def redact_ips(content: str) -> str:
    """Replace any non-safe IPv4 address with a redaction token (both lanes)."""
    def ip_replacer(match):
        ip = match.group(0)
        return ip if ip in SAFE_IPS else "[REDACTED_IP]"

    ip_pattern = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    )
    return ip_pattern.sub(ip_replacer, content)


def strip_private_fences(content: str):
    """Remove whole ```private (etc.) fenced blocks. Returns (content, count).

    Non-greedy match stops at the first closing fence, so a private block
    should hold plain text, not nested code fences.
    """
    labels = '|'.join(re.escape(label) for label in sorted(PRIVATE_FENCE_LABELS))
    pattern = re.compile(
        rf'^[ \t]*```(?:{labels})[ \t]*\n.*?\n[ \t]*```[ \t]*$\n?',
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    new_content, count = pattern.subn('', content)
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)  # collapse the holes
    return new_content, count


# Inline player-piano markers for paragraph/phrase-level privacy — the same
# [[[token]]] bracket dialect already used for SEARCH/REPLACE and TODO_SLUGS
# blocks elsewhere in this toolchain. The fence stripper above handles whole
# blocks; this handles a clause or paragraph mid-sentence without forcing a
# line break and without colliding with real code fences. `p` is shorthand
# for `private` — either spelling works, but an opener must be closed by its
# own spelling (the backreference below enforces that).
INLINE_PRIVATE_PATTERN = re.compile(
    r'\[\[\[(p|private)\]\]\](.*?)\[\[\[/\1\]\]\]',
    flags=re.DOTALL | re.IGNORECASE,
)
INLINE_PRIVATE_STRAY_PATTERN = re.compile(
    r'\[\[\[/?(?:p|private)\]\]\]',
    flags=re.IGNORECASE,
)


def strip_private_inline(content: str):
    """Remove inline [[[p]]]...[[[/p]]] / [[[private]]]...[[[/private]]] spans.

    Returns (content, count). Unlike strip_private_fences this works mid-line
    or mid-paragraph, so a single clause can poof without exiling the rest of
    the paragraph onto its own fenced block.
    """
    new_content, count = INLINE_PRIVATE_PATTERN.subn('', content)
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)  # collapse the holes
    stray = INLINE_PRIVATE_STRAY_PATTERN.findall(new_content)
    if stray:
        print(f"⚠️  Found {len(stray)} unmatched [[[p]]]/[[[private]]] marker(s) — check for a missing close tag.")
    return new_content, count


def load_pii_rules():
    """Load (pattern, replacement) tuples from pii_substitutions.txt, if present."""
    rules = []
    if PII_FILE.exists():
        for line in PII_FILE.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            if ' === ' in line:
                pattern, repl = line.split(' === ', 1)
                rules.append((pattern, repl))
    return rules


def apply_pii(content: str):
    """Apply the role-based PII substitution table. Returns (content, count)."""
    total = 0
    for pattern, replacement in load_pii_rules():
        try:
            content, n = re.subn(pattern, replacement, content)
            total += n
        except re.error as e:
            print(f"⚠️  Skipping bad PII pattern {pattern!r}: {e}")
    return content, total


def sanitize_article(public: bool):
    """Read article.txt, scrub it for the chosen lane, and save back in place."""
    if not ARTICLE_FILE.exists():
        print(f"⚠️  {ARTICLE_FILE.name} not found.")
        return

    content = ARTICLE_FILE.read_text()
    original_content = content

    # --- BOTH LANES: strip prompt boundary + loose IPs ---
    content = strip_prompt_boundary(content)
    content = redact_ips(content)

    if public:
        # --- PUBLIC LANE: drop private fences + scrub names to roles ---
        content, fence_count = strip_private_fences(content)
        content, inline_count = strip_private_inline(content)
        content, pii_count = apply_pii(content)
        if fence_count:
            print(f"🔒 Removed {fence_count} private fenced block(s) — kept only at source.")
        if inline_count:
            print(f"🔒 Removed {inline_count} inline private span(s) — kept only at source.")
        if pii_count:
            print(f"🪄 Applied {pii_count} PII substitution(s).")
        if not fence_count and not inline_count and not pii_count:
            print("ℹ️  Public lane: no private fences, inline spans, or PII matches found.")
    else:
        print("ℹ️  Private lane (grim): prompt boundary + IP scrub only; fences and names preserved.")

    if content != original_content:
        ARTICLE_FILE.write_text(content)
        print("✅ Article sanitized!")
    else:
        print("ℹ️  Nothing to scrub. Article is already clean.")


def resolve_lane(args) -> bool:
    """Returns True for the public (full-scrub) lane, False for private.

    Precedence: an explicit --public/--private flag always beats blogs.json;
    otherwise the target's 'lane' attribute decides. Fail closed: anything
    that is not an explicit, recognized 'private' gets the full defensive
    scrub, including a missing target, missing lane key, or typo'd value.
    """
    if args.private:
        return False
    if args.public:
        return True
    targets = common.load_targets()
    target_config = targets.get(str(args.target), {})
    lane = str(target_config.get('lane', 'public')).strip().lower()
    if lane == 'private':
        print(f"🎯 Lane resolved from blogs.json: private ({target_config.get('name', args.target)})")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Defensive pre-publish sanitizer for article.txt."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--public', action='store_true',
        help="Explicit override: full defensive scrub (strip private fences + apply PII substitutions)."
    )
    group.add_argument(
        '--private', action='store_true',
        help="Explicit override: light lane (strip prompt boundary + IPs only; keep fences and names)."
    )
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    # Data-driven routing: the target's 'lane' in blogs.json decides,
    # unless an explicit flag overrides. Fail closed toward public scrub.
    sanitize_article(public=resolve_lane(args))


if __name__ == "__main__":
    main()
