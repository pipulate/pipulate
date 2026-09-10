#!/usr/bin/env python3
# scripts/connectors/jira.py
"""
jira.py — List your open Jira tickets, or fetch one by key.

A Unix-philosophy gateway to the Jira Cloud API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/jira.py                 # MINE: open issues assigned to you (the For You tab)
  python scripts/connectors/jira.py projects        # LIST: projects you can see
  python scripts/connectors/jira.py ENG             # LIST: recently-updated issues in project ENG
  python scripts/connectors/jira.py ENG-123         # FETCH: full text of one issue (custom fields + description + comments)
  python scripts/connectors/jira.py 'assignee = currentUser() ORDER BY updated DESC'  # SEARCH: raw JQL

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/jira.py
  ! python scripts/connectors/jira.py ENG
  ! python scripts/connectors/jira.py ENG-123

Disambiguation rule (checked in this order):
  - no argument                          -> MINE: open issues assigned to you
  - any /jira/for-you URL               -> MINE, the same answer
  - the word projects                    -> LIST projects
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
               THE BASE URL IS A FUNCTION OF THE CREDENTIAL, NOT OF THE SITE.
               A CLASSIC (unscoped) API token authenticates basic-auth against
               the site host above. A SCOPED API token -- the kind Atlassian's
               own token page now steers you toward, and the ONLY kind a
               service account can mint -- authenticates ONLY through the
               platform gateway at api.atlassian.com/ex/jira/<cloudId>/, and
               answers 401 at the site host forever, no matter who grants what.
               An OAuth 2.0 (3LO) access token rides that same gateway with a
               Bearer header. This connector speaks ROW ONE ONLY (2026-07-23).
  JIRA_EMAIL   falls back to CONFLUENCE_EMAIL / CONFLUENCE_USER
  JIRA_TOKEN   falls back to CONFLUENCE_TOKEN   (secret — env or .env only)
  JIRA_CLOUD_ID  OPTIONAL, and it is the DOOR SELECTOR. Set it (the site's
               cloudId UUID; an identifier, not a secret) and EVERY call
               routes through the gateway, which is what a SCOPED token
               requires. Leave it unset and calls go to the site host, which
               is what a CLASSIC token requires. Declare it to match the
               token you actually hold: the wrong setting is 401 forever,
               and 401 is the same answer a stranger with no account gets.

Endpoint note (verified against Atlassian's current Cloud REST v3): the legacy
/rest/api/3/search was fully REMOVED. This connector uses the enhanced
/rest/api/3/search/jql (GET; jql + fields + maxResults; nextPageToken paging).
Because THE PROBE ECONOMY RULE bounds every call to one --max page, this
connector never needs to walk nextPageToken -- the bound IS the feature.

Output is capped by -n/--max (default 25) per THE PROBE ECONOMY RULE: stdout is
destined for compiled context payloads, so the bound is a feature.

COMPILE-LANE CAUTION: project keys, issue summaries, descriptions, comments,
custom-field values (a SalesForce ID, a Project URL), and attachment URLs
are client identifiers and client content. Any `!` invocation bound for a cloud
chat window rides through the compile-lane sanitizer -- make sure
pii_substitutions.txt covers the relevant identifiers first. (For an
internal-Confluence-only lane, a disclosure profile that leaves names in place
is the intended path.)
"""

import os
import re
import sys
import json
import argparse
from urllib.parse import urlparse, parse_qs

import httpx

ISSUE_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+-\d+$')
PROJECT_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+$')

# THE EMPTY ARGUMENT ASKS THE MORNING QUESTION (2026-09-10). Bare `jira` used
# to list every project the account could see -- a directory, when the one
# thing a Solutions Engineer asks Jira first, every day, is "what is still
# open with my name on it." The browser answers that at /jira/for-you on the
# assigned tab, so the empty argument now gives the same answer, the For You
# URL routes to it (normalize_query), and the directory keeps one plain word.
# The JQL is INFERRED, not observed: it approximates the tab's own filter,
# and the tab's count is the falsifier -- if the two disagree, this line is
# the suspect, never the tickets. statusCategory rather than resolution so a
# ticket closed without a resolution set still drops off the list.
MINE_JQL = ('assignee = currentUser() AND statusCategory != Done '
            'ORDER BY priority DESC, updated DESC')
PROJECTS_WORD = 'projects'

# THE DOOR IS DECLARED, NEVER PROBED. Presence of JIRA_CLOUD_ID IS the
# declaration that this credential is a SCOPED token, which authenticates
# only at the platform gateway; absence means a CLASSIC token, which
# authenticates only at the site host. There is deliberately NO
# try-one-then-fall-back: Jira raises a CAPTCHA after a few consecutive
# failed logins and then refuses REST auth outright (the tell is a header
# reading X-Seraph-LoginReason: AUTHENTICATION_DENIED), so a connector that
# probes its own door doubles every failed auth and can destroy the very
# instrument it is reading with -- on a counter nobody can reset from this
# side. Same shape as `clear` eating scrollback: a read that deletes.
JIRA_GATEWAY = "https://api.atlassian.com/ex/jira"


def resolve_base(site_url, cloud_id):
    """Return (base_url, door_label) from DECLARED config only."""
    cloud_id = (cloud_id or "").strip()
    if cloud_id:
        return f"{JIRA_GATEWAY}/{cloud_id}", "gateway"
    return (site_url or "").rstrip('/'), "site host"


def normalize_query(arg):
    """Turn a browser-copied Jira URL into the key this connector routes on.

    THE URL IS WHAT THE HUMAN HAS. Every other accepted shape -- a bare issue
    key, a bare project key, a JQL string -- requires already knowing the key,
    which in practice means reading it off a URL and retyping it. The URL is
    the one thing a browser hands you with a keystroke, so it is the shape
    that should just work. Recognized, in order: any query value that IS an
    issue key (?selectedIssue=PROJ-123), then any path segment that IS an
    issue key (/browse/PROJ-123), then the segment after /projects/ or
    /browse/ when it is a project key.

    IT REFUSES RATHER THAN FALLS THROUGH. An unrecognized http(s) argument
    used to reach search_issues as a JQL string, and Jira answers that with an
    HTTP 400 about JQL syntax -- an error about a query language the human
    never typed, naming nothing they can act on. Same disease as the Slack
    channel-URL bug convicted 2026-08-26: the wrong lane's error message. A
    JQL string never begins with http, so this refusal cannot swallow a
    legitimate search.

    CALLED BEFORE make_client() ON PURPOSE. The refusal then costs no
    credential and no network call, which is what makes the wiring probeable
    in the compile lane without firing a live request at a client's Jira and
    printing that host into a payload.
    """
    if not arg.startswith(('http://', 'https://')):
        return arg
    parsed = urlparse(arg)
    for values in parse_qs(parsed.query).values():
        for value in values:
            if ISSUE_KEY_RE.match(value):
                return value
    parts = [p for p in parsed.path.split('/') if p]
    # THE FOR YOU PAGE IS THE MINE MODE (2026-09-10). /jira/for-you is the
    # one Jira URL with no key in it, and it is the one a Solutions Engineer
    # has open all day. None here means "no argument", which main() routes
    # to list_mine -- the same answer the empty command gives. A
    # ?selectedIssue= on that page still wins above, because a clicked
    # ticket is more specific than the page it was clicked on.
    if 'for-you' in parts:
        return None
    for part in reversed(parts):
        if ISSUE_KEY_RE.match(part):
            return part
    for marker in ('projects', 'browse'):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts) and PROJECT_KEY_RE.match(parts[index + 1]):
                return parts[index + 1]
    sys.stderr.write(
        "Could not find an issue key or project key in that URL.\n"
        "Recognized shapes:\n"
        "  https://<site>.atlassian.net/browse/PROJ-123\n"
        "  https://<site>.atlassian.net/jira/for-you?tab=assigned\n"
        "  https://<site>.atlassian.net/jira/...?selectedIssue=PROJ-123\n"
        "  https://<site>.atlassian.net/jira/software/c/projects/PROJ/boards/1\n"
        "Pass the key itself (PROJ-123 or PROJ) for any other shape.\n"
    )
    # THE AMPUTATED URL (convicted 2026-09-02). An UNQUOTED for-you URL
    # reached here as .../for-you?tab=assigned -- bash had read the `&`
    # as its background operator, printed a job number, and executed
    # `selectedIssue=PS-10559` as a variable assignment nobody read. The
    # refusal above was correct for the argv it got and wrong about the
    # cause: the shape was fine, the shell ate half of it. The signature
    # is a query string with NO `&` in it, which a browser-copied Jira URL
    # almost never has; a short legitimate URL still refuses quietly.
    if parsed.query and '&' not in parsed.query:
        sys.stderr.write(
            "Hint: if the shell printed a job number like [1] NNNN, it split\n"
            "the URL at an unquoted `&`. Wrap the whole URL in single quotes.\n"
        )
    sys.exit(1)


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
        # THE THIRD OCCURRENCE. The 2026-07-23 car that retired the
        # shared-identity claim moved the module docstring and check()'s
        # docstring and MISSED this one -- the only one a stranger actually
        # reads, at the exact moment they are configuring. Caught by a delta
        # probe whose absolute prediction (1 -> 0) was wrong because the real
        # baseline was 2. A label move is counted BEFORE it is made.
        sys.stderr.write(
            "Missing environment variable(s): " + ", ".join(missing) + "\n"
            "JIRA_URL example: https://yourco.atlassian.net  (no /wiki)\n"
            "That host is right for a CLASSIC token only. A SCOPED token\n"
            "authenticates at https://api.atlassian.com/ex/jira/<cloudId>/\n"
            "and 401s at the site host forever -- same failure a stranger\n"
            "with no account gets, so the message cannot tell you apart.\n"
            "JIRA_TOKEN MAY be the same Atlassian API token confluence.py\n"
            "uses, but it need not be: Jira and Confluence can live at\n"
            "different hosts under different tokens, and a SCOPED token\n"
            "minted for one product does not grant the other. Set JIRA_TOKEN\n"
            "explicitly whenever the two differ.\n"
        )
        sys.exit(1)
    return base.rstrip('/'), email, token


def make_client():
    base, email, token = get_env()
    api_base, _door = resolve_base(base, os.getenv("JIRA_CLOUD_ID"))
    client = httpx.Client(auth=(email, token), timeout=60.0,
                          headers={"Accept": "application/json"})
    return client, api_base


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
              "panel", "rule", "mediaSingle", "mediaGroup"}


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
        # A link MARK rides on the text node, and smart cards (inlineCard,
        # blockCard, embedCard) carry their URL in attrs with no text node
        # at all. Convicted 2026-09-10 by a census receipt: "has some helpful
        # documentation here:" printed followed by nothing, the Confluence
        # link having been an inlineCard the old walk rendered as "". Keep
        # the href beside the text unless the text already IS the href.
        text = node.get("text", "")
        for mark in node.get("marks") or []:
            if isinstance(mark, dict) and mark.get("type") == "link":
                href = (mark.get("attrs") or {}).get("href") or ""
                if href and href != text:
                    return f"{text} ({href})"
        return text
    if ntype in ("inlineCard", "blockCard", "embedCard"):
        return (node.get("attrs") or {}).get("url") or "[card]"
    if ntype in ("media", "mediaInline"):
        # Screenshots and attachments are media nodes with an id and no
        # text; "The screenshot below" used to point at nothing.
        attrs = node.get("attrs") or {}
        return "[media: " + str(attrs.get("alt") or attrs.get("id") or "?") + "]"
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


# CUSTOM FIELDS ARE OPAQUE IDS UNTIL YOU ASK FOR THEIR NAMES (2026-09-10).
# fetch_issue used to request a fixed field list, so "Project URL" never
# escaped -- it was never requested. It now asks for *all with expand=names,
# which returns a customfield_NNNNN -> label map beside the values, and every
# populated custom field prints under ## Fields. The denylist is BY LABEL and
# was written from a census receipt, not imagined: Rank is a lexorank string
# ("2|i06je5:") and Development a JSON blob about branches; neither is a fact
# a human reads. Extend it only from another receipt.
_FIELD_DENYLIST = {"Rank", "Development"}


def _field_empty(value):
    """True for every shape Jira uses to say 'nothing here': null, an empty
    string/list/dict, and the JSON-ish "{}" / "[]" strings some fields return
    instead of null (Development, witnessed 2026-09-10)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ("", "{}", "[]")
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _field_text(value):
    """One line of text for a custom-field value, whatever its shape: strings
    and numbers verbatim, option/user/version dicts by their display key, an
    ADF doc through adf_to_text, lists joined, and anything unrecognized as
    truncated JSON so an unknown shape SHOWS rather than vanishes."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if value.get("type") == "doc":
            return clean_text(adf_to_text(value))
        for key in ("displayName", "name", "value", "key"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value)[:120]
    if isinstance(value, list):
        return ", ".join(_field_text(v) for v in value if not _field_empty(v))
    return str(value)


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
                "fields": "summary,status,issuetype,priority,assignee,updated"})
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


def list_mine(client, base, max_items):
    """MINE mode, no argument: every open issue assigned to this account.

    Prints the JQL it ran as the second line, so the human can copy it into
    SEARCH mode and bend it (add a project, drop the ORDER BY) without
    reading source -- the connector teaching its own use, contract item 3.
    """
    issues = _search(client, base, MINE_JQL, max_items)
    print("# Open Jira issues assigned to you (key | status | priority | summary)")
    print(f"# jql: {MINE_JQL}\n")
    if not issues:
        print("(nothing open with your name on it -- or the JQL above disagrees "
              "with /jira/for-you?tab=assigned, in which case the JQL is wrong)")
        return
    for it in issues[:max_items]:
        f = it.get("fields", {})
        print(f"{it.get('key', '?')}  [{_name(f.get('status'))}]  "
              f"[{_name(f.get('priority'))}]  {f.get('summary', '')}")
    if len(issues) >= max_items:
        print(f"\n# (capped at {max_items}; raise -n/--max to see the rest)")
    print("\n# Next: python scripts/connectors/jira.py <PROJ-123>   (full issue text)")
    print("#       python scripts/connectors/jira.py projects      (every project you can see)")


def fetch_issue(client, base, issue_key):
    """FETCH mode: one issue's full text -- fields, description, comments."""
    data = get_json(
        client, f"{base}/rest/api/3/issue/{issue_key}",
        params={"fields": "*all", "expand": "names"})
    f = data.get("fields", {})
    names = data.get("names", {}) or {}
    summary = f.get("summary", "(no summary)")
    print(f'# Jira issue {issue_key} -- "{summary}"')
    print(f"# status: {_name(f.get('status'))} | type: {_name(f.get('issuetype'))} "
          f"| priority: {_name(f.get('priority'))}")
    print(f"# assignee: {_name(f.get('assignee'))} | reporter: {_name(f.get('reporter'))}")
    print(f"# created: {f.get('created', '?')} | updated: {f.get('updated', '?')}\n")

    custom = []
    for key, value in f.items():
        if not key.startswith("customfield_") or _field_empty(value):
            continue
        label = names.get(key, key)
        if label in _FIELD_DENYLIST:
            continue
        custom.append((label, value))
    if custom:
        print("## Fields")
        for label, value in custom:
            print(f"{label}: {_field_text(value)}")
        print()

    attachments = f.get("attachment") or []
    if attachments:
        print(f"## Attachments ({len(attachments)})")
        for a in attachments:
            print(f"{a.get('filename', '?')}  {a.get('content', '')}")
        print()

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
    api_base, door = resolve_base(base, os.getenv("JIRA_CLOUD_ID"))
    try:
        with httpx.Client(auth=(email, token), timeout=15.0,
                          headers={"Accept": "application/json"}) as client:
            resp = client.get(api_base + "/rest/api/3/myself")
    except httpx.HTTPError as e:
        sys.stderr.write(f"jira RED gate2: transport failure: {e}\n")
        return 1
    # 401 and 403 are DIFFERENT failures and must not share a sentence. 401 is
    # "not authenticated"; 403 is "authenticated, then forbidden". The old line
    # blamed a missing Jira license for a 401 without ever having established
    # that the token worked anywhere -- a verdict where only an observation was
    # in hand. Report the observation; offer causes as ordered candidates.
    #
    # ORDERING CONVICTED 2026-07-23 by probe: /rest/api/3/serverInfo answered
    # 200 ANONYMOUSLY on the same base whose /myself read 401. That pair is a
    # HOST LIVENESS receipt and never an auth one, so "wrong site" leaves the
    # top of the list. Atlassian Cloud returns this identical 401 both for a
    # bad credential and for a valid one whose account is not a member of the
    # site, which is why membership rides above licensing. The same probe
    # found this wallet's JIRA_TOKEN was not the CONFLUENCE token at all, so
    # the cross-check below is conditional on the two actually matching.
    #
    # ORDERING AMENDED 2026-07-23 (round two): a candidate that is FREE to
    # falsify and needs NO other human rides above every candidate that needs
    # an admin. A scoped token 401s at the site host byte-identically to a
    # revoked one and to a stranger's, so this message has been ranking three
    # expensive causes above one cheap one. THE FREE FALSIFIER RIDES FIRST.
    if resp.status_code == 401:
        shared = bool(token) and token == os.getenv("CONFLUENCE_TOKEN")
        cross = ("JIRA_TOKEN is the same string as CONFLUENCE_TOKEN, so "
                 "`confluence --check` splits credential from site access"
                 if shared else
                 "JIRA_TOKEN differs from CONFLUENCE_TOKEN, so a green "
                 "confluence row establishes nothing about this one")
        door_line = (
            "(1) the token is SCOPED and this is the wrong door -- a scoped "
            "token authenticates ONLY at https://api.atlassian.com/ex/jira/"
            "<cloudId>/rest/... and 401s at a site host forever; declare "
            "JIRA_CLOUD_ID to route there. Costs one anonymous call to "
            "falsify and needs no admin, so it goes first. "
            if door == "site host" else
            "(1) NOT the wrong door -- this call already went through the "
            "gateway, so routing is FALSIFIED and every candidate below it "
            "needs someone or something other than you. ")
        sys.stderr.write(
            f"jira RED gate2: HTTP 401 via {door}, not authenticated. "
            "Candidates in order: " + door_line +
            "(2) the token's account is not a "
            "member of THIS site, which Cloud reports as 401 rather than 403; "
            "(3) the token is expired -- Atlassian gave every previously "
            "infinite token an expiry between 2026-03-14 and 2026-05-12, so "
            "an old untouched token is dead by arithmetic; (4) email and "
            "token belong "
            "to different accounts; (5) the site is Server/Data Center, which "
            "wants a Personal Access Token in an Authorization: Bearer header "
            "instead of basic auth -- serverInfo's deploymentType splits that "
            "in one anonymous call. A missing Jira LICENSE reads 403, not 401. "
            f"{cross}.\n")
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
    print(f"jira GREEN {name} (via {door})")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Jira Cloud API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (your open issues), the word projects, a PROJECTKEY, an issue key (PROJ-123), a Jira URL, or a JQL string."
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

    if args.query:
        args.query = normalize_query(args.query.strip())

    client, base = make_client()
    try:
        arg = args.query
        if arg is None:
            list_mine(client, base, args.max)
        else:
            arg = arg.strip()
            if arg == PROJECTS_WORD:
                list_projects(client, base, args.max)
            elif ISSUE_KEY_RE.match(arg):
                fetch_issue(client, base, arg)
            elif PROJECT_KEY_RE.match(arg):
                list_project_issues(client, base, arg, args.max)
            else:
                search_issues(client, base, arg, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
