#!/usr/bin/env python3
# scripts/connectors/botify.py
"""
botify.py — Bring Botify crawl data and BQL query results into context.

A Unix-philosophy gateway to the Botify API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/botify.py                    # LIST: identity walk -> all your org/project slugs
  python scripts/connectors/botify.py org                # LIST: projects under that org slug
  python scripts/connectors/botify.py org/project        # LIST: analyses (crawl snapshots) for that project
  python scripts/connectors/botify.py '<BQL or JSON>'    # FETCH: run a query (needs org/project coordinates)

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/botify.py
  ! python scripts/connectors/botify.py my-org/my-project
  ! python scripts/connectors/botify.py 'SELECT url FROM crawl' --org my-org --project my-project

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

# Wire into the central config (same pattern as scripts/ai.py).
# NOTE: connectors/ is one level deeper than scripts/, hence three parents.
# The editable install also exposes `config`, but the explicit path keeps
# this file honest as a standalone, curl-able artifact.
project_root = Path(__file__).resolve().parent.parent.parent
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
    """Drain a Botify list endpoint, capped at max_items.

    Defensive against BOTH response shapes the API actually serves:
      - paginated envelope: {"results": [...], "next": url-or-null}
      - bare JSON array:    [...]   (e.g. /users/{username}/projects)
    The bare-array case has no pagination cursor, so take it and stop.
    """
    items = []
    while url and len(items) < max_items:
        data = get_json(client, url)
        if isinstance(data, list):
            items.extend(data)
            break
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
    print("\n# Next: python scripts/connectors/botify.py <org>/<project>   (list analyses)")


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


# ----------------------------------------------------------------------------
# Health check (THE EXIT-CODE PROTOCOL: the exit code IS the whole answer)
# ----------------------------------------------------------------------------
def check():
    """SELECT 1 for the `warm` scoreboard: exit 0 GREEN, exit 1 RED.

    Crosses BOTH gates of the 2026-07-20 two-gate earmark: gate 1 is
    "credential present", gate 2 is "credential accepted by the live API".
    A GREEN row therefore means end-to-end, never merely "a token exists".
    The stderr line names which gate failed. Never interactive, never opens
    a browser, hard-bounded timeout: a check that can block is a check that
    can hang the whole scoreboard.
    """
    token = get_botify_token()
    if not token:
        sys.stderr.write(
            "botify RED gate1: no BOTIFY_API_TOKEN in env or project .env\n")
        return 1
    try:
        with httpx.Client(
            headers={"Authorization": f"Token {token}",
                     "Content-Type": "application/json"},
            timeout=15.0,
        ) as client:
            resp = client.get(f"{API_BASE}/authentication/profile")
    except httpx.HTTPError as e:
        sys.stderr.write(f"botify RED gate2: transport failure: {e}\n")
        return 1
    if resp.status_code in (401, 403):
        sys.stderr.write(
            f"botify RED gate2: token rejected (HTTP {resp.status_code})\n")
        return 1
    if resp.status_code != 200:
        sys.stderr.write(f"botify RED gate2: HTTP {resp.status_code}\n")
        return 1
    try:
        username = extract_username(resp.json())
    except ValueError:
        username = None
    if not username:
        sys.stderr.write(
            "botify RED gate2: authenticated but no username in profile\n")
        return 1
    print(f"botify GREEN {username}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        # ONE SOURCE FOR THREE SURFACES (2026-08-30): the sources roster reads
        # this module's docstring by AST, tools/connector_tools.py installs it
        # as the registry tool's __doc__, and --help prints it here. A
        # description that differs by surface is a confound wearing help's
        # coat; RawDescriptionHelpFormatter keeps the example lines intact.
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

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
