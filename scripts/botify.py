#!/usr/bin/env python3
# scripts/botify.py
"""
botify.py — A Unix-philosophy gateway to the Botify API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/botify.py                    # LIST: identity walk -> all your org/project slugs
  python scripts/botify.py org                # LIST: projects under that org slug
  python scripts/botify.py org/project        # LIST: analyses (crawl snapshots) for that project
  python scripts/botify.py '<BQL or JSON>'    # FETCH: run a query (needs org/project coordinates)

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/botify.py
  ! python scripts/botify.py my-org/my-project
  ! python scripts/botify.py 'SELECT url FROM crawl' --org my-org --project my-project

Disambiguation rule: an argument that starts with '{' or contains whitespace is
a query (FETCH mode); anything else is a slug path (LIST mode). No argument at
all triggers the identity walk.

Auth: BOTIFY_API_TOKEN via config.get_botify_token() (env var or project .env).
FETCH coordinates resolve from --org/--project flags, then BOTIFY_ORG /
BOTIFY_PROJECT environment variables.

Output is capped by --max (default 25) per THE PROBE ECONOMY RULE: stdout is
destined for compiled context payloads, so the bound is a feature.

COMPILE-LANE CAUTION: LIST output contains client org/project slugs. Any `!`
invocation bound for a cloud chat window rides through the compile-lane
sanitizer — make sure pii_substitutions.txt covers client identifiers first.
"""

import os
import sys
import json
import argparse
from pathlib import Path

import httpx

# Wire into the central config (same pattern as scripts/ai.py)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from config import get_botify_token

API_BASE = "https://api.botify.com/v1"


# ----------------------------------------------------------------------------
# Auth & transport
# ----------------------------------------------------------------------------
def make_client():
    token = get_botify_token()
    if not token:
        sys.stderr.write(
            "Missing BOTIFY_API_TOKEN.\n"
            "Set it in your environment or the project-root .env file\n"
            "(config.get_botify_token() checks both).\n"
        )
        sys.exit(1)
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    return httpx.Client(headers=headers, timeout=60.0)


def get_json(client, url, params=None):
    resp = client.get(url, params=params)
    if resp.status_code != 200:
        sys.stderr.write(f"HTTP {resp.status_code} for {url}\n{resp.text[:500]}\n")
        sys.exit(1)
    return resp.json()


# ----------------------------------------------------------------------------
# Defensive extraction (profile shape treated as unverified ground truth,
# same posture as imports/botify/true_schema_discoverer.py)
# ----------------------------------------------------------------------------
def extract_username(profile):
    candidates = [
        profile.get("username"),
        profile.get("data", {}).get("username") if isinstance(profile.get("data"), dict) else None,
        profile.get("user", {}).get("username") if isinstance(profile.get("user"), dict) else None,
        profile.get("login"),
    ]
    for c in candidates:
        if c:
            return c
    return None


def project_coordinates(project):
    """Best-effort (org, slug, name) from a project payload."""
    slug = project.get("slug", "?")
    name = project.get("name", "")
    org = (
        (project.get("user") or {}).get("login")
        or (project.get("organization") or {}).get("slug")
        or "?"
    )
    return org, slug, name


def follow_pages(client, url, max_items):
    """Drain a paginated Botify list endpoint, capped at max_items."""
    items = []
    while url and len(items) < max_items:
        data = get_json(client, url)
        items.extend(data.get("results", []))
        url = data.get("next")
    return items[:max_items]


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def list_identity(client, max_items):
    """LIST mode, no argument: whoami -> every accessible org/project slug."""
    profile = get_json(client, f"{API_BASE}/authentication/profile")
    username = extract_username(profile)
    if not username:
        sys.stderr.write("Could not locate 'username' in the profile payload.\n")
        sys.exit(1)
    print(f"# Botify projects visible to {username} (org/project | name)\n")
    projects = follow_pages(client, f"{API_BASE}/users/{username}/projects", max_items)
    if not projects:
        print("(no accessible projects)")
        return
    for p in projects:
        org, slug, name = project_coordinates(p)
        print(f"{org}/{slug}  {name}")
    print("\n# Next: python scripts/botify.py <org>/<project>   (list analyses)")


def list_org_projects(client, org, max_items):
    """LIST mode, single slug: projects under one org."""
    print(f"# Botify projects under '{org}' (org/project | name)\n")
    projects = follow_pages(client, f"{API_BASE}/projects/{org}", max_items)
    if not projects:
        print("(no projects found — check the org slug)")
        return
    for p in projects:
        _, slug, name = project_coordinates(p)
        print(f"{org}/{slug}  {name}")
    print("\n# Next: python scripts/botify.py " + org + "/<project>   (list analyses)")


def list_analyses(client, org, project, max_items):
    """LIST mode, org/project: crawl snapshots, newest first."""
    print(f"# Botify analyses for {org}/{project} (newest first)\n")
    analyses = follow_pages(client, f"{API_BASE}/analyses/{org}/{project}/light", max_items)
    if not analyses:
        print("(no analyses found)")
        return
    for a in analyses:
        slug = a.get("slug", "?")
        status = a.get("status", "")
        finished = a.get("date_finished") or a.get("date_created") or ""
        print(f"{slug}  {status}  {finished}")
    print(
        "\n# Next: python scripts/botify.py 'SELECT url FROM crawl' "
        f"--org {org} --project {project}"
    )


def run_query(client, raw_query, org, project, max_items):
    """FETCH mode: BQL string or full JSON payload against the query endpoint."""
    if not (org and project):
        sys.stderr.write(
            "FETCH mode needs coordinates: pass --org/--project or set\n"
            "BOTIFY_ORG / BOTIFY_PROJECT in your environment.\n"
        )
        sys.exit(1)

    stripped = raw_query.strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Argument looks like JSON but failed to parse: {e}\n")
            sys.exit(1)
        payload.setdefault("size", max_items)
    else:
        payload = {"query": stripped, "size": max_items}

    url = f"{API_BASE}/projects/{org}/{project}/query"
    resp = client.post(url, json=payload)
    if resp.status_code != 200:
        sys.stderr.write(f"HTTP {resp.status_code} for {url}\n{resp.text[:500]}\n")
        sys.exit(1)
    data = resp.json()
    results = data.get("results")
    if isinstance(results, list):
        results = results[:max_items]
        print(f"# Botify query results for {org}/{project} ({len(results)} row(s), cap {max_items})\n")
        print(json.dumps(results, indent=2, default=str))
    else:
        print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Botify API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (identity walk), 'org', 'org/project', or a BQL/JSON query string."
    )
    parser.add_argument('--org', default=os.getenv('BOTIFY_ORG'),
                        help='Org slug for FETCH mode (default: BOTIFY_ORG env).')
    parser.add_argument('--project', default=os.getenv('BOTIFY_PROJECT'),
                        help='Project slug for FETCH mode (default: BOTIFY_PROJECT env).')
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Output cap per THE PROBE ECONOMY RULE (default: 25).')
    args = parser.parse_args()

    client = make_client()
    try:
        arg = args.query
        if arg is None:
            list_identity(client, args.max)
        elif arg.strip().startswith('{') or any(ch.isspace() for ch in arg.strip()):
            run_query(client, arg, args.org, args.project, args.max)
        else:
            parts = [p for p in arg.strip('/').split('/') if p]
            if len(parts) == 1:
                list_org_projects(client, parts[0], args.max)
            elif len(parts) >= 2:
                list_analyses(client, parts[0], parts[1], args.max)
            else:
                list_identity(client, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
