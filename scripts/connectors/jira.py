#!/usr/bin/env python3
# scripts/connectors/jira.py
"""
jira.py — Bring a Jira project, issue, or JQL search into context.

A Unix-philosophy gateway to the Jira Cloud API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/jira.py                 # LIST: projects you can see
  python scripts/connectors/jira.py ENG             # LIST: recently-updated issues in project ENG
  python scripts/connectors/jira.py ENG-123         # FETCH: full text of one issue (description + comments)
  python scripts/connectors/jira.py 'assignee = currentUser() ORDER BY updated DESC'  # SEARCH: raw JQL

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/jira.py
  ! python scripts/connectors/jira.py ENG
  ! python scripts/connectors/jira.py ENG-123

Disambiguation rule (checked in this order):
  - no argument                          -> LIST projects
  - matches PROJ-123 (KEY-<digits>)      -> FETCH one issue
  - matches a bare KEY (all caps/digits) -> LIST that project's issues
  - anything else (spaces, lowercase, =, ~) -> raw JQL SEARCH

Auth (basic_auth). The CONFLUENCE_* fallbacks below are a CONVENIENCE for the
common case where one Atlassian identity covers both products -- they are NOT
a guarantee that it does. Convicted 2026-07-23 by a live probe on this very
wallet: JIRA_URL was explicit, its host DIFFERED from the Confluence host, and
JIRA_TOKEN DIFFERED from CONFLUENCE_TOKEN. A green confluence row therefore
established nothing about this connector, and the older wording promised a
single shared Atlassian token -- a label lying at the moment of diagnosis:
  JIRA_URL     e.g. https://yourco.atlassian.net   (NO /wiki suffix).
               If unset, derived from CONFLUENCE_URL / CONFLUENCE_BASE_URL by
               stripping a trailing /wiki.
  JIRA_EMAIL   falls back to CONFLUENCE_EMAIL / CONFLUENCE_USER
  JIRA_TOKEN   falls back to CONFLUENCE_TOKEN   (secret — env or .env only)

Endpoint note (verified against Atlassian's current Cloud REST v3): the legacy
/rest/api/3/search was fully REMOVED. This connector uses the enhanced
/rest/api/3/search/jql (GET; jql + fields + maxResults; nextPageToken paging).
Because THE PROBE ECONOMY RULE bounds every call to one --max page, this
connector never needs to walk nextPageToken -- the bound IS the feature.

Output is capped by -n/--max (default 25) per THE PROBE ECONOMY RULE: stdout is
destined for compiled context payloads, so the bound is a feature.

COMPILE-LANE CAUTION: project keys, issue summaries, descriptions, and comments
are client identifiers and client content. Any `!` invocation bound for a cloud
chat window rides through the compile-lane sanitizer -- make sure
pii_substitutions.txt covers the relevant identifiers first. (For an
internal-Confluence-only lane, a disclosure profile that leaves names in place
is the intended path.)
"""

import os
import re
import sys
import argparse

import httpx

ISSUE_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+-\d+$')
PROJECT_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+$')


# ----------------------------------------------------------------------------
# Auth & transport
# ----------------------------------------------------------------------------
def get_env():
    base = os.getenv("JIRA_URL")
    if not base:
        conf = os.getenv("CONFLUENCE_URL") or os.getenv("CONFLUENCE_BASE_URL")
        if conf:
            # Confluence base carries a trailing /wiki; Jira's REST base does not.
            base = re.sub(r'/wiki/?$', '', conf.rstrip('/'))
    email = (os.getenv("JIRA_EMAIL")
             or os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER"))
    token = os.getenv("JIRA_TOKEN") or os.getenv("CONFLUENCE_TOKEN")
    missing = [name for name, val in [
        ("JIRA_URL (or CONFLUENCE_URL to derive)", base),
        ("JIRA_EMAIL (or CONFLUENCE_EMAIL)", email),
        ("JIRA_TOKEN (or CONFLUENCE_TOKEN)", token),
    ] if not val]
    if missing:
        sys.stderr.write(
            "Missing environment variable(s): " + ", ".join(missing) + "\n"
            "JIRA_URL example: https://yourco.atlassian.net  (no /wiki)\n"
            "The token is the SAME Atlassian API token confluence.py uses.\n"
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
# Atlassian Document Format (ADF) -> plain text
# ----------------------------------------------------------------------------
_ADF_BLOCK = {"paragraph", "heading", "blockquote", "codeBlock",
              "listItem", "tableRow", "bulletList", "orderedList", "table",
              "panel", "rule"}


def adf_to_text(node):
    """Flatten an Atlassian Document Format node (JSON) to readable text.

    Jira descriptions and comments arrive as ADF, not HTML -- a nested JSON
    doc model. This walks it depth-first, keeping paragraph/heading/list
    breaks; deliberately crude-but-honest (same posture as confluence.py's
    HTML strip)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(n) for n in node)
    if not isinstance(node, dict):
        return str(node)
    ntype = node.get("type", "")
    if ntype == "text":
        return node.get("text", "")
    if ntype == "hardBreak":
        return "\n"
    if ntype == "mention":
        return "@" + ((node.get("attrs", {}).get("text", "") or "").lstrip("@") or "user")
    if ntype == "emoji":
        return node.get("attrs", {}).get("text", "") or ""
    inner = adf_to_text(node.get("content", []))
    if ntype in _ADF_BLOCK:
        return inner + "\n"
    return inner


def clean_text(s):
    return re.sub(r'\n{3,}', '\n\n', s or '').strip()


def _name(obj):
    if isinstance(obj, dict):
        return obj.get("displayName") or obj.get("name") or obj.get("value") or "?"
    return "?"


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def list_projects(client, base, max_items):
    """LIST mode, no argument: every project visible to this account."""
    data = get_json(client, f"{base}/rest/api/3/project/search",
                    params={"maxResults": max_items,
                            "orderBy": "lastIssueUpdatedTime"})
    values = data.get("values", []) if isinstance(data, dict) else data
    print("# Jira projects visible to this account (key | name)\n")
    if not values:
        print("(no projects visible)")
        return
    for p in values[:max_items]:
        print(f"{p.get('key', '?')}  {p.get('name', '')}")
    print("\n# Next: python scripts/connectors/jira.py <PROJECTKEY>   (recent issues)")


def _search(client, base, jql, max_items):
    data = get_json(
        client, f"{base}/rest/api/3/search/jql",
        params={"jql": jql, "maxResults": max_items,
                "fields": "summary,status,issuetype,assignee,updated"})
    return data.get("issues", []) if isinstance(data, dict) else []


def list_project_issues(client, base, project_key, max_items):
    """LIST mode, bare KEY: recently-updated issues in one project."""
    jql = f'project = "{project_key}" ORDER BY updated DESC'
    issues = _search(client, base, jql, max_items)
    print(f"# Recent issues in project '{project_key}' (key | status | type | summary)\n")
    if not issues:
        print("(no issues found -- check the project key)")
        return
    for it in issues[:max_items]:
        f = it.get("fields", {})
        print(f"{it.get('key', '?')}  [{_name(f.get('status'))}]  "
              f"[{_name(f.get('issuetype'))}]  {f.get('summary', '')}")
    print("\n# Next: python scripts/connectors/jira.py <PROJ-123>   (full issue text)")


def search_issues(client, base, jql, max_items):
    """SEARCH mode: raw JQL."""
    issues = _search(client, base, jql, max_items)
    print(f"# Jira JQL search: {jql}  (key | status | summary)\n")
    if not issues:
        print("(no matches)")
        return
    for it in issues[:max_items]:
        f = it.get("fields", {})
        print(f"{it.get('key', '?')}  [{_name(f.get('status'))}]  {f.get('summary', '')}")
    print("\n# Next: python scripts/connectors/jira.py <PROJ-123>   (full issue text)")


def fetch_issue(client, base, issue_key):
    """FETCH mode: one issue's full text -- fields, description, comments."""
    data = get_json(
        client, f"{base}/rest/api/3/issue/{issue_key}",
        params={"fields": "summary,status,issuetype,priority,assignee,"
                          "reporter,created,updated,description,comment"})
    f = data.get("fields", {})
    summary = f.get("summary", "(no summary)")
    print(f'# Jira issue {issue_key} -- "{summary}"')
    print(f"# status: {_name(f.get('status'))} | type: {_name(f.get('issuetype'))} "
          f"| priority: {_name(f.get('priority'))}")
    print(f"# assignee: {_name(f.get('assignee'))} | reporter: {_name(f.get('reporter'))}")
    print(f"# created: {f.get('created', '?')} | updated: {f.get('updated', '?')}\n")

    print("## Description")
    print(clean_text(adf_to_text(f.get("description"))) or "(no description)")
    print()

    comment_block = f.get("comment", {}) or {}
    comments = comment_block.get("comments", []) if isinstance(comment_block, dict) else []
    print(f"## Comments ({len(comments)})\n")
    if not comments:
        print("(no comments)")
        return
    for c in comments:
        print(f"### [{c.get('created', '?')}] {_name(c.get('author'))}")
        print(clean_text(adf_to_text(c.get("body"))) or "(empty comment)")
        print("\n---\n")


# ----------------------------------------------------------------------------
# Health check (THE EXIT-CODE PROTOCOL: the exit code IS the whole answer)
# ----------------------------------------------------------------------------
def check():
    """SELECT 1 for the wallet board: exit 0 GREEN, exit 1 RED.

    This row exists because Jira is a SEPARATE product at a SEPARATE host and
    -- witnessed 2026-07-23 on a live wallet -- sometimes under a SEPARATE
    token. The CONFLUENCE_* fallbacks make sharing easy, never certain, so
    this check must not infer its own health from Confluence's. Gate 2 is one
    /rest/api/3/myself call, hard 15s timeout.
    """
    base = os.getenv("JIRA_URL")
    if not base:
        conf = os.getenv("CONFLUENCE_URL") or os.getenv("CONFLUENCE_BASE_URL")
        if conf:
            base = re.sub(r'/wiki/?$', '', conf.rstrip('/'))
    email = (os.getenv("JIRA_EMAIL")
             or os.getenv("CONFLUENCE_EMAIL") or os.getenv("CONFLUENCE_USER"))
    token = os.getenv("JIRA_TOKEN") or os.getenv("CONFLUENCE_TOKEN")
    missing = [n for n, v in [("JIRA_URL (or CONFLUENCE_URL)", base),
                              ("JIRA_EMAIL (or CONFLUENCE_EMAIL)", email),
                              ("JIRA_TOKEN (or CONFLUENCE_TOKEN)", token)] if not v]
    if missing:
        sys.stderr.write("jira RED gate1: unset " + ", ".join(missing) + "\n")
        return 1
    try:
        with httpx.Client(auth=(email, token), timeout=15.0,
                          headers={"Accept": "application/json"}) as client:
            resp = client.get(base.rstrip('/') + "/rest/api/3/myself")
    except httpx.HTTPError as e:
        sys.stderr.write(f"jira RED gate2: transport failure: {e}\n")
        return 1
    # 401 and 403 are DIFFERENT failures and must not share a sentence. 401 is
    # "not authenticated"; 403 is "authenticated, then forbidden". The old line
    # blamed a missing Jira license for a 401 without ever having established
    # that the token worked anywhere -- a verdict where only an observation was
    # in hand. Report the observation; offer causes as ordered candidates.
    if resp.status_code == 401:
        sys.stderr.write(
            "jira RED gate2: HTTP 401, not authenticated by this site. "
            "Candidates in order: wrong or expired API token; email and token "
            "belong to different accounts; JIRA_URL points at a site this "
            "token was not minted for. (A missing Jira LICENSE reads 403, not "
            "401 -- run confluence --check with the same token to split them.)\n")
        return 1
    if resp.status_code == 403:
        sys.stderr.write(
            "jira RED gate2: HTTP 403, authenticated but forbidden -- most "
            "likely this account holds no Jira license or product access, "
            "which a token valid for Confluence does not confer.\n")
        return 1
    if resp.status_code != 200:
        sys.stderr.write(f"jira RED gate2: HTTP {resp.status_code}\n")
        return 1
    try:
        who = resp.json()
    except ValueError:
        who = {}
    name = who.get("displayName") or who.get("emailAddress") or who.get("accountId")
    if not name:
        sys.stderr.write("jira RED gate2: authenticated but no identity returned\n")
        return 1
    print(f"jira GREEN {name}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Jira Cloud API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (list projects), a PROJECTKEY, an issue key (PROJ-123), or a JQL string."
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
            list_projects(client, base, args.max)
        else:
            arg = arg.strip()
            if ISSUE_KEY_RE.match(arg):
                fetch_issue(client, base, arg)
            elif PROJECT_KEY_RE.match(arg):
                list_project_issues(client, base, arg, args.max)
            else:
                search_issues(client, base, arg, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
