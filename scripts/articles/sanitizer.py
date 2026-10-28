import re
import argparse
from pathlib import Path
import common

# Paths
ARTICLE_FILE = Path(__file__).parent / "article.txt"
PII_FILE = Path.home() / ".config" / "pipulate" / "pii_substitutions.txt"
DENYLIST_FILE = Path.home() / ".config" / "pipulate" / "commit_denylist.txt"

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


FENCE_SEGMENT_RE = re.compile(r'(^```[^\n]*\n.*?^```[ \t]*$)', re.MULTILINE | re.DOTALL)


def _is_single_dollar_mathjax(masked_line: str, s_pos: int, e_pos: int) -> bool:
    """True when a single-dollar $...$ span is TeX/MathJax, False for currency or shell."""
    expr = masked_line[s_pos + 1 : e_pos]
    if not (1 <= len(expr) <= 120):
        return False
    if expr[0].isspace() or expr[-1].isspace():
        return False
    prev_ch = masked_line[s_pos - 1] if s_pos > 0 else ""
    next_ch = masked_line[e_pos + 1] if e_pos + 1 < len(masked_line) else ""
    if prev_ch and (prev_ch.isalnum() or prev_ch in "\\$"):
        return False
    if next_ch and (next_ch.isalnum() or next_ch == "$"):
        return False
    if re.match(r"^\d[\d,.]*/[A-Za-z]{2,}", expr) or re.match(r"^\d[\d,.]*[kKmMbB]?\s+[A-Za-z]{2,}", expr):
        return False
    if "\\" in expr:
        return True
    if re.search(r"[\^_=<>&+]", expr):
        return True
    if re.match(r"^(?:[A-Za-z]'?|\d+/\d+|[A-Za-z]/[A-Za-z])$", expr):
        return True
    if re.match(r"^[A-Za-z]+\([^()]*\)$", expr):
        return True
    if re.match(r"^[A-Za-z0-9_]+\s*[-+*/]\s*[A-Za-z0-9_]+$", expr):
        return True
    return False


def _double_single_dollar_mathjax_line(line: str) -> tuple[str, int]:
    """Upgrade single-dollar $...$ MathJax spans on one line to $$...$$."""
    if '$' not in line or line.startswith(('    ', '\t')):
        return line, 0
    shadow = re.sub(r'`+[^`]*`+', lambda m: '#' * len(m.group(0)), line)
    shadow = re.sub(r'\$\$[\s\S]*?\$\$', lambda m: '#' * len(m.group(0)), shadow)
    shadow = re.sub(r'\$\$+', lambda m: '#' * len(m.group(0)), shadow)
    positions = [m.start() for m in re.finditer(r'\$', shadow)]
    if len(positions) < 2:
        return line, 0
    matches = []
    idx = 0
    while idx + 1 < len(positions):
        s_pos, e_pos = positions[idx], positions[idx + 1]
        if _is_single_dollar_mathjax(shadow, s_pos, e_pos):
            matches.append((s_pos, e_pos))
            idx += 2
        else:
            idx += 1
    if not matches:
        return line, 0
    out = []
    cursor = 0
    for s_pos, e_pos in matches:
        out.append(line[cursor:s_pos])
        out.append(f"$${line[s_pos + 1 : e_pos]}$$")
        cursor = e_pos + 1
    out.append(line[cursor:])
    return "".join(out), len(matches)


def double_single_dollar_mathjax(content: str) -> tuple[str, int]:
    """Double single-dollar MathJax spans outside fenced code blocks. Returns (new_content, count)."""
    parts = FENCE_SEGMENT_RE.split(content)
    total = 0
    for idx in range(0, len(parts), 2):
        lines = parts[idx].split('\n')
        for li, ln in enumerate(lines):
            new_ln, n = _double_single_dollar_mathjax_line(ln)
            if n:
                lines[li] = new_ln
                total += n
        parts[idx] = '\n'.join(lines)
    return ''.join(parts), total


def heal_corpus_mathjax(posts_dir: Path, dry_run: bool = False) -> tuple[int, int]:
    """Batch-upgrade single-dollar MathJax spans across dated *.md posts while preserving frontmatter and mtime."""
    import os
    files_changed = 0
    spans_changed = 0
    for md_path in sorted(posts_dir.glob("*.md")):
        if not md_path.name[:4].isdigit():
            continue
        raw = md_path.read_text(encoding="utf-8", errors="ignore")
        if raw.startswith("---\n"):
            fm_parts = raw.split("\n---\n", 1)
            if len(fm_parts) == 2:
                head, body = fm_parts[0] + "\n---\n", fm_parts[1]
            else:
                head, body = "", raw
        else:
            head, body = "", raw
        new_body, count = double_single_dollar_mathjax(body)
        if count > 0 and new_body != body:
            files_changed += 1
            spans_changed += count
            if not dry_run:
                st = md_path.stat()
                md_path.write_text(head + new_body, encoding="utf-8")
                os.utime(md_path, (st.st_atime, st.st_mtime))
    mode = "DRY RUN" if dry_run else "HEALED"
    print(f"🧮 MathJax Corpus [{mode}]: {spans_changed} span(s) across {files_changed} post(s) in {posts_dir}.")
    return files_changed, spans_changed


def neutralize_inception_artifacts(content: str) -> str:
    """Heal web-UI autolinks, inverted bold/code closures, and wrapped backticked cue examples."""
    # 1. Unwrap self-referential web-UI autolink contamination back to bare URLs (safe everywhere)
    content = re.sub(r'\[(https?://[^\]\s]+)\]\(\1/?\)', r'\1', content)
    content = re.sub(r'\[(www\.[^\]\s]+)\]\(https?://\1/?\)', r'\1', content)
    # Split by fenced code blocks so prose-only repairs never touch code inside fences
    parts = FENCE_SEGMENT_RE.split(content)
    for idx in range(0, len(parts), 2):
        seg = parts[idx]
        # 2. Repair inverted bold/inline-code closures using flat character classes (zero backtracking)
        seg = re.sub(r'`\*\*([^`*\n]+)`([^`*\n]+)\*\*`', r'`**\1`\2`**`', seg)
        seg = re.sub(r'\*\*([^*`\n]*`[^`*\n]+)\*\*`', r'**\1`**', seg)
        # 3. Collapse hard-wrapped newlines inside single-backticked player-piano cue examples
        seg = re.sub(
            r'(?<!`)`(\s*(?:<!--\s*(?:pp4|weebo|media)\b[^`]{1,200}?-->|\[{3}\s*(?:weebo|media|image|video|patronus)\s*:[^`\]]{1,200}?\]{3})\s*)`(?!`)',
            lambda m: '`' + ' '.join(m.group(1).split()) + '`' if '\n' in m.group(1) else m.group(0),
            seg,
            flags=re.IGNORECASE,
        )
        lines = seg.split('\n')
        for li, ln in enumerate(lines):
            new_ln, _ = _double_single_dollar_mathjax_line(ln)
            lines[li] = new_ln
        parts[idx] = '\n'.join(lines)
    return ''.join(parts)


def redact_ips(content: str) -> str:
    """Replace any non-safe IPv4 address with a redaction token (both lanes).

    IPs in the URL authority position (immediately after '://') get a
    bracket-free, hostname-safe token: urlparse treats '[' after '//' as an
    IPv6 literal and raises ValueError('Invalid IPv6 URL') on
    'http://[REDACTED_IP]/...', which detonates md2conf downstream in
    confluenceizer.py. Prose occurrences keep the visible bracketed token.
    """
    ip_core = (
        r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    )

    def make_replacer(token):
        def replacer(match):
            ip = match.group(0)
            return ip if ip in SAFE_IPS else token
        return replacer

    # Pass 1: URL host position -> hostname-safe token (no brackets)
    content = re.sub(rf'(?<=://){ip_core}\b', make_replacer("redacted-ip.invalid"), content)
    # Pass 2: everything else -> the visible bracketed token
    content = re.sub(rf'\b{ip_core}\b', make_replacer("[REDACTED_IP]"), content)
    return content


# THE FENCE CONTRACT (the non-arms-race, 2026-07-06): everything downstream
# -- Gemini subheading insertion, Jekyll, md2conf, TTS -- assumes well-formed
# fences. Instead of healing each parser's failure mode at the projection
# boundary, refuse malformed input at the intake chokepoint. Three rules:
#   1. A fence is recognized ONLY at column 0. Any run of 3+ backticks
#      anywhere else on a line is neutralized to a literal token; it was
#      never going to survive the transformation pipeline anyway.
#   2. Every opening fence must declare a language (bash, text, python...).
#      A naked opener SELF-HEALS to a text-tagged fence in place. The state
#      machine already classified it as an opener, so the repair was always
#      mechanical; refusing the run only made the human retype what the
#      machine already knew. The heal is written back to article.txt.
#   3. Every closing fence must be bare. A labeled fence encountered while
#      a fence is already open means a quoted fence or a missing closer.
# Rule 3 (and an unclosed fence at EOF) still fails CLOSED with line numbers
# (mechanical vim jumps); the && chain in write_post halts, so nothing
# genuinely ambiguous reaches articleizer.
FENCE_RUN_RE = re.compile(r'`{3,}')
NEUTRAL_FENCE_TKN = '[triple-backtick]'


def enforce_fence_contract(content: str) -> str:
    """Neutralize floating fences; heal naked openers; stop on asymmetry."""
    lines = content.split('\n')
    out = []
    problems = []
    in_fence = False
    open_line = 0
    open_tag = ""
    neutralized = 0
    healed = 0
    for i, line in enumerate(lines, 1):
        if '```' in line and not line.startswith('```'):
            line, n = FENCE_RUN_RE.subn(NEUTRAL_FENCE_TKN, line)
            neutralized += n
        if line.startswith('```'):
            if not in_fence:
                if line.strip() == '```':
                    # SELF-HEALING OPENER: this branch is reached only after
                    # the state machine has ALREADY classified the run as an
                    # opener, so the correct repair is fully determined --
                    # tag it text. rstrip() also eats trailing whitespace on
                    # the fence line, which no downstream parser wanted.
                    line = line.rstrip() + 'text'
                    healed += 1
                in_fence = True
                open_line = i
                open_tag = line.strip()
            else:
                if line.strip() != '```':
                    problems.append(
                        f"line {i} ({line.strip()}): labeled fence while fence from "
                        f"line {open_line} ({open_tag}) is still open "
                        f"(jump: vim +{open_line} {ARTICLE_FILE})"
                    )
                    # Stay in_fence from this new opener so one missing closer
                    # does not invert every subsequent fence in the file.
                    open_line = i
                    open_tag = line.strip()
                else:
                    in_fence = False
        out.append(line)
    if in_fence:
        problems.append(
            f"EOF: unclosed fence opened at line {open_line} ({open_tag}) "
            f"(jump: vim +{open_line} {ARTICLE_FILE})"
        )
    if neutralized:
        print(f"🧯 Neutralized {neutralized} floating backtick run(s) -> {NEUTRAL_FENCE_TKN}")
    if healed:
        print(f"🩹 Tagged {healed} naked opening fence(s) with 'text'.")
    if problems:
        print("💥 FENCE CONTRACT VIOLATIONS in article.txt -- refusing to proceed:")
        for p in problems:
            print(f"   • {p}")
        raise SystemExit(1)
    return '\n'.join(out)


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


# Inline player-piano markers for paragraph/phrase-level privacy -- the same
# [[[token]]] bracket dialect already used for SEARCH/REPLACE and TODO_SLUGS
# blocks elsewhere in this toolchain. The fence stripper above handles whole
# blocks; this handles a clause or paragraph mid-sentence without forcing a
# line break and without colliding with real code fences. `p` is shorthand
# for `private` -- either spelling works, but an opener must be closed by its
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
        print(f"⚠️  Found {len(stray)} unmatched [[[p]]]/[[[private]]] marker(s) -- check for a missing close tag.")
    return new_content, count


def load_pii_rules():
    """Load (pattern, replacement) tuples from pii_substitutions.txt, if present."""
    rules = []
    if PII_FILE.exists():
        for line in PII_FILE.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            if line.startswith('pub:'):
                line = line[4:]  # publish-lane-only marker; this IS the publish lane
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


def load_denylist():
    """Load regex patterns from the out-of-repo denylist, if present.

    Same file the commit airlock reads: one pattern per line, '#' comments
    and blanks ignored. A 'cs:' prefix makes that one pattern case-sensitive
    (for brand names that collide with common English words); everything
    else matches case-insensitively so prose capitalization can't sneak a
    name past the gate. Caveat: the git pre-commit hook will treat a 'cs:'
    line as a literal, never-matching pattern -- acceptable degradation,
    since this publish gate is the one that guards prose.
    """
    patterns = []
    if DENYLIST_FILE.exists():
        for line in DENYLIST_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('pub:'):
                line = line[4:].strip()  # publish-lane-only marker; this IS the publish lane
            if line.startswith('cs:'):
                patterns.append((line[3:], 0))
            else:
                patterns.append((line, re.IGNORECASE))
    return patterns


def enforce_denylist(content: str):
    """PUBLIC-LANE INTERLOCK: fail closed if a denylisted identifier survives.

    Runs after the substitution pass, so pii_substitutions.txt is the
    redaction layer and this is the proof it worked. Reports line numbers
    for mechanical vim jumps, then halts so nothing tainted reaches
    articleizer.py or a public repo.
    """
    problems = []
    lines = content.split('\n')
    for pattern, flags in load_denylist():
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            print(f"⚠️  Skipping bad denylist pattern {pattern!r}: {e}")
            continue
        hits = [i for i, line in enumerate(lines, 1) if rx.search(line)]
        if hits:
            shown = ', '.join(str(h) for h in hits[:8])
            more = f" (+{len(hits) - 8} more)" if len(hits) > 8 else ""
            problems.append(f"pattern {pattern!r}: line(s) {shown}{more}")
    if problems:
        print("🛑 PUBLISH BLOCKED: denylisted identifier(s) survive the scrub:")
        for p in problems:
            print(f"   • {p}")
        print(f"   Add a substitution to {PII_FILE} (pattern === replacement)")
        print("   or fix the source. No bypass flag exists in the publish lane.")
        raise SystemExit(1)


def sanitize_article(public: bool):
    """Read article.txt, scrub it for the chosen lane, and save back in place."""
    if not ARTICLE_FILE.exists():
        print(f"⚠️  {ARTICLE_FILE.name} not found.")
        return

    content = ARTICLE_FILE.read_text()
    original_content = content

    # --- BOTH LANES: strip prompt boundary + enforce fence contract first + inception artifacts + IPs ---
    content = strip_prompt_boundary(content)
    content = enforce_fence_contract(content)
    content = neutralize_inception_artifacts(content)
    content = redact_ips(content)

    if public:
        # --- PUBLIC LANE: drop private fences + scrub names to roles ---
        content, fence_count = strip_private_fences(content)
        content, inline_count = strip_private_inline(content)
        content, pii_count = apply_pii(content)
        if fence_count:
            print(f"🔒 Removed {fence_count} private fenced block(s) -- kept only at source.")
        if inline_count:
            print(f"🔒 Removed {inline_count} inline private span(s) -- kept only at source.")
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

    # PUBLISH TRAPDOOR: enforce AFTER the write so scrub progress persists
    # in article.txt even when blocked, but raise before the && chain in
    # write_post can reach articleizer.py. Private lane is untouched.
    if public:
        enforce_denylist(content)


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
    parser.add_argument(
        '--heal-mathjax', action='store_true',
        help="Batch-upgrade single-dollar $...$ MathJax spans to $$...$$ across the target _posts directory."
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Report how many posts/spans --heal-mathjax would update without writing to disk."
    )
    args = parser.parse_args()

    if args.heal_mathjax:
        posts_dir = common.get_target_path(args)
        heal_corpus_mathjax(posts_dir, dry_run=args.dry_run)
        return

    sanitize_article(public=resolve_lane(args))


if __name__ == "__main__":
    main()
