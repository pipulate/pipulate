#!/usr/bin/env python3
"""
scripts/confluence_probe.py
The Cheapest Falsifying Probe for the Atlassian Confluence REST API v2.

Three non-overlapping modes, each a progressively more dangerous falsifying shot:

  (default)        List pages; optional --parent filters client-side by parentId.
  --read PAGE_ID   Read-shape probe: prove id/spaceId/parentId/version/storage.
  --create-canary  Preflight a parent, collision-check a canary title, and
                   (only with --yes) create one disposable private child page,
                   then read it back to prove the storage round-trip survived.

Anti-Crichton posture: --create-canary is DRY-RUN unless --yes is passed.
The dangerous seam tested is code-block escaping, not plain paragraphs.
"""

import os
import re
import sys
import html
import json
import base64
import argparse
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse


CANARY_TITLE = "DELETE_ME_Pipulate_Confluence_API_Canary"

# The smallest body that exercises the part most likely to break: a code macro.
# Plain <p> always survives; CDATA-wrapped code is where storage-format
# escaping bugs show up first.
CANARY_BODY = (
    "<p>Pipulate Confluence API canary.</p>"
    "<ac:structured-macro ac:name=\"code\">"
    "<ac:plain-text-body><![CDATA[print(\"hello confluence\")]]></ac:plain-text-body>"
    "</ac:structured-macro>"
)

# The substring we expect to survive the create -> read-back round trip intact.
CANARY_CODE_SENTINEL = 'print("hello confluence")'


# ---------------------------------------------------------------------------
# Markdown -> Confluence storage-format converter (deliberately narrow).
# The dangerous seam — fenced code blocks — reuses the EXACT ac:structured-macro
# CDATA shape that create_canary already round-tripped intact, so this adds no
# new network assumption. Only the local parse/escape logic is unproven, and
# --convert falsifies that with zero network and zero mutation.
# ---------------------------------------------------------------------------

def _strip_front_matter(md_text: str) -> str:
    """Drop a leading --- ... --- YAML block if present; otherwise pass through."""
    lines = md_text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return md_text


def _inline(text: str) -> str:
    """Escape HTML metacharacters first, then layer the two inline forms we support."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def markdown_to_storage(md_text: str) -> str:
    """Convert a narrow subset of Markdown to Confluence storage XML.

    Supported: ATX headings (# .. ######), blank-line-delimited paragraphs,
    **bold**, `inline code`, and fenced ``` code blocks. Tables, images, and
    nested lists are intentionally out of scope — they are the swamp, and the
    contract proves out without them.
    """
    lines = _strip_front_matter(md_text).split("\n")
    out = []
    para = []

    def flush_para():
        if para:
            joined = " ".join(s.strip() for s in para).strip()
            if joined:
                out.append(f"<p>{_inline(joined)}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("```"):
            flush_para()
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume the closing fence
            code = "\n".join(code_lines)
            # The only thing CDATA cannot contain verbatim is the terminator.
            code = code.replace("]]>", "]]]]><![CDATA[>")
            out.append(
                '<ac:structured-macro ac:name="code">'
                "<ac:plain-text-body><![CDATA[" + code + "]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_para()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            i += 1
            continue

        if not stripped:
            flush_para()
            i += 1
            continue

        para.append(lines[i])
        i += 1

    flush_para()
    return "".join(out)


def _resolve_domain() -> str:
    """Accepts either a bare domain (CONFLUENCE_DOMAIN) or a full instance
    URL (CONFLUENCE_URL, the name already living in this repo's .env) and
    normalizes down to the bare hostname the v2 path-building below expects."""
    raw = os.getenv("CONFLUENCE_DOMAIN") or os.getenv("CONFLUENCE_URL") or "YOUR_INSTANCE.atlassian.net"
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.strip("/")


def _auth_header(email: str, api_token: str) -> str:
    auth_str = f"{email}:{api_token}"
    return "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")


def _request(domain: str, email: str, api_token: str, path: str,
             method: str = "GET", payload: dict = None) -> dict:
    """Single chokepoint for v2 calls. Raises urllib.error.HTTPError upward so
    callers can print the server's JSON error body verbatim."""
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


def _print_http_error(e: "urllib.error.HTTPError"):
    print(f"❌ Handshake Aborted (HTTP {e.code}: {e.reason})", file=sys.stderr)
    if e.code == 401:
        print("  ↳ Check your API token and email. v2 endpoints may require a scoped token.", file=sys.stderr)
    elif e.code == 403:
        print("  ↳ Authenticated but not permitted. The credential lacks write capability on this parent/space.", file=sys.stderr)
    elif e.code == 404:
        print("  ↳ Confirm the Cloud domain and the page/parent ID exist and are visible to this user.", file=sys.stderr)
    try:
        body = e.read().decode("utf-8", errors="replace")
        if body:
            print(f"  ↳ Server said: {body}", file=sys.stderr)
    except Exception:
        pass


def list_pages(domain, email, api_token, parent_id=None) -> bool:
    print(f"📡 Initiating handshake against: https://{domain}/wiki/api/v2/pages")
    try:
        data = _request(domain, email, api_token, "/pages?limit=25")
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure: {e}", file=sys.stderr)
        return False

    print("✅ Connection Established (HTTP 200)")
    results = data.get("results", [])
    if parent_id and parent_id != "0":
        scoped = [p for p in results if p.get("parentId") == parent_id]
        print(f"\n--- Confluence Page Inventory (parentId={parent_id}, {len(scoped)} of {len(results)} fetched match) ---")
        results = scoped
    else:
        print(f"\n--- Confluence Page Inventory (Found {len(results)} items, no parent filter applied) ---")

    print(f"{'Page ID':15} | {'Page Title'}")
    print("-" * 60)
    for page in results:
        print(f"{page.get('id'):15} | {page.get('title')}")

    next_link = data.get("_links", {}).get("next")
    if next_link:
        print(f"\n🔄 Cursor token detected. Next page handle available ({next_link}).")
    else:
        print(f"\n🛑 End of paginated stream. No further cursors found.")
    return True


def read_page(domain, email, api_token, page_id) -> bool:
    query = urllib.parse.urlencode({"body-format": "storage", "include-version": "true"})
    print(f"📡 Reading page shape: https://{domain}/wiki/api/v2/pages/{page_id}?{query}")
    try:
        data = _request(domain, email, api_token, f"/pages/{page_id}?{query}")
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure: {e}", file=sys.stderr)
        return False

    body = data.get("body") or {}
    version = data.get("version") or {}
    storage = body.get("storage") or {}
    value = storage.get("value") or ""

    print("✅ Page read-shape probe passed")
    print(f"id:        {data.get('id')}")
    print(f"title:     {data.get('title')}")
    print(f"status:    {data.get('status')}")
    print(f"spaceId:   {data.get('spaceId')}")
    print(f"parentId:  {data.get('parentId')}")
    print(f"version:   {version.get('number')}")
    print(f"body keys: {list(body.keys())}")
    print(f"storage representation present: {'yes' if storage else 'no'}")
    print(f"storage chars: {len(value)}")
    return True


def create_canary(domain, email, api_token, parent_id, do_write) -> bool:
    # --- Preflight 1: read the parent to harvest spaceId and sniff permissions. ---
    print(f"🔎 Preflight: reading parent {parent_id} (with operations)...")
    try:
        parent = _request(
            domain, email, api_token,
            f"/pages/{parent_id}?include-operations=true"
        )
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure reading parent: {e}", file=sys.stderr)
        return False

    space_id = parent.get("spaceId")
    print(f"   parent title:  {parent.get('title')}")
    print(f"   parent spaceId: {space_id}")
    if not space_id:
        print("❌ Parent returned no spaceId; cannot place a child. Aborting.", file=sys.stderr)
        return False

    # Permission sniff: look for a create/update operation in the operations list.
    ops = []
    operations = parent.get("operations") or {}
    if isinstance(operations, dict):
        ops = [o.get("operation") for o in operations.get("results", [])]
    elif isinstance(operations, list):
        ops = [o.get("operation") for o in operations]
    if ops:
        print(f"   operations:    {', '.join(o for o in ops if o)}")
        if "create" not in ops and "update" not in ops:
            print("   ⚠ No 'create'/'update' in parent operations — write may 403.")
    else:
        print("   operations:    (none reported; create will be the real test)")

    # --- Preflight 2: collision check the canary title within the space. ---
    print(f"🔎 Preflight: checking for existing '{CANARY_TITLE}' in space {space_id}...")
    collision_query = urllib.parse.urlencode({"title": CANARY_TITLE, "space-id": space_id, "limit": 5})
    try:
        existing = _request(domain, email, api_token, f"/pages?{collision_query}")
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure during collision check: {e}", file=sys.stderr)
        return False

    # --- The ON CONFLICT branch: collision becomes an UPDATE, not a dead end. ---
    # Confluence v2 has no native upsert, so we synthesize it: a title hit routes
    # to PUT /pages/{id} (bumping version + restoring status), a miss routes to
    # POST /pages. This keeps re-runs idempotent instead of stacking canaries.
    hits = existing.get("results", [])
    existing_id = None
    existing_version = None
    if hits:
        existing_id = hits[0].get("id")
        print(f"   ↻ Canary title already exists (id={existing_id}); upsert will UPDATE it in place.")
        # Read its current version + status so the PUT can bump the version and,
        # if the page was archived, request status=current to restore it.
        try:
            current = _request(
                domain, email, api_token,
                f"/pages/{existing_id}?include-version=true"
            )
        except urllib.error.HTTPError as e:
            _print_http_error(e)
            return False
        except Exception as e:
            print(f"❌ Network Failure reading existing canary: {e}", file=sys.stderr)
            return False
        existing_version = (current.get("version") or {}).get("number")
        print(f"   existing status:  {current.get('status')}")
        print(f"   existing version: {existing_version}")
        if existing_version is None:
            print("❌ Could not read existing version number; cannot bump. Aborting.", file=sys.stderr)
            return False
    else:
        print("   ✅ No collision. Title is free; upsert will CREATE.")

    # --- The mutation gate. ---
    if existing_id:
        verb = "UPDATE"
        method = "PUT"
        path = f"/pages/{existing_id}"
        payload = {
            "id": str(existing_id),
            "status": "current",
            "title": CANARY_TITLE,
            "body": {"representation": "storage", "value": CANARY_BODY},
            "version": {"number": existing_version + 1, "message": "Pipulate canary upsert"},
        }
    else:
        verb = "CREATE"
        method = "POST"
        path = "/pages?private=true"
        payload = {
            "spaceId": str(space_id),
            "status": "current",
            "title": CANARY_TITLE,
            "parentId": str(parent_id),
            "body": {"representation": "storage", "value": CANARY_BODY},
        }

    if not do_write:
        print(f"\n🅳🆁🆈 DRY-RUN — no mutation. Would {method} {path} ({verb}) with:")
        print(json.dumps(payload, indent=2))
        print("\nRe-run with --yes to actually perform the upsert.")
        return True

    print(f"\n✍️  {verb}: {method} {path} ...")
    try:
        result = _request(domain, email, api_token, path, method=method, payload=payload)
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure during {verb.lower()}: {e}", file=sys.stderr)
        return False

    new_id = result.get("id") or existing_id
    print(f"✅ Canary {verb.lower()}d. id={new_id}  title={result.get('title')}")

    # --- The whole point: read it back and confirm the code block survived. ---
    print("🔁 Reading canary back to verify storage round-trip...")
    try:
        readback = _request(
            domain, email, api_token,
            f"/pages/{new_id}?body-format=storage"
        )
    except urllib.error.HTTPError as e:
        _print_http_error(e)
        return False
    except Exception as e:
        print(f"❌ Network Failure during read-back: {e}", file=sys.stderr)
        return False

    value = ((readback.get("body") or {}).get("storage") or {}).get("value") or ""
    if CANARY_CODE_SENTINEL in value:
        print(f"✅ ROUND-TRIP CLEAN: code sentinel {CANARY_CODE_SENTINEL!r} survived intact.")
        print("   The adapter is real, not leaky. Safe to build the Markdown pipeline next.")
    else:
        print(f"⚠ ROUND-TRIP LEAK: sentinel {CANARY_CODE_SENTINEL!r} not found verbatim in read-back.")
        print("   Storage-format escaping mangled the code block — fix the adapter before the pipeline.")
        print(f"   Returned storage (first 400 chars):\n{value[:400]}")

    print(f"\n🧹 Cleanup: delete this canary when done →")
    print(f"   curl -u \"$CONFLUENCE_USER:$CONFLUENCE_TOKEN\" -X DELETE "
          f"\"https://{domain}/wiki/api/v2/pages/{new_id}\"")
    return True


def main():
    parser = argparse.ArgumentParser(description="Cheapest falsifying probe for Confluence Cloud REST API v2.")
    parser.add_argument("--read", metavar="PAGE_ID", help="Read-shape probe: dump id/spaceId/parentId/version/storage for one page.")
    parser.add_argument("--parent", metavar="PAGE_ID", help="Parent page ID. Filters the listing; required for --create-canary.")
    parser.add_argument("--create-canary", action="store_true", help="Preflight + collision-check, then create a disposable private child (dry-run unless --yes).")
    parser.add_argument("--yes", action="store_true", help="Arm the mutation. Without it, --create-canary is dry-run only.")
    parser.add_argument("--convert", metavar="PATH", help="No-network probe: read a Markdown file, strip front matter, convert to storage format, print it. No auth, no mutation.")
    args = parser.parse_args()

    # No-network probe gate: the converter is a pure function, so it runs
    # before the auth check. It falsifies the parse/escape logic locally
    # without ever touching the API or arming a mutation.
    if args.convert:
        try:
            with open(args.convert, "r", encoding="utf-8") as f:
                md_text = f.read()
        except OSError as e:
            print(f"❌ Could not read {args.convert}: {e}", file=sys.stderr)
            sys.exit(1)
        storage = markdown_to_storage(md_text)
        print(storage)
        # Disposable fixture-coupled assertions: prove the three sentinels and
        # the proven code macro survive the local transform.
        print("\n--- Sentinel Survival Check (local, no network) ---", file=sys.stderr)
        for sentinel in ("Heading Sentinel", "Paragraph sentinel", 'print("hello confluence markdown")'):
            mark = "✅" if sentinel in storage else "❌"
            print(f"  {mark} {sentinel!r}", file=sys.stderr)
        in_macro = "<![CDATA[" in storage and 'ac:name="code"' in storage
        print(f"  {'✅' if in_macro else '❌'} code block wrapped in proven CDATA macro", file=sys.stderr)
        sys.exit(0)

    domain = _resolve_domain()
    email = os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER")
    api_token = os.getenv("CONFLUENCE_TOKEN")

    if not email or not api_token:
        print("❌ Error: Missing authentication surface variables.")
        print("   Set CONFLUENCE_EMAIL (or CONFLUENCE_USER) and CONFLUENCE_TOKEN in your shell environment before running.")
        sys.exit(1)

    if args.create_canary:
        if not args.parent:
            print("❌ --create-canary requires --parent PAGE_ID (the page to hang the canary under).")
            sys.exit(1)
        ok = create_canary(domain, email, api_token, args.parent, do_write=args.yes)
    elif args.read:
        ok = read_page(domain, email, api_token, args.read)
    else:
        ok = list_pages(domain, email, api_token, parent_id=args.parent)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
