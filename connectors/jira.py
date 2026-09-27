#!/usr/bin/env python3
# connectors/jira.py
"""
jira.py — List your open Jira tickets, or fetch one by key.

A Unix-philosophy gateway to the Jira Cloud API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python connectors/jira.py                 # MINE: open issues assigned to you (the For You tab)
  python connectors/jira.py projects        # LIST: projects you can see
  python connectors/jira.py ENG             # LIST: recently-updated issues in project ENG
  python connectors/jira.py ENG-123         # FETCH: full text of one issue (custom fields + description + comments)
  python connectors/jira.py board:453       # BOARD: the board's saved filter, its JQL, counts, then its issues (a /boards/<id> URL routes here)
  python connectors/jira.py 'assignee = currentUser() ORDER BY updated DESC'  # SEARCH: raw JQL

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python connectors/jira.py
  ! python connectors/jira.py ENG
  ! python connectors/jira.py ENG-123

Disambiguation rule (checked in this order):
  - no argument                          -> MINE: open issues assigned to you
  - any /jira/for-you URL               -> MINE, the same answer
  - the word projects                    -> LIST projects
  - matches PROJ-123 (KEY-<digits>)      -> FETCH one issue
  - board:<id> (or a /boards/<id> URL)  -> BOARD: the saved filter's JQL, counts first, then rows
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
THE PROBE ECONOMY RULE still bounds every search to -n, and since 2026-09-27
the walk goes page by page up to it (_search_pages): the server pages at 100
whatever maxResults asks (READ when -n 500 on board 453 returned exactly 100
of the 162 the board shows), so one page under a larger -n read as a complete
list. The bound IS still the feature; the pages are how it is reached.

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
import glob
from urllib.parse import urlparse, parse_qs

import httpx

ISSUE_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+-\d+$')
PROJECT_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+$')
BOARD_RE = re.compile(r'^board:(\d+)$')
SEARCH_FIELDS = "summary,status,issuetype,priority,assignee,updated"
# THE LINK LIVES IN THE TEXT (READ 2026-09-27, deed 1626): both custom fields
# named Project URL counted 0 on SVB (cf[12188] and cf[12189], each is not
# EMPTY), so a ticket's Botify project, when it names one, is a link in the
# summary or the description. The first two path segments are org/project;
# app.botify.com/tools/... is a product page and never an org.
BOTIFY_PROJECT_RE = re.compile(r'https?://app\.botify\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)')
_NOT_AN_ORG = frozenset({"tools", "admin", "api", "login", "static", "settings"})


def _botify_project_link(text):
    """The first app.botify.com/<org>/<project> URL in text, or ''."""
    for match in BOTIFY_PROJECT_RE.finditer(text or ""):
        if match.group(1).lower() not in _NOT_AN_ORG:
            return match.group(0)
    return ""


def _slug_from_url(url):
    """org/project from an app.botify.com URL, or ''."""
    if not str(url or "").startswith(("http://", "https://")):
        return ""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if "botify.com" in parsed.netloc and len(parts) >= 2 and parts[0].lower() not in _NOT_AN_ORG:
        return f"{parts[0]}/{parts[1]}"
    return ""


# THE JOIN IS THE HOSTNAME (READ 2026-09-27, deed 1627): 185 board rows, one
# app.botify.com link among them, and every open row naming its site in the
# summary ("JS settings QA - client-g.example"), while a Botify project slug
# is usually the hostname itself (mikelev.in, client-c.example). A populated
# field labelled Project-slug on the specimen ticket is the cleaner join and
# rides first; the summary's hostname is the fallback, resolved against the
# local corpus so a slug is printed only when botify --rules can answer it.
HOSTNAME_RE = re.compile(r'\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b', re.IGNORECASE)


def _hostname_in(text):
    """The first hostname-shaped token in text, lowercased, or ''."""
    match = HOSTNAME_RE.search(text or "")
    return match.group(1).lower() if match else ""


def _slug_for_host(host, pulls_root):
    """org/project when a local pull carries this hostname as its project slug, with or without a leading www., else ''."""
    candidates = [host, host[4:] if host.startswith("www.") else "www." + host]
    for candidate in candidates:
        hits = sorted(glob.glob(os.path.join(pulls_root, "*", candidate, "sitecrawler.json")))
        if hits:
            org = os.path.basename(os.path.dirname(os.path.dirname(hits[0])))
            return f"{org}/{candidate}"
    return ""


def _slug_from_text(text, pulls_root):
    """org/project from a Project-slug value: an app URL parses, a slashed value is taken as given, a bare slug resolves like a hostname; '' when unresolved."""
    text = str(text or "").strip().strip("/")
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return _slug_from_url(text)
    if "/" in text:
        return text
    return _slug_for_host(text.lower(), pulls_root)

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
# NO SCOPE SLOT, AND NO WALLET READER (census 2026-09-16; the receipt is a
# grep of THIS file for connectors.json, PIPULATE_WALLET, defaults,
# JIRA_PROJECT and JIRA_JQL matching NOTHING, exit 1, on both sides of a
# compile). Bare `jira` has exactly one behavior and no argument to narrow
# it. A project key narrows it (`jira PROJ`); a board's saved filter cannot,
# because there is nowhere to put one. THE BOARD IS NOT HARDWIRED HERE --
# there is no board constant to un-hardwire -- so the defect is a MISSING
# slot, not a CHOSEN one, and that is a different repair than the MCP
# credential path needed before token_path_for: that one made collision
# unrepresentable, this one must make scope REPRESENTABLE.
# THE CURE IS AN ENV VAR, NOT A JSON READER. flake.nix's WALLET HYDRATOR
# already exports every `defaults` key of every wallet slot as an env var at
# shell entry, never overwriting what is already set, and for an ENV KIND --
# jira is basic_auth -- those keys ARE env var NAMES, which is also how
# wallet.py's _warm_env reads them when it prints defaults[var] as the
# example for var. So a wallet slot carrying
#   "jira": {"auth": "basic_auth", "defaults": {"JIRA_JQL": "<filter>"}}
# arrives here as a plain os.getenv("JIRA_JQL"), with no reader added, no
# fourth copy of any derivation, and README.md's stated order unchanged:
# CLI flag -> env var -> connectors.json default -> clean failure. The key
# is JQL and not `board` or `project` because a board IS a saved JQL filter
# on the Atlassian side, a project key is already handled positionally, and
# a raw JQL string is the one shape that can express either. Until that
# lands, this constant is the whole of MINE mode.
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
# WITNESSED 2026-09-24: a 192-character token answered 401 at the site host
# and GREEN at the gateway, with JIRA_CLOUD_ID set to the cloudId that
# <site>/_edge/tenant_info returns without authentication. Two declared
# runs, one per door, settled it; this connector never tried both itself.
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
    # THE BOARD URL WORKS, AND SILENTLY DROPS THE BOARD (named 2026-09-16).
    # A board address is .../jira/software/c/projects/PROJ/boards/123, so
    # `projects` is in parts and PROJ matches PROJECT_KEY_RE: this returns
    # PROJ and main() routes to list_project_issues. That is not a failure
    # and it is not the board either. The /boards/123 half -- the ONLY part
    # carrying the saved filter the human meant -- is discarded without a
    # word, and what comes back is the whole project ordered by updated
    # DESC. THE DISCRIMINATION QUESTION, failing inside a return value: the
    # output is byte-identical to `jira PROJ`, so nothing on screen can tell
    # the board they asked for from the project they got, and the refusal
    # message above even lists this URL shape as RECOGNIZED, which it is --
    # as a project key. Whoever lands the scope slot should decide here
    # whether a /boards/<id> segment says so out loud or resolves.
    # WITNESSED 2026-09-24: a board URL printed the project header and the
    # same first three rows as the bare project key.
    # RESOLVED 2026-09-27 (the speed-dating queue): a /boards/<id> segment
    # now wins over the project key beside it and routes to BOARD mode as
    # board:<id>, the spelling a hand can type without the URL. The
    # paragraph above is the history of the branch this one replaces.
    if 'boards' in parts:
        index = parts.index('boards')
        if index + 1 < len(parts) and parts[index + 1].isdigit():
            return f"board:{parts[index + 1]}"
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
    print("\n# Next: python connectors/jira.py <PROJECTKEY>   (recent issues)")


def _search_pages(client, base, jql, max_items, fields=SEARCH_FIELDS):
    """Walk the enhanced search page by page, up to max_items.

    THE FULL PAGE WAS SILENT, second shape (READ 2026-09-27, deeds 1625 and
    1626): the server pages at 100 whatever maxResults asks, INFERRED from
    -n 500 on board 453 returning exactly 100 of the 162 the board shows, so
    a single page under a bigger -n read as a complete list and the cap line
    never fired. -n is still the bound: the walk stops at it, at the server's
    isLast, at a missing nextPageToken, or at 50 pages. Returns
    (issues, pages, exhausted); exhausted is True when the server said the
    last page was reached, so a caller can tell 'all of them' from 'the
    first N', which is the difference between a census and a sample.
    """
    issues, token, pages, exhausted = [], None, 0, False
    while len(issues) < max_items and pages < 50:
        params = {"jql": jql, "maxResults": max_items - len(issues), "fields": fields}
        if token:
            params["nextPageToken"] = token
        data = get_json(client, f"{base}/rest/api/3/search/jql", params=params)
        data = data if isinstance(data, dict) else {}
        page = data.get("issues") or []
        pages += 1
        issues.extend(page)
        token = data.get("nextPageToken")
        exhausted = bool(data.get("isLast")) or not token or not page
        if exhausted:
            break
    return issues[:max_items], pages, exhausted


def _search(client, base, jql, max_items):
    return _search_pages(client, base, jql, max_items)[0]


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
    # THE FULL PAGE WAS SILENT (convicted 2026-09-24, cartridge
    # foo-9d59e535-96.zip). `jira SVB -n 100` printed exactly 100 rows and no
    # warning, and a truncated list reads exactly like a complete one: the
    # only tells were a row count and SVB-115 missing from it. list_mine
    # already says so out loud; this says it the same way.
    if len(issues) >= max_items:
        print(f"\n# (hit the -n cap of {max_items}; there may be more -- raise -n/--max)")
    print("\n# Next: python connectors/jira.py <PROJ-123>   (full issue text)")


def search_issues(client, base, jql, max_items):
    """SEARCH mode: raw JQL."""
    # THE EMPTY SET IS NOT A CENSUS (witnessed 2026-09-24). Three key-range
    # windows over one project -- `key <= P-100`, `key > P-100 AND key <=
    # P-200`, `key > P-200` -- each printed "(no matches)" with no HTTP
    # error, in the compile where the plain project listing returned rows
    # through this same _search, with issues known to exist inside the
    # middle window. The cause is not established. "(no matches)" reports
    # what the API returned for that JQL, never how many issues exist: trust
    # a range query only after a key known to be inside it comes back.
    issues = _search(client, base, jql, max_items)
    print(f"# Jira JQL search: {jql}  (key | status | summary)\n")
    if not issues:
        print("(no matches)")
        return
    for it in issues[:max_items]:
        f = it.get("fields", {})
        print(f"{it.get('key', '?')}  [{_name(f.get('status'))}]  {f.get('summary', '')}")
    if len(issues) >= max_items:
        print(f"\n# (hit the -n cap of {max_items}; there may be more -- raise -n/--max)")
    print("\n# Next: python connectors/jira.py <PROJ-123>   (full issue text)")


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
    print("\n# Next: python connectors/jira.py <PROJ-123>   (full issue text)")
    print("#       python connectors/jira.py projects      (every project you can see)")


def _custom_field_ids(client, base, labels):
    """{label: [ids]} for every custom field whose folded label is one of labels, in the API's order.

    A search returns custom fields by id (customfield_NNNNN) and never by
    label, and the id differs from site to site while the label is what
    the humans typed, so one GET on /rest/api/3/field maps the label to
    this site's id. None means the site has no such field, which the
    caller says out loud rather than reading as zero tickets with a URL.
    CONVICTED 2026-09-27 (deed 1625, by a census and not by a second
    candidate arriving): this site carries TWO fields named Project URL,
    customfield_12188 and customfield_12189, and this loop keeps whichever
    the API lists first, so the board's counts line read 0 with an id
    resolved and no note printed: SINGLE-CANDIDATE BLINDNESS in a selector
    that never knew there were two. A JQL by the same name read rows=0
    and raised no ambiguity error, so Jira picked one as well, unnamed.
    The cure, once a populated issue is known: return every id under the
    label and let the caller read whichever is filled per issue. The
    falsifier is by id and never by name: cf[12188] is not EMPTY and
    cf[12189] is not EMPTY, each counted. READ 2026-09-27 (deed 1626): both
    counted 0 on SVB, so every id rides, the caller reads whichever is
    filled, and a link in the summary or description stands in for both.
    READ 2026-09-27 (deed 1627): the specimen ticket carries a populated
    field labelled Project-slug, so this lookup takes a set of labels and
    folds case, whitespace and hyphens before comparing, returning every id
    under each label; the board reads Project URL, then Project-slug.
    """
    def fold(name):
        return re.sub(r"[\s_-]+", " ", str(name or "")).strip().lower()
    found = {fold(label): [] for label in labels}
    fields = get_json(client, f"{base}/rest/api/3/field")
    for item in (fields if isinstance(fields, list) else []):
        if isinstance(item, dict) and item.get("id") and fold(item.get("name")) in found:
            found[fold(item.get("name"))].append(item.get("id"))
    return found


def list_board_issues(client, base, board_id, max_items):
    """BOARD mode, board:<id>: the board's saved filter, its JQL, counts, rows.

    THE BOARD IS THE SCOPE (2026-09-27, the speed-dating queue; named
    2026-09-16 when a board URL was found reducing to its project key). A
    board is a saved filter on the Atlassian side, so the scope is three
    GETs: the board's configuration names its filter, the filter carries
    the JQL, the enhanced search runs it with this site's Project URL
    field asked for by id. THE COUNTS COME BEFORE ANY ROW, because the
    queue's shape is the question a Solutions Engineer asks first: how
    many issues the filter returns under the -n cap, how many carry a
    Project URL, how many of those name an app.botify.com org/project, and
    how many of those have a local pull under data/botify_pulls, so that
    botify --rules org/project answers for them today. Rows follow, each
    with its org/project when it has one. The two Atlassian paths
    (/rest/agile/1.0/board/<id>/configuration and /rest/api/3/filter/<id>)
    are from the documentation and UNWITNESSED until the first receipt;
    get_json prints the HTTP code and the body on any refusal, so a wrong
    path is a reading and never a crash.
    WITNESSED 2026-09-27 (deed 1623, the first flight): both answered 200
    for board 453, SVB board, type simple, filter 15051, JQL project = SVB
    ORDER BY Rank ASC, so that board is the whole project in board order,
    Rank ASC being the top. The counts line read 0 with a Project URL
    among 100 issues at -n 100 and again at -n 500, which returned exactly
    100 (deed 1625): the enhanced search pages at 100 (INFERRED from 500
    asked), the cap line below fires only when the page fills -n, so a
    server page smaller than -n reads as a complete list -- THE FULL PAGE
    WAS SILENT in a second shape -- and nextPageToken is never walked here
    by design. The zero has a second cause in _custom_field_ids.
    RESOLVED 2026-09-27 (deed 1626): _search_pages walks the pages up to
    -n and says whether the filter was exhausted, every Project URL id is
    read, a link in the summary or description stands in when the fields
    are empty (both read 0 on SVB), and the counts carry a by-status line so
    the board's own column numbers (To Do 13, In Progress 1, In Review 11,
    Done 137 on 2026-09-27) are the known members of the census.
    READ 2026-09-27 (deed 1627): the filter returns 185 where the board's
    face shows 162, the 23 INFERRED epics and sub-tasks a column never
    counts, so a by-type line rides beside by-status; one row in 185 carried
    an app.botify.com link and none a Project URL, so the join is the
    Project-slug field first and the summary's hostname second, resolved
    against data/botify_pulls, and each row says whether a pull exists.
    """
    config = get_json(client, f"{base}/rest/agile/1.0/board/{board_id}/configuration")
    config = config if isinstance(config, dict) else {}
    filt = config.get("filter") if isinstance(config.get("filter"), dict) else {}
    filter_id = filt.get("id")
    print(f"# Jira board {board_id}: {config.get('name', '?')} "
          f"(type {config.get('type', '?')}, filter {filter_id or '?'})")
    if not filter_id:
        print("(the board configuration names no filter; nothing to search)")
        return
    filter_data = get_json(client, f"{base}/rest/api/3/filter/{filter_id}")
    jql = filter_data.get("jql") if isinstance(filter_data, dict) else None
    print(f"# jql: {jql}\n")
    if not jql:
        print("(the filter carries no jql)")
        return
    ids = _custom_field_ids(client, base, ("project url", "project slug"))
    url_fields, slug_fields = ids["project url"], ids["project slug"]
    fields = SEARCH_FIELDS + ",description"
    if url_fields or slug_fields:
        fields += "," + ",".join(url_fields + slug_fields)
    issues, pages, exhausted = _search_pages(client, base, jql, max_items, fields)
    by_status, by_type = {}, {}
    source_counts = {"Project URL": 0, "Project-slug": 0, "link": 0, "hostname": 0}
    pulls_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "botify_pulls")
    with_project = local = 0
    rows = []
    for it in issues:
        f = it.get("fields", {}) or {}
        status = _name(f.get("status"))
        by_status[status] = by_status.get(status, 0) + 1
        itype = _name(f.get("issuetype"))
        by_type[itype] = by_type.get(itype, 0) + 1
        summary = f.get("summary") or ""
        slug = host = source = ""
        for field_id in url_fields:
            raw = f.get(field_id)
            if not _field_empty(raw):
                slug = _slug_from_url(_field_text(raw))
                if slug:
                    source = "Project URL"
                    break
        if not slug:
            for field_id in slug_fields:
                raw = f.get(field_id)
                if _field_empty(raw):
                    continue
                value = _field_text(raw)
                slug = _slug_from_text(value, pulls_root)
                if slug:
                    source = "Project-slug"
                    break
                host = host or _hostname_in(value)
        if not slug:
            link = _botify_project_link(f"{summary}\n{adf_to_text(f.get('description'))}")
            slug = _slug_from_url(link) if link else ""
            if slug:
                source = "link"
        if not slug:
            host = host or _hostname_in(summary)
            slug = _slug_for_host(host, pulls_root) if host else ""
            if slug:
                source = "hostname"
        pulled = False
        if slug:
            with_project += 1
            source_counts[source] += 1
            org, _, project = slug.partition("/")
            pulled = os.path.exists(os.path.join(pulls_root, org, project, "sitecrawler.json"))
            local += 1 if pulled else 0
        rows.append((it.get("key", "?"), status, summary, slug, host, pulled))
    sources = ", ".join(f"{n} from {label}" for label, n in source_counts.items())
    print(f"# counts: {len(issues)} issue(s) under the -n cap of {max_items} "
          f"({pages} page(s); {'the filter is exhausted' if exhausted else 'more remain above the cap'}); "
          f"{with_project} naming a Botify org/project ({sources}); {local} of those with a local pull "
          "(botify --rules org/project answers today)")
    print("# by status: " + (" | ".join(f"{s} {n}" for s, n in sorted(by_status.items(), key=lambda kv: -kv[1])) or "none"))
    print("# by type: " + (" | ".join(f"{t} {n}" for t, n in sorted(by_type.items(), key=lambda kv: -kv[1])) or "none"))
    print(f"# field id(s): Project URL {', '.join(url_fields) or 'none'}; Project-slug {', '.join(slug_fields) or 'none'}")
    if not issues:
        print("(no issues match the board's filter)")
        return
    print()
    for key, status, summary, slug, host, pulled in rows:
        tail = ""
        if slug:
            tail = f"  -> {slug}" + ("  (pulled)" if pulled else "  (no local pull)")
        elif host:
            tail = f"  -> {host}  (no local pull; no org known)"
        print(f"{key}  [{status}]  {summary}{tail}")
    if len(issues) >= max_items:
        print(f"\n# (hit the -n cap of {max_items}; there may be more -- raise -n/--max)")
    print("\n# Next: python connectors/jira.py <PROJ-123>   (full issue text)")
    print("#       botify --rules <org/project>             (that project's deployed rules, from the local corpus)")


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
            elif BOARD_RE.match(arg):
                list_board_issues(client, base, BOARD_RE.match(arg).group(1), args.max)
            elif PROJECT_KEY_RE.match(arg):
                list_project_issues(client, base, arg, args.max)
            else:
                search_issues(client, base, arg, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
