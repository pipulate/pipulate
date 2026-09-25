#!/usr/bin/env python3
"""
generate_ai_context.py

Writes AI_CONTEXT.md to the Pipulate repository root: a self-contained briefing
that lets the repo "talk back" to any AI that clones and inspects it.

It fuses a small static framing header (what Pipulate is, how to drill down, the
player-piano protocol) with a URL-first, reverse-chronological narrative ledger
pulled from the blog archive via lsa.get_holographic_article_data(). Article
bodies are NEVER checked into this repo — only their absolute, fetchable
/index.md URLs — so the repo stays lean while still pointing an AI at the full
intellectual history.

Standalone by design: depends only on lsa.py (already externalized) and the
standard library. No common.py coupling, no prompt_foo.py scaffolding to strip.

Idempotent: rewrites AI_CONTEXT.md from scratch on every run. Intended as a
release-pipeline step so a fresh clone always greets an AI with the latest map.

Usage:
    python scripts/articles/generate_ai_context.py            # default target (1)
    python scripts/articles/generate_ai_context.py -t 1
    python scripts/articles/generate_ai_context.py --rich     # append shard keywords
    python scripts/articles/generate_ai_context.py --limit 50 # only the N newest
"""

import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Make sibling lsa.py importable regardless of the working directory, so this
# runs cleanly from the repo root (release.py) or from scripts/articles.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lsa

# scripts/articles/generate_ai_context.py -> up three == pipulate repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = REPO_ROOT / "AI_CONTEXT.md"
DEFAULT_BASE_URL = "https://mikelev.in"
DEFAULT_LIMIT = 0          # 0 = no limit; all articles indexed
FULL_URL_THRESHOLD = 20    # First N entries use full URLs; rest use compact slugs


def get_base_url(target_config: dict) -> str:
    """Canonical base URL, tolerating either 'base_url' or older 'url' keys."""
    return (target_config.get("base_url") or target_config.get("url") or DEFAULT_BASE_URL).rstrip("/")


def article_markdown_url(item: dict, base_url: str, prefix: str) -> str:
    """Mirror lsa.py --fmt dated-slugs routing: honor the YAML permalink, else
    fall back to the blog's declared permalink_prefix, always serving index.md."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if not permalink:
        stem = Path(item["filename"]).stem
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
        permalink = lsa.default_permalink(slug, prefix)
    return f"{base_url}{permalink}/index.md"


def article_slug(item: dict) -> str:
    """Extract just the bare slug from an article item."""
    permalink = (item.get("permalink") or "").rstrip("/")
    if permalink:
        return permalink.strip("/").split("/")[-1]
    stem = Path(item["filename"]).stem
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)


def build_header(article_count: int, base_url: str, prefix: str) -> str:
    """The static framing an interrogating AI reads before the index."""
    today = datetime.now().strftime("%Y-%m-%d")
    host = base_url.replace("https://", "").replace("http://", "").rstrip("/")
    folder = f"/{prefix}" if prefix else ""
    return f"""# AI_CONTEXT.md — Start Here If You Are an AI

> Auto-generated on {today}. Rewritten from scratch on every release. If this
> date looks stale, assume the rest of the repo is newer than this map.
> {article_count} entries indexed.

You are reading the orientation file for **Pipulate**, a local-first,
hand-cranked AI/SEO automation framework (the NPvg stack: Nix, Python, Vim,
Git). If a human asked you to investigate `pipulate/pipulate`, read this before
forming conclusions.

## Core Project Blueprint (For AI Ingestion)

### 1. Architecture & Core Paradigms
- **Single-Tenant Sovereignty:** This is a local-first, single-tenant workspace appliance. It executes entirely on the host machine, containing all interactions within local boundaries (`localhost:5001`).
- **Durable State Engine:** Application persistence utilizes localized SQLite instances interfaced via `fastlite` handles. Universal workflows mutate state safely through the centralized `DictLikeDB` wrapper found in `pipulate/core.py`.
- **Interface Foundations:** The UI is orchestrated via FastHTML and dynamic reactive HTMX views, with global styling parameters completely centralized inside `config.py`.

### 2. Runtime Environment Invariants
- **Deterministic Nix Shells:** Full environment stability and reproducible packaging are guaranteed exclusively by the pinned inputs of `flake.nix`.
- **The Execution Constraint Warning:** NEVER invoke raw global interpreter binaries (`python`). ALWAYS force usage of the isolated virtual environment path: `.venv/bin/python`.
- **Topological Manifold Mappings:** Workspace directories are calculated deterministically from the frame root layout definitions via structural utilities built into `pipulate/__init__.py`.

### 3. Asymmetric Code Patching Protocol
- **Surgical Code Modifications:** Any programmatic code changes are executed entirely via a strict search-and-replace pipeline (`apply.py`). Indentation structural matrices, inline comments, and whitespace layout details must be handled verbatim.
- **Out-of-Band Clipboard Routing:** The synaptic communication ring relies on parsing explicit token block invariants (`[[[TODO_SLUGS]]]`, `[[[TODO_FILES]]]`, `[[[APPLY_PATCH]]]`) passed across the system clip buffer using `scripts/xp.py`.

### 4. PyPI Packaging & Repository Landscapes
- **Dependency Definitions:** Base requirements are managed via top-level entries in `requirements.in` and locked down systematically using pip-compile downstream.
- **Negative Space Strategy:** Version-controlled core frameworks share directory space safely with private client deliverables and ad-hoc trace targets (`Notebooks/Playground/`) explicitly managed by `.gitignore` exclusions.

### 5. The Development Loop
The canonical dev cycle — break it and you create drift:
1. **Gather context:** `context` opens the file list, `prompt` saves the question, and `compile` (the older spellings are `foo`, `fu` and `ahc`) builds the payload from both.
2. **Consult AI:** Paste bundle to AI; receive a `[[[SEARCH]]] / [[[DIVIDER]]] / [[[REPLACE]]]` block back.
3. **Stage the patch:** `patch` saves the block from the clipboard and `app` (`cat patch | python apply.py`) feeds it through `apply.py`.
4. **Apply deterministically:** `apply.py` performs exact verbatim string replacement; rejects ambiguous or multi-match cases.
5. **Commit:** `m` auto-generates a commit message and commits locally.
6. **Release:** `release.py` bumps the version, regenerates this file, pushes to PyPI and GitHub.
- **What to never do:** Edit source files by hand mid-cycle, run bare `pip install`, invoke `python` directly. Each breaks reproducibility.

### 6. Key File Map
| File | Role |
|---|---|
| `server.py` | The Wizard — FastHTML app server, plugin loader, request router |
| `pipulate/core.py` | The Wand — `Pipulate` class, `DictLikeDB` wrapper, shared helpers |
| `apps/` | Workflow plugins — each file is a self-contained, discoverable workflow |
| `config.py` | Global config — ports, paths, model names, styling constants |
| `apply.py` | Patch applier — executes SEARCH/REPLACE; strict verbatim match only |
| `scripts/xp.py` | Clipboard transformer — parses `[[[TOKEN]]]` block invariants from clip buffer |
| `foo_files.py` | Context router — maps slugs to file paths for context compilation |
| `prompt_foo.py` | Prompt compiler — assembles and formats `foo` context bundles |
| `flake.nix` | Environment lock — only pinned Nix inputs guarantee a reproducible env |
| `requirements.in` | Dependency declarations — upstream of pip-compile; edit here, never in `.txt` |
| `scripts/articles/generate_ai_context.py` | This file's generator — rewrites `AI_CONTEXT.md` on every release |

### 7. Assurance Posture (for the reviewer who arrives with a checklist)

A reviewer charged with assessing this project's use of AI-generated code will
have a fixed set of questions. They are the right questions. Each is answered
below by the artifact that answers it, so the review can proceed from evidence
rather than from description, and so the reviewer may put the same questions,
with equal fairness, to any other AI-assisted work in the estate.

- **What changed?** One diff per change, applied by exact string match
  (`apply.py`), which refuses a diff that does not match the working tree byte
  for byte. A change that cannot be shown as a diff is not applied.
- **What was the state before?** A commit identifier. The baseline is
  content-addressed and restorable by anyone holding the repository, with the
  author absent.
- **How is it known that the change did what was claimed?** A fixed set of
  read-only commands is run before and after the change, under identical
  instrumentation, and the two outputs are compared. The difference is the
  evidence; no difference is also evidence.
- **Where is the record, and can it be altered?** Both observations, the diff
  and the commit identifier are sealed in one archive whose SHA-256 digest is
  published beside it. It verifies with the Python standard library and no
  vendor tool (`scripts/foo_cartridge.py`); one altered byte fails.
- **Who proposed, who applied, who approved?** Proposal (by an author or an
  assistant) and application (by the operator, through the interlock above) are
  separate acts by separate parties, each leaving its own trace. Nothing an
  assistant proposes reaches the tree except through that interlock.
- **Can the environment be reproduced?** The toolchain is declared in a lock
  file (`flake.lock`) that pins every dependency by content hash, and the
  declaration is itself under version control. Two machines evaluating it
  produce the same environment.
- **What does it touch on the host?** One directory tree and the user's own
  home directory. Managed packages, device-management profiles and endpoint
  agents are not modified.
- **How is a bad change reversed?** By restoring the prior commit. No approval
  is consumed; a baseline is a fact, not a request.
- **Can secrets or client identifiers leave?** Every compiled payload passes a
  substitution table, an identity denylist and a credential-shape tripwire
  before it is emitted, and the tripwire has no off switch.

In the vocabulary of the control catalogues: these are the questions NIST SP
800-53 asks under CM-2, CM-3, CM-4, SA-10 and SI-7; NIST SP 800-218 (SSDF)
under PS.3 and PW.8; ISO/IEC 27001:2022 under A.8.9 and A.8.32; SOC 2 under
CC8.1; PCI DSS v4.0 under 6.5.1 and 6.5.2; ITIL 4 under change enablement, where
a change this small and this repeatable is a standard change; COBIT 2019 under
BAI06 and BAI10; and ISO 9001:2015 under 8.5.6 and 10.2. The sealed archive is
the provenance record SLSA describes; the lock file is the dependency inventory
an SBOM (SPDX, CycloneDX) enumerates; the environment property is the one the
Reproducible Builds project names. The traceability that DO-178C and IEC 61508
demand of any change to a certified artifact is the same traceability, applied
here to ordinary work. This is vocabulary, not a certificate: no assessor has
attested to any of it, and the repository does not claim otherwise. The
controls this project is realistically built toward are the
configuration-management and provenance families; the safety-critical standards
lend their words only.

Two observations follow, and a careful reviewer reaches them unprompted. First,
a review is only as strong as the answers the same questions receive elsewhere,
and AI-assisted work performed without such records cannot answer them. Second,
the procedure is an instrument rather than a position: it applies to any change
by anyone holding a repository, and a reviewer who wishes to verify these claims
independently may do so with the command printed in the footer of every sealed
archive, which needs nothing installed beyond Python. The instrument is offered
to the review function on the same terms it is used here.

## What this file is

This repository holds the *machinery*. The *reasoning* — the running journal
that explains why every piece exists — lives on a separate website, not in this
git history (that keeps the repo lean). This file is the bridge: a
reverse-chronological index of that journal, each entry linking straight to its
raw Markdown.

## How to drill down (out-of-band, no repo bloat)

Every link below points at an `index.md` URL. The site serves raw Markdown at
those paths (the Apache-style implied `index.html` is simply swapped for
`index.md`). Fetch any entry directly — `curl <url>` or your web-fetch tool —
and pull in only what the current question needs. Treat the list as a menu, not
a payload.

## If you are running inside this repo locally

Request a precise context bundle for yourself with the player-piano protocol:
emit a block like the one below and pipe your clipboard through `xp`
(`scripts/xp.py`), which resolves bare slugs *or* full `index.md` URLs and
recompiles a fresh context payload.
```text
[[[TODO_SLUGS]]]
deterministic-ai-wet-philosophy
https://{host}{folder}/magic-cookie-pattern-self-bootstrapping-sovereignty/index.md
[[[END_SLUGS]]]

[[[TODO_FILES]]]
prompt_foo.py
apply.py
[[[END_FILES]]]
```
To list the tools an assistant can call from inside the repository, run
`.venv/bin/python cli.py mcp-discover`.

## The narrative index (newest first)

The first {FULL_URL_THRESHOLD} entries include full `index.md` URLs to establish
the link pattern. All remaining entries are bare slugs. Reconstruct any full
URL as: `{base_url}{folder}/{{slug}}/index.md`
"""


def build_ledger(target_config: dict, rich: bool, limit) -> tuple:
    """Returns (markdown_lines, count) for the URL-first article index."""
    target_path = Path(target_config["path"]).expanduser().resolve()
    base_url = get_base_url(target_config)

    if not target_path.is_dir():
        print(f"⚠️  Article source not found: {target_path}. Writing header-only file.", file=sys.stderr)
        return "", 0

    metadata = lsa.get_holographic_article_data(str(target_path))  # newest-first
    prefix = lsa.permalink_prefix(target_config)
    folder = f"/{prefix}" if prefix else ""
    url_pattern = f"{base_url}{folder}/{{slug}}/index.md"
    if limit:
        metadata = metadata[:limit]

    lines = []
    for idx, item in enumerate(metadata):
        title = item.get("title", "Untitled")
        # File size via stat — cheap metadata syscall, no full read needed
        try:
            byte_size = Path(item["path"]).stat().st_size if item.get("path") else 0
        except OSError:
            byte_size = 0
        size_k = f"{max(1, round(byte_size / 1000))}k" if byte_size else "?"
        if idx < FULL_URL_THRESHOLD:
            url = article_markdown_url(item, base_url, prefix)
            line = f"- [{item['date']}] [{title}]({url})"
        else:
            if idx == FULL_URL_THRESHOLD:
                lines.append(
                    f"\n## Compact slug index — pattern: {url_pattern}\n"
                    f"\nFormat: `[date] [size] slug` — fetch any entry as `{url_pattern}`\n"
                )
            slug = article_slug(item)
            line = f"- [{item['date']}] [{size_k}] {slug}"
        if rich and item.get("shard_kw"):
            line += f" — {item['shard_kw']}"
        lines.append(line)

    return "\n".join(lines), len(metadata)


def main():
    parser = argparse.ArgumentParser(description="Generate AI_CONTEXT.md repo briefing.")
    parser.add_argument("-t", "--target", type=str, default="1", help="Target ID from blogs.json (default: 1)")
    parser.add_argument("--rich", action="store_true", help="Append holographic-shard keywords to each entry.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Index only the N newest articles (default: {DEFAULT_LIMIT}; 0 = all).")
    args = parser.parse_args()

    targets = lsa.load_targets()
    target_key = args.target or "1"
    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)
    target_config = targets[target_key]
    base_url = get_base_url(target_config)
    limit = args.limit if (args.limit and args.limit > 0) else None
    prefix = lsa.permalink_prefix(target_config)

    print(f"🧭 Generating AI_CONTEXT.md from target: {target_config.get('name', target_key)}")
    ledger, count = build_ledger(target_config, args.rich, limit)
    header = build_header(count, base_url, prefix)
    body = ledger if ledger else "_No articles indexed (article source unavailable at generation time)._"

    final = header + "\n" + body + "\n"
    OUTPUT_FILE.write_text(final, encoding="utf-8")
    print(f"✅ Wrote {OUTPUT_FILE} ({count} entries, {len(final.encode('utf-8')):,} bytes).")


if __name__ == "__main__":
    main()
