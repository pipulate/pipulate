#!/usr/bin/env python3
# scripts/confluence.py
"""
confluence.py — Bring a Confluence space, page, or search hit into context.

A Unix-philosophy gateway to the Confluence API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/confluence.py                  # LIST: all spaces you can see
  python scripts/confluence.py SPACEKEY         # LIST: recently modified pages in that space
  python scripts/confluence.py 123456789        # FETCH: full page text by numeric page ID
  python scripts/confluence.py 'search words'   # SEARCH: CQL text search across pages

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/confluence.py
  ! python scripts/confluence.py ENG
  ! python scripts/confluence.py 123456789

Disambiguation rule: an all-digit argument is a page ID (FETCH); an argument
containing whitespace is a search (CQL text query); any other single token is
treated as a space key (LIST). No argument at all lists spaces.

Auth (same envs confluenceizer.py already uses):
  CONFLUENCE_BASE_URL   e.g. https://yourco.atlassian.net/wiki
  CONFLUENCE_EMAIL      (or CONFLUENCE_USER)
  CONFLUENCE_TOKEN      Atlassian API token

Output is capped by --max (default 25) per THE PROBE ECONOMY RULE: stdout is
destined for compiled context payloads, so the bound is a feature.

COMPILE-LANE CAUTION: space keys, page titles, and page bodies are client
identifiers and client content. Any `!` invocation bound for a cloud chat
window rides through the compile-lane sanitizer — make sure
pii_substitutions.txt covers the relevant identifiers first.
"""

import os
import re
import sys
import json
import argparse
import html as html_lib

import httpx


# ----------------------------------------------------------------------------
# Auth & transport
# ----------------------------------------------------------------------------
def get_env():
    # BOTH names, BASE_URL first. jira.py has accepted CONFLUENCE_URL since it
    # shipped; this file did not, so a fully-configured wallet read as unset.
    # Convicted 2026-07-23 by a FALSE RED on the live board: the credential was
    # never tested, the check simply asked for the wrong variable NAME.
    base = os.getenv("CONFLUENCE_BASE_URL") or os.getenv("CONFLUENCE_URL")
    email = os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER")
    token = os.getenv("CONFLUENCE_TOKEN")
    missing = [name for name, val in [
        ("CONFLUENCE_BASE_URL (or CONFLUENCE_URL)", base),
        ("CONFLUENCE_EMAIL (or CONFLUENCE_USER)", email),
        ("CONFLUENCE_TOKEN", token),
    ] if not val]
    if missing:
        sys.stderr.write(
            "Missing environment variable(s): " + ", ".join(missing) + "\n"
            "CONFLUENCE_BASE_URL example: https://yourco.atlassian.net/wiki\n"
            "These are the same envs confluenceizer.py uses.\n"
        )
        sys.exit(1)
    return base.rstrip('/'), email, token


def make_client():
    base, email, token = get_env()
    client = httpx.Client(auth=(email, token), timeout=60.0,
                          headers={"Accept": "application/json"})
    return client, base


def get_json(client, url, params=None):
    resp = client.get(url, params=params)
    if resp.status_code != 200:
        sys.stderr.write(f"HTTP {resp.status_code} for {url}\n{resp.text[:500]}\n")
        sys.exit(1)
    return resp.json()


# ----------------------------------------------------------------------------
# HTML -> text (same crude-but-honest strip gmail.py uses)
# ----------------------------------------------------------------------------
def strip_html(s):
    s = re.sub(r'(?is)<(script|style).*?</\1>', '', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|li|h[1-6]|tr)\s*>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_lib.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def list_spaces(client, base, max_items):
    """LIST mode, no argument: every space visible to this account."""
    data = get_json(client, f"{base}/rest/api/space",
                    params={"limit": max_items})
    results = data.get("results", []) if isinstance(data, dict) else data
    print(f"# Confluence spaces visible to this account (key | name)\n")
    if not results:
        print("(no spaces visible)")
        return
    for s in results[:max_items]:
        print(f"{s.get('key', '?')}  {s.get('name', '')}")
    print("\n# Next: python scripts/confluence.py <SPACEKEY>   (list recent pages)")


def list_space_pages(client, base, space_key, max_items):
    """LIST mode, single token: recently modified pages in one space."""
    cql = f'space="{space_key}" and type=page order by lastmodified desc'
    data = get_json(client, f"{base}/rest/api/content/search",
                    params={"cql": cql, "limit": max_items})
    results = data.get("results", []) if isinstance(data, dict) else data
    print(f"# Recent pages in space '{space_key}' (id | title)\n")
    if not results:
        print("(no pages found — check the space key)")
        return
    for p in results[:max_items]:
        print(f"{p.get('id', '?')}  {p.get('title', '')}")
    print("\n# Next: python scripts/confluence.py <page_id>   (fetch full page text)")


def fetch_page(client, base, page_id):
    """FETCH mode: one page's full body as stripped text."""
    data = get_json(client, f"{base}/rest/api/content/{page_id}",
                    params={"expand": "body.storage,version,space"})
    title = data.get("title", "(no title)")
    space = (data.get("space") or {}).get("key", "?")
    version = (data.get("version") or {}).get("number", "?")
    body_html = ((data.get("body") or {}).get("storage") or {}).get("value", "")
    print(f'# Confluence page {page_id} — "{title}"')
    print(f"# space: {space} | version: {version}\n")
    print(strip_html(body_html) or "(empty body)")


def search_pages(client, base, text, max_items):
    """SEARCH mode: CQL text search across pages."""
    safe = text.replace('"', '\\"')
    cql = f'type=page and text ~ "{safe}" order by lastmodified desc'
    data = get_json(client, f"{base}/rest/api/content/search",
                    params={"cql": cql, "limit": max_items})
    results = data.get("results", []) if isinstance(data, dict) else data
    print(f'# Confluence page search: "{text}" (id | title)\n')
    if not results:
        print("(no matches)")
        return
    for p in results[:max_items]:
        print(f"{p.get('id', '?')}  {p.get('title', '')}")
    print("\n# Next: python scripts/confluence.py <page_id>   (fetch full page text)")


# ----------------------------------------------------------------------------
# Health check (THE EXIT-CODE PROTOCOL: the exit code IS the whole answer)
# ----------------------------------------------------------------------------
def check():
    """SELECT 1 for the wallet board: exit 0 GREEN, exit 1 RED.

    Reads the environment directly rather than calling get_env(), because
    get_env() exits with a generic message; the board needs the gate NAMED.
    Gate 1 is "the three vars are set", gate 2 is "Atlassian accepts them
    right now" -- one /rest/api/user/current call, hard 15s timeout.
    """
    base = os.getenv("CONFLUENCE_BASE_URL")
    email = os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER")
    token = os.getenv("CONFLUENCE_TOKEN")
    missing = [n for n, v in [("CONFLUENCE_BASE_URL", base),
                              ("CONFLUENCE_EMAIL", email),
                              ("CONFLUENCE_TOKEN", token)] if not v]
    if missing:
        sys.stderr.write("confluence RED gate1: unset " + ", ".join(missing) + "\n")
        return 1
    try:
        with httpx.Client(auth=(email, token), timeout=15.0,
                          headers={"Accept": "application/json"}) as client:
            resp = client.get(base.rstrip('/') + "/rest/api/user/current")
    except httpx.HTTPError as e:
        sys.stderr.write(f"confluence RED gate2: transport failure: {e}\n")
        return 1
    if resp.status_code in (401, 403):
        sys.stderr.write(
            f"confluence RED gate2: credentials rejected (HTTP {resp.status_code})\n")
        return 1
    if resp.status_code != 200:
        sys.stderr.write(f"confluence RED gate2: HTTP {resp.status_code}\n")
        return 1
    try:
        who = resp.json()
    except ValueError:
        who = {}
    name = who.get("displayName") or who.get("email") or who.get("accountId")
    if not name:
        sys.stderr.write("confluence RED gate2: authenticated but no identity returned\n")
        return 1
    print(f"confluence GREEN {name}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Confluence API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (list spaces), SPACEKEY, numeric page ID, or 'search words'."
    )
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Output cap per THE PROBE ECONOMY RULE (default: 25).')
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

    client, base = make_client()
    try:
        arg = args.query
        if arg is None:
            list_spaces(client, base, args.max)
        elif arg.strip().isdigit():
            fetch_page(client, base, arg.strip())
        elif any(ch.isspace() for ch in arg.strip()):
            search_pages(client, base, arg.strip(), args.max)
        else:
            list_space_pages(client, base, arg.strip(), args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
