#!/usr/bin/env python3
"""
scripts/articles/confluenceizer.py
The Idempotent Confluence Publishing Adapter.
Loads targets from blogs.json, extracts the Confluence metadata surface,
and sequences local Markdown posts into the wiki page tree.
"""

import sys
import re
import argparse
import os
import json
import base64
import subprocess
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path
import frontmatter
import common

def _sanitize_internal_pii(text: str) -> str:
    """Map pseudo-private client/colleague identities to roles out-of-band."""
    if not text:
        return text
    
    rules = []
    txt_file = Path.home() / ".config" / "pipulate" / "pii_substitutions.txt"
    if txt_file.exists():
        for line in txt_file.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if " === " in line:
                pattern, repl = line.split(" === ", 1)
                rules.append((pattern, repl))
                
    for pattern, replacement in rules:
        text = re.sub(pattern, replacement, text)
    return text


def _strip_front_matter(md_text: str) -> str:
    """Drop a leading --- ... --- YAML block and Liquid template tags if present; otherwise pass through."""
    lines = md_text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                md_text = "\n".join(lines[i + 1:])
                break
    # Strip Liquid safety wrappers — meaningful for Jekyll rendering, noise in Confluence
    md_text = re.sub(r'\{%-?\s*raw\s*-?%\}\s*\n?', '', md_text)
    md_text = re.sub(r'\{%-?\s*endraw\s*-?%\}\s*\n?', '', md_text)

    # Corporate journal transformation & dialogue cleanup
    md_text = md_text.replace("**Me**:", "**Mike Levin**:")
    md_text = md_text.replace("Curious Book Reader", "Curious Journal Reader")
    md_text = md_text.replace("## Book Analysis", "## Content Analysis")

    # Internal-wiki identity scrub (client + colleague names -> roles)
    md_text = _sanitize_internal_pii(md_text)

    # Defuse sanitizer artifacts that detonate md2conf's urlparse: a
    # '[REDACTED_IP]' token in the URL authority position ('http://[...')
    # parses as an invalid IPv6 literal and raises ValueError. Heals posts
    # published before sanitizer.py became URL-aware; idempotent by nature.
    md_text = md_text.replace("://[REDACTED_IP]", "://redacted-ip.invalid")

    # Prune public metadata blocks to prevent confusion in team wiki environments
    md_text = re.sub(r'### 🐦 X\.com Promo Tweet\n```text\n.*?\n```\n*', '', md_text, flags=re.DOTALL)
    md_text = re.sub(r'### Title Brainstorm\n.*?(?=\n### |\Z)', '', md_text, flags=re.DOTALL)

    return md_text

_VOID_HTML_TAG_RE = re.compile(
    r"<(area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)(\s[^<>]*?)?>",
    re.IGNORECASE,
)

def _normalize_void_html_tag(match: re.Match) -> str:
    """Rewrite browser-tolerated void HTML tags as XML-safe self-closing tags."""
    tag = match.group(1).lower()
    attrs = (match.group(2) or "").strip()
    attrs = re.sub(r"\s*/\s*$", "", attrs).strip()
    return f"<{tag}{' ' + attrs if attrs else ''} />"

# THE PROSE PSEUDO-TAG DEFUSAL (probe-convicted 2026-07-06, round two):
# webclip-captured dialogue arrives as single enormous prose lines that quote
# their own trigger strings, including bare mid-line ``` runs. Python-Markdown's
# backtick regex backtracks an unmatched triple-run into a SINGLE-backtick
# opener, re-pairing every subsequent code span in the line off-by-one; a
# backticked `<module>` then lands in prose as a live HTML tag, and lxml dies
# with 'Opening and ending tag mismatch: module and p'. Sanitizing individual
# strings is an arms race (the journal must quote its own bugs), so instead:
# segment each non-fenced line with the SAME pairing regex md2conf's markdown
# pass uses, and entity-escape any <tag> in the prose segments whose name is
# not a legitimate HTML element. Real code spans pass through verbatim; when
# pairing desyncs, we desync in lockstep, so our prose is exactly its prose.
# Idempotent: '&lt;module&gt;' contains no '<' for _RAW_TAG_RE to match.
_HTML_ELEMENTS = frozenset((
    "a abbr address area article aside audio b base bdi bdo blockquote body br "
    "button canvas caption cite code col colgroup data datalist dd del details "
    "dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2 "
    "h3 h4 h5 h6 head header hr html i iframe img input ins kbd label legend li "
    "link main map mark meta meter nav noscript object ol optgroup option output "
    "p param picture pre progress q rp rt ruby s samp script section select "
    "small source span strong style sub summary sup table tbody td template "
    "textarea tfoot th thead time title tr track u ul var video wbr"
).split())

# Python-Markdown's inline backtick span pairing, replicated for segmentation.
_BACKTICK_SPAN_RE = re.compile(r'(?<!\\)(`+)(.+?)(?<!`)\1(?!`)')

_RAW_TAG_RE = re.compile(r'</?([A-Za-z][\w.-]*)[^<>]*>')

def _escape_non_html_tags(segment: str) -> str:
    """Entity-escape pseudo-tags (<module>, <string>, <frozen runpy>) in prose.

    Leaves legitimate HTML elements and markdown autolinks/mail links intact.
    """
    def repl(m):
        whole = m.group(0)
        if '://' in whole or '@' in whole:
            return whole  # markdown autolink or email — not a tag
        if m.group(1).lower() in _HTML_ELEMENTS:
            return whole
        return whole.replace('<', '&lt;').replace('>', '&gt;')
    return _RAW_TAG_RE.sub(repl, segment)

def _defuse_prose_pseudo_tags(line: str) -> str:
    """Escape non-HTML tags only in the segments md2conf will treat as prose."""
    out, pos = [], 0
    for m in _BACKTICK_SPAN_RE.finditer(line):
        out.append(_escape_non_html_tags(line[pos:m.start()]))
        out.append(m.group(0))  # code span survives verbatim
        pos = m.end()
    out.append(_escape_non_html_tags(line[pos:]))
    return ''.join(out)

# THE ORPHANED LINK TAIL (probe-convicted 2026-07-06): webclip citation blocks
# paste as ONE markdown link spanning multiple paragraphs --
# '[![](favicon)' ... blank line ... title ... blank line ... 'www.site.com](url)'.
# Python-Markdown parses inline syntax per paragraph, so the opening '[' never
# reaches the tail; md2conf then linkifies the bare 'www.' domain and hands
# urlparse 'http://www.site.com](https://...' -- a ']' in the URL authority
# with no '[', which raises ValueError('Invalid IPv6 URL'). The repair: any
# non-fenced line whose prefix contains no brackets but continues '](url)' is
# an orphaned tail; promote it to a well-formed single-line link. Idempotent:
# a repaired line starts with '[', which the prefix class refuses to match.
# End-of-line anchor: true webclip tails end immediately after the ')'.
# Without it, prose sentences quoting '](http://...)' fragments in inline
# code get a stray '[' prepended (cosmetic, but this journal quotes such
# fragments constantly -- it documents its own bugs).
_ORPHAN_LINK_TAIL_RE = re.compile(r'^([^\[\]\n]+?)\]\((https?://[^)\s]+)\)\s*$')

def _normalize_markdown_for_md2conf(md_text: str) -> str:
    """Make mixed Markdown/raw-HTML safer for md2conf without touching fenced code."""
    out = []
    in_fence = False

    for line in md_text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        line = _ORPHAN_LINK_TAIL_RE.sub(r'[\1](\2)', line)
        line = _defuse_prose_pseudo_tags(line)
        out.append(_VOID_HTML_TAG_RE.sub(_normalize_void_html_tag, line))

    return "".join(out)

def markdown_to_storage(md_text: str) -> str:
    """Convert Markdown to Confluence storage XML using md2conf."""
    cleaned_md = _normalize_markdown_for_md2conf(_strip_front_matter(md_text))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "page.md"
        tmp_path.write_text(cleaned_md, encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "md2conf",
            "--local",
            "--ignore-invalid-url",
            "-d",
            _resolve_domain(),
            str(tmp_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as err:
            detail = (err.stderr or err.stdout or str(err)).strip()
            raise RuntimeError(f"md2conf local conversion failed: {detail}") from err

        csf_path = Path(tmpdir) / "page.csf"
        if not csf_path.exists():
            raise RuntimeError(f"md2conf did not create expected CSF output: {csf_path}")

        csf_content = csf_path.read_text(encoding="utf-8")
        csf_content = re.sub(
            r'<ac:structured-macro ac:name="info".*?</ac:structured-macro>',
            '',
            csf_content,
            flags=re.DOTALL,
        )
        return csf_content.strip()

def _resolve_domain() -> str:
    raw = os.getenv("CONFLUENCE_DOMAIN") or os.getenv("CONFLUENCE_URL") or "YOUR_INSTANCE.atlassian.net"
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.strip("/")

def _auth_header(email: str, api_token: str) -> str:
    auth_str = f"{email}:{api_token}"
    return "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

def _request(domain: str, email: str, api_token: str, path: str,
             method: str = "GET", payload: dict = None) -> dict:
    url = f"https://{domain}/wiki/api/v2{path}"
    data = None
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", _auth_header(email, api_token))
    req.add_header("Accept", "application/json")
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def _fetch_child_inventory(domain: str, email: str, api_token: str, parent_id: str) -> dict:
    """Recursively traverses Confluence v2 cursor pagination links to harvest
    all downstream children, returning a mapping of page titles to local metadata."""
    inventory = {}
    path = f"/pages/{parent_id}/children?limit=50"
    
    while path:
        # Strip v2 base path if echoed back inside response links
        if path.startswith("/wiki/api/v2"):
            path = path[12:]
            
        data = _request(domain, email, api_token, path)
        results = data.get("results", [])
        
        for page in results:
            title = page.get("title")
            version_obj = page.get("version") or {}
            inventory[title] = {
                "id": page.get("id"),
                "version": version_obj.get("number"),
                "status": page.get("status")
            }
                
        path = data.get("_links", {}).get("next")
    return inventory

def _metadata_value(metadata: dict, *keys):
    """Return the first present, non-empty front-matter value for any key."""
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return value
    return None

def _doc_date(md_file: Path, metadata: dict) -> str:
    """Prefer the Jekyll filename date, then fall back to front matter."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-", md_file.name)
    if match:
        return match.group(1)

    raw_date = _metadata_value(metadata, "date", "created", "published")
    if raw_date:
        return str(raw_date)[:10]

    return "0000-00-00"

def _fallback_title(md_file: Path) -> str:
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", md_file.stem)
    return stem.replace("-", " ").strip().title()

def _target_title(md_file: Path, post) -> str:
    """Compile the local Markdown file into the Confluence title contract."""
    metadata = post.metadata or {}
    title = _sanitize_internal_pii(_metadata_value(metadata, "title") or _fallback_title(md_file))
    sort_order = _metadata_value(metadata, "sort_order", "order", "sort", "ordinal")
    date_part = _doc_date(md_file, metadata)

    if sort_order is None:
        return f"{date_part} | {title}"
    return f"{date_part} ({sort_order}) | {title}"

def main():
    parser = argparse.ArgumentParser(description="Publish local markdown articles to Confluence Cloud.")
    common.add_standard_arguments(parser)
    parser.add_argument("--yes", action="store_true", help="Arm Confluence mutations. Without this, only print the dry-run contract.")
    parser.add_argument("--file", action="append", metavar="PATH",
                        help="Sync only the given file(s). Repeatable. Beats both --latest and the full sweep.")
    parser.add_argument("--latest", action="store_true",
                        help="Sync only the article articleizer.py most recently wrote for this target (from the marker). Errors if no marker exists.")
    args = parser.parse_args()

    targets = common.load_targets()
    target_key = str(args.target)

    if target_key not in targets:
        print(f"❌ Error: Target key '{target_key}' not found in blogs.json.")
        sys.exit(1)

    config = targets[target_key]
    print(f"🔒 Locked Target: {config.get('name')} ({config.get('path')})")

    parent_id = config.get("confluence_parent_id")
    if not parent_id:
        print(f"❌ Aborted: Target '{target_key}' does not define a 'confluence_parent_id' in blogs.json.")
        sys.exit(1)

    print(f"📡 Anchored Confluence Parent ID: {parent_id}")

    posts_dir = Path(config["path"]).expanduser().resolve()
    if not posts_dir.is_dir():
        print(f"❌ Error: Posts directory does not exist: {posts_dir}")
        sys.exit(1)

    # Selection precedence: explicit --file > --latest > full directory sweep.
    # The sweep stays the default so dry-runs (no --yes) and intentional global
    # re-syncs for template/pipeline changes keep working exactly as before.
    if args.file:
        md_files = []
        for raw in args.file:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = posts_dir / candidate
            candidate = candidate.resolve()
            if candidate.is_file():
                md_files.append(candidate)
            else:
                print(f"   ⚠ Skipping --file (not found): {candidate}")
        print(f"🎯 Explicit selection via --file: {len(md_files)} document(s).")
    elif args.latest:
        latest_path = common.get_last_published(target_key)
        if not latest_path:
            print(f"❌ --latest: no recorded publish for target '{target_key}'.")
            print("  ↳ Run 'bot' (articleizer.py) first, pass --file PATH, or drop --latest for a full sweep.")
            sys.exit(1)
        md_files = [Path(latest_path).resolve()]
        print(f"🎯 Latest-only selection (from marker): {md_files[0].name}")
    else:
        md_files = sorted(list(posts_dir.glob("*.md")))

    print(f"📝 Found {len(md_files)} candidate document(s) for publishing queue.")

    if not md_files:
        print("🛑 Queue empty. Nothing to parse.")
        return

    local_contracts = []
    print("\n🧾 Local Target Title Contract:")
    try:
        for md_file in md_files:
            post = frontmatter.load(md_file)
            target_title = _target_title(md_file, post)
            storage_xml = markdown_to_storage(post.content)
            local_contracts.append((md_file, target_title, storage_xml))
            print(f"   Target Title: {target_title}")
        print(f"✅ Local title contract pass complete. {len(local_contracts)} document(s) mapped.")
    except Exception as e:
        print(f"❌ Local title contract failure: {e}")
        sys.exit(1)

    # Handshake validation pass on the first document in the queue
    first_file = md_files[0]
    print(f"\n🔍 Handshake Verification Pass: Analyzing '{first_file.name}'...")
    
    try:
        post = frontmatter.load(first_file)
        print(f"  • Frontmatter Title: {post.metadata.get('title', 'None')}")
        print(f"  • Frontmatter Date:  {post.metadata.get('date', 'None')}")
        
        storage_xml = markdown_to_storage(post.content)
        print("\n--- Compiled Storage XML Representation Preview ---")
        print(storage_xml[:500] + ("..." if len(storage_xml) > 500 else ""))
        print("---------------------------------------------------")
        print("✅ Local conversion pass successful.")
    except Exception as e:
        print(f"❌ Structural load or compilation failure: {e}")
        sys.exit(1)

    # 4. Network Handshake Pass (The Minimal Falsifying Probe)
    domain = _resolve_domain()
    email = os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER")
    api_token = os.getenv("CONFLUENCE_TOKEN")

    if not email or not api_token:
        print("\n❌ Network Handshake Skipped: Missing authentication environment variables.")
        print("  ↳ Set CONFLUENCE_EMAIL and CONFLUENCE_TOKEN to test wire connectivity.")
        return

    print(f"\n📡 Connecting to Atlassian Network Boundary: https://{domain}...")
    try:
        parent_meta = _request(domain, email, api_token, f"/pages/{parent_id}?include-operations=true")
        space_id = parent_meta.get("spaceId")
        print(f"✅ Network Handshake Successful! Parent Title: '{parent_meta.get('title')}' [Space ID: {space_id}]")
        if not space_id:
            print("❌ Parent returned no spaceId; cannot place children. Aborting.")
            sys.exit(1)

        ops = []
        operations = parent_meta.get("operations") or {}
        if isinstance(operations, dict):
            ops = [o.get("operation") for o in operations.get("results", [])]
        elif isinstance(operations, list):
            ops = [o.get("operation") for o in operations]
        if ops:
            print(f"   operations: {', '.join(o for o in ops if o)}")
            if "create" not in ops and "update" not in ops:
                print("   ⚠ No 'create'/'update' in parent operations — write may 403.")
        else:
            print("   operations: (none reported; write will be the real permission test)")
        
        print(f"🔎 Scanning Remote Page Inventory under Parent ID {parent_id}...")
        inventory = _fetch_child_inventory(domain, email, api_token, parent_id)
        print(f"✅ Inventory Scan Complete. Found {len(inventory)} matching child page(s) on remote wiki.")
        for title, meta in inventory.items():
            print(f"   • [ID: {meta['id']}] {title} (Version: {meta['version']})")

        print("\n🧭 Remote Match Contract:")
        for md_file, target_title, storage_xml in local_contracts:
            meta = inventory.get(target_title)
            if meta:
                print(f"   MATCH: {md_file.name} -> [ID: {meta['id']}] {target_title}")
            else:
                print(f"   MISS:  {md_file.name} -> {target_title}")

        if not args.yes:
            print("\n🅳🆁🆈 DRY-RUN — no mutation. Review Target Title and MATCH/MISS lines before porting the proven upsert path.")
            print("  ↳ Next patch should lift create_canary's space-scoped collision check, private create, version bump, and read-back verification.")
            return

        print(f"\n✍️  Mutations armed (--yes). Upserting {len(local_contracts)} document(s) into the space...")
        created = updated = skipped = failed = 0
        inventory_ids = {str(v.get("id")) for v in inventory.values() if v.get("id")}

        for md_file, target_title, storage_xml in local_contracts:
            meta = inventory.get(target_title)
            try:
                if meta:
                    existing_id = meta["id"]
                    current = _request(domain, email, api_token, f"/pages/{existing_id}?include-version=true")
                    current_version = (current.get("version") or {}).get("number")
                    if current_version is None:
                        print(f"   ⚠ SKIP {target_title!r}: could not read existing version; refusing to guess the bump.")
                        skipped += 1
                        continue

                    verb = "UPDATE"
                    payload = {
                        "id": str(existing_id),
                        "status": "current",
                        "title": target_title,
                        "body": {"representation": "storage", "value": storage_xml},
                        "version": {"number": current_version + 1, "message": "Pipulate markdown upsert"},
                    }
                    result = _request(domain, email, api_token, f"/pages/{existing_id}", method="PUT", payload=payload)
                    new_id = result.get("id") or existing_id
                    expected_version = current_version + 1
                else:
                    collision_query = urllib.parse.urlencode({"title": target_title, "space-id": space_id, "limit": 5})
                    existing = _request(domain, email, api_token, f"/pages?{collision_query}")
                    hits = existing.get("results", [])
                    collision_ids = {str(hit.get("id")) for hit in hits if hit.get("id")}

                    if collision_ids and not collision_ids.intersection(inventory_ids):
                        print(f"   ⚠ SKIP {target_title!r}: exact title already exists elsewhere in space; refusing to create a duplicate-orphan.")
                        skipped += 1
                        continue
                    if collision_ids:
                        print(f"   ⚠ SKIP {target_title!r}: exact title collision exists but was not mapped by child inventory; inspect before mutating.")
                        skipped += 1
                        continue

                    verb = "CREATE"
                    payload = {
                        "spaceId": str(space_id),
                        "status": "current",
                        "title": target_title,
                        "parentId": str(parent_id),
                        "body": {"representation": "storage", "value": storage_xml},
                    }
                    result = _request(domain, email, api_token, "/pages", method="POST", payload=payload)
                    new_id = result.get("id")
                    expected_version = (result.get("version") or {}).get("number")
                    if not new_id:
                        print(f"   ❌ {target_title!r} failed: Confluence returned no page id after create.")
                        failed += 1
                        continue

                # Read-back round-trip: prove the write landed and the storage survived intact.
                readback = _request(domain, email, api_token, f"/pages/{new_id}?body-format=storage&include-version=true")
                rb_version = (readback.get("version") or {}).get("number")
                rb_title = readback.get("title")
                rb_value = ((readback.get("body") or {}).get("storage") or {}).get("value") or ""
                sentinel_match = re.search(r">([^<>]{20,}?)<", storage_xml)
                sentinel = sentinel_match.group(1) if sentinel_match else ""
                version_ok = expected_version is None or rb_version == expected_version
                title_ok = rb_title == target_title
                sentinel_ok = not sentinel or sentinel in rb_value
                round_trip_ok = bool(rb_value) and version_ok and title_ok and sentinel_ok

                flag = "✅" if round_trip_ok else "⚠"
                print(f"   {flag} {verb} [ID: {new_id}] v{rb_version} ({len(rb_value):,} chars) -> {target_title}")
                if not round_trip_ok:
                    print(f"      ⚠ Round-trip suspect (expected v{expected_version}; title ok: {title_ok}; storage {len(rb_value)} chars; sentinel survived: {sentinel_ok}). Inspect before trusting.")

                if verb == "CREATE":
                    created += 1
                else:
                    updated += 1
            except urllib.error.HTTPError as http_err:
                detail = ""
                try:
                    detail = http_err.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
                print(f"   ❌ {target_title!r} failed (HTTP {http_err.code} {http_err.reason}): {detail}")
                failed += 1
            except Exception as err:
                print(f"   ❌ {target_title!r} failed: {err}")
                failed += 1

        print(f"\n🏁 Upsert complete. Created: {created}  Updated: {updated}  Skipped: {skipped}  Failed: {failed}")
        return
    except Exception as e:
        print(f"❌ Network Boundary Handshake Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
