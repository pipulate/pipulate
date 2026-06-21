#!/usr/bin/env python3
"""
scripts/confluence_probe.py
The Cheapest Falsifying Probe for the Atlassian Confluence REST API v2.

Validates the network path, basic auth token handshake, and prints
the titles of pages under a specified parent ID using cursor pagination.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from urllib.parse import urlparse


def _resolve_domain() -> str:
    """Accepts either a bare domain (CONFLUENCE_DOMAIN) or a full instance
    URL (CONFLUENCE_URL, the name already living in this repo's .env) and
    normalizes down to the bare hostname the v2 path-building below expects."""
    raw = os.getenv("CONFLUENCE_DOMAIN") or os.getenv("CONFLUENCE_URL") or "YOUR_INSTANCE.atlassian.net"
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.strip("/")


def probe_confluence(domain: str, email: str, api_token: str, parent_id: str):
    # Construct the modern v2 pages endpoint. The v2 spec doesn't expose a
    # server-side "children of this parent" filter on GET /pages, but every
    # Page object in the response carries its own parentId field, so we
    # filter client-side after the fetch instead of fighting the API surface.
    url = f"https://{domain}/wiki/api/v2/pages?limit=25"

    print(f"📡 Initiating handshake against: https://{domain}/wiki/api/v2/pages")

    auth_str = f"{email}:{api_token}"
    base64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {base64_auth}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            print(f"✅ Connection Established (HTTP {status_code})")

            raw_data = response.read().decode('utf-8')
            data = json.loads(raw_data)

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

    except urllib.error.HTTPError as e:
        print(f"❌ Handshake Aborted (HTTP {e.code}: {e.reason})", file=sys.stderr)
        if e.code == 401:
            print("  ↳ Check your API token and email credentials inside your local keychain configuration.", file=sys.stderr)
        elif e.code == 404:
            print("  ↳ Confirm your Cloud domain spelling. The v2 endpoint route may be obscured.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Network Failure: {e}", file=sys.stderr)
        return False


def main():
    # Defensive credentials airlock: read from environment to keep repo context lossless.
    # Accepts CONFLUENCE_EMAIL (preferred) or CONFLUENCE_USER (the name
    # already sitting in .env from the original drop-in) so the probe
    # doesn't fight the naming you already settled on.
    domain = _resolve_domain()
    email = os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER")
    api_token = os.getenv("CONFLUENCE_TOKEN")

    parent_id = sys.argv[1] if len(sys.argv) > 1 else "0"

    if not email or not api_token:
        print("❌ Error: Missing authentication surface variables.")
        print("   Set CONFLUENCE_EMAIL (or CONFLUENCE_USER) and CONFLUENCE_TOKEN in your shell environment before running.")
        sys.exit(1)

    success = probe_confluence(domain, email, api_token, parent_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
