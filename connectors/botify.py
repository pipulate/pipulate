#!/usr/bin/env python3
# connectors/botify.py
"""
botify.py — Bring Botify crawl data and BQL query results into context.

A Unix-philosophy gateway to the Botify API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python connectors/botify.py                    # LIST: identity walk -> all your org/project slugs
  python connectors/botify.py org                # LIST: projects under that org slug
  python connectors/botify.py org/project        # LIST: analyses (crawl snapshots) for that project
  python connectors/botify.py org/project/analysis    # FETCH: verdict (status, pages, rate, cadence ETA) + crawl statistics, running or done
  python connectors/botify.py 'https://app.botify.com/org/project/...'   # any app URL reduces to its slug path first
  python connectors/botify.py org/project/saved_explorers --grep facet   # DRILL: any project sub-resource, rows narrowed
  python connectors/botify.py org/project/saved_explorers/<uuid>   # FETCH: one item in full, containers as JSON
  python connectors/botify.py org/project/analysis/crawl_statistics   # DRILL: any analysis sub-resource; a ?k=v rides along
  python connectors/botify.py org/project/collections/crawl.<slug> --grep link   # FIND: every leaf path in one object matching
  python connectors/botify.py org/project/analysis --grep link   # the verdict, then every leaf in the detail matching
  python connectors/botify.py '<BQL or JSON>'    # FETCH: run a query (needs org/project coordinates)
  python connectors/botify.py --census --q mikelev.in   # CENSUS: one row, to smoke the export door
  python connectors/botify.py --census           # CENSUS: every project, via the Django admin export form
  python connectors/botify.py --pull-configs --queue data/botify_census/<file>.queue.jsonl --limit 10

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python connectors/botify.py
  ! python connectors/botify.py my-org/my-project
  ! python connectors/botify.py 'SELECT url FROM crawl' --org my-org --project my-project

Disambiguation rule: an argument that starts with '{' or contains whitespace is
a query (FETCH mode); an app.botify.com URL is first reduced to its slug path
(org/project, plus ?analysisSlug= as a third segment); one or two segments LIST;
an all-digit third segment FETCHES that crawl's verdict, and a LIST never shows
a crawl still running -- fetch it by slug (witnessed 2026-09-10); any other
third segment, and anything after a slug, DRILLS the raw API path under the
project or the analysis, rendered by shape and narrowed by --grep. No argument at
all triggers the identity walk.

Auth: BOTIFY_API_TOKEN via config.get_botify_token() (env var or project .env).
FETCH coordinates resolve from --org/--project flags, then BOTIFY_ORG /
BOTIFY_PROJECT environment variables.

CENSUS and PULL-CONFIGS modes use NEITHER. They ride the session cookie
weblogin parked in data/uc_profiles/<profile>. Census needs it because the API
cannot enumerate projects at all; config pulls need it because SiteCrawler
settings and Activation GraphQL are authenticated by the warmed app session.
Both write only under data/ (gitignored), and pull mode prints only its summary.

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
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs, parse_qsl
from datetime import datetime, timedelta, timezone

import httpx

# Wire into the central config (same pattern as scripts/ai.py).
# NOTE: connectors/ sits at the repo root, beside scripts/, since the move
# out of scripts/connectors/ -- hence TWO parents. Three reached $HOME, read
# off the first Mac compile after the move; the import survived only because
# the editable install also exposes `config`.
# The editable install also exposes `config`, but the explicit path keeps
# this file honest as a standalone, curl-able artifact.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from config import get_botify_token

API_BASE = "https://api.botify.com/v1"


def normalize_query(arg):
    """Turn an app.botify.com URL into the slug path this connector routes on.

    THE URL IS WHAT THE HUMAN HAS (jira.py's rule, applied here 2026-09-10):
    the Jira ticket's Project URL field and the browser's address bar both
    hand you https://app.botify.com/<org>/<project>/..., and a
    ?analysisSlug= query names the crawl on the live-stats page. Recognized:
    the first two path segments as org/project, plus analysisSlug (or an
    all-digit third segment) as the analysis. Anything that is not an
    http(s) URL passes through untouched, so no BQL string and no bare slug
    path can be caught by this. A URL with no org/project refuses with the
    shape it wanted rather than falling through to a 404 about a path the
    human never typed.
    """
    if not arg.startswith(('http://', 'https://')):
        return arg
    parsed = urlparse(arg)
    parts = [p for p in parsed.path.split('/') if p]
    if len(parts) < 2:
        sys.stderr.write(
            "Could not find <org>/<project> in that URL's path.\n"
            "Expected https://app.botify.com/<org>/<project>/... "
            "(optionally ?analysisSlug=<slug>).\n")
        sys.exit(1)
    slug = (parse_qs(parsed.query).get('analysisSlug') or [None])[0]
    if not slug and len(parts) >= 3 and parts[2].isdigit():
        slug = parts[2]
    return '/'.join([parts[0], parts[1]] + ([slug] if slug else []))


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
    print("\n# Next: python connectors/botify.py <org>/<project>   (list analyses)")


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
    print("\n# Next: python connectors/botify.py " + org + "/<project>   (list analyses)")


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
        "\n# Next: python connectors/botify.py 'SELECT url FROM crawl' "
        f"--org {org} --project {project}"
    )
    print(f"#       python connectors/botify.py {org}/{project}/<analysis>   (one crawl's status + statistics;")
    print("#       a crawl still RUNNING can be absent from the list above -- fetch it by its slug)")


def scalar_rows(obj, cap):
    """(key, value) rows a human can read from one JSON object: scalars
    whole, containers as their size, capped at `cap` with a trailing tally
    row so the truncation is visible rather than silent."""
    items = list(obj.items()) if isinstance(obj, dict) else []
    rows = []
    for key, value in items[:cap]:
        if isinstance(value, dict):
            names = ", ".join(str(k) for k in list(value)[:6])
            more = ", ..." if len(value) > 6 else ""
            rows.append((key, "{" + f"{len(value)} keys: {names}{more}" + "}"))
        elif isinstance(value, list):
            rows.append((key, f"[{len(value)} item(s)]"))
        else:
            rows.append((key, value))
    if len(items) > cap:
        rows.append(("...", f"+{len(items) - cap} more key(s) (raise -n/--max)"))
    return rows


# THE FIELD NAMES, VERBATIM FROM THE FIRST RECEIPT (2026-09-10). The analysis
# detail carries the status and the clock; crawl_statistics carries the
# counters. The detail's own urls_done read 0 and urls_in_queue read None in
# the same receipt where crawl_statistics read pages_dones 10,954,595 -- the
# obviously named pair is dead, and the verdict below never reads it.
ANALYSIS_KEYS = ("slug", "name", "status", "crawl_launch_type", "date_created",
                 "date_launched", "date_crawl_done", "date_finished", "url")


def _iso(value):
    """A tz-aware datetime from an API timestamp, or None. The API writes a
    trailing Z, which fromisoformat accepts only from 3.11 on; spell it out."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def crawl_verdict(detail, stats, siblings):
    """The morning answer in a few lines: how far, how fast, and when.

    Every number comes from the receipts' own field names; a missing field
    drops its line rather than inventing one. Two clocks are printed and
    labelled: the queue-drain time at the observed rate, which is a FLOOR
    because the queue grows as deeper pages are found, and the ETA by
    cadence -- THE CADENCE IS THE CLOCK -- the median launch-to-finish of
    the finished siblings, which is what this crawler has actually done
    week after week without ever needing its 25M-page cap.
    TWO ENDS, NOT ONE (three receipts 2026-09-10): an analysis has
    date_crawl_done and then date_finished, with hours of post-crawl
    computing between them. The drain floor and the crawl-done cadence bound
    the first; the finished cadence bounds the second; filter links need the
    second. Discovery was witnessed at a tenth of the crawl rate, so the
    drain floor reads close to true near the end and hopelessly early at the
    start -- which is why it is labelled and never promoted.
    """
    lines = []
    launched = _iso(detail.get("date_launched"))
    finished = _iso(detail.get("date_finished"))
    crawl_done = _iso(detail.get("date_crawl_done"))
    updated = _iso(stats.get("last_upd_dt")) or datetime.now(timezone.utc)
    done, known = stats.get("pages_dones"), stats.get("pages_known")
    counted = isinstance(done, (int, float)) and isinstance(known, (int, float))
    lines.append(f"status: {detail.get('status', '?')}   "
                 f"launched: {detail.get('date_launched', '?')}")
    if counted:
        queued = known - done
        share = (done / known * 100) if known else 0.0
        lines.append(f"pages: {int(done):,} done of {int(known):,} known "
                     f"({int(queued):,} queued, {share:.1f}% of known), "
                     f"depth {stats.get('depth_current', '?')}")
        bad = sum(int(stats.get(k) or 0) for k in
                  ("pages_dones_4xx", "pages_dones_5xx", "pages_dones_networkerror"))
        lines.append(f"health: {int(stats.get('pages_dones_2xx') or 0):,} 2xx, "
                     f"{int(stats.get('pages_dones_3xx') or 0):,} 3xx, "
                     f"{bad:,} 4xx/5xx/network")
    rate = None
    if launched and counted:
        hours = ((crawl_done or finished or updated) - launched).total_seconds() / 3600
        if hours > 0:
            rate = done / (hours * 3600)
            lines.append(f"rate: {rate:.1f} URLs/s over {hours:.1f} h "
                         f"(as of {stats.get('last_upd_dt', 'now')})")
    if rate and not crawl_done and counted:
        drain = (known - done) / rate / 3600
        lines.append(f"queue drain: {drain:.1f} h at this rate -- a FLOOR on crawl-done, "
                     "not on finished; the queue grows as deeper pages are found")
    def cadence(label, end_key):
        spans = []
        for s in siblings or []:
            a, b = _iso(s.get("date_launched")), _iso(s.get(end_key))
            if a and b and b > a and s.get("slug") != detail.get("slug"):
                spans.append((b - a).total_seconds())
        if not spans:
            return (f"{label}: no cadence -- the /light siblings carry no "
                    f"date_launched/{end_key} pair to time")
        spans.sort()
        median = spans[len(spans) // 2]
        eta = launched + timedelta(seconds=median)
        return (f"{label}: {eta.strftime('%Y-%m-%dT%H:%MZ')} "
                f"({eta.astimezone().strftime('%a %b %d %H:%M %Z')}) by cadence -- "
                f"median of {len(spans)} sibling(s), {median / 86400:.1f} d from launch")
    if launched and not crawl_done:
        lines.append(cadence("crawl done", "date_crawl_done"))
    if launched and not finished:
        lines.append(cadence("finished", "date_finished"))
    if crawl_done:
        lines.append(f"crawl done: {crawl_done.isoformat()}")
    if finished:
        lines.append(f"finished: {finished.isoformat()}")
    return lines


def fetch_analysis(client, org, project, slug, max_items, grep=None):
    """FETCH mode, org/project/analysis: one crawl's status and live counters.

    THE RUNNING CRAWL IS NOT IN THE LIST (witnessed 2026-09-10): the /light
    listing returned five `success` rows for a project whose app page said a
    sixth analysis was running, so LIST cannot answer the morning question,
    "is it done yet", and the answer needs a FETCH by slug. Two calls: the
    analysis detail (status and dates) and its crawl_statistics -- the same
    endpoint the live-stats page's own SPA polls, witnessed in that page's
    wire truth as /analyses/<org>/<project>/<slug>/crawl_stati... and cut off
    there by the lens, which is why the second call tolerates a non-200 and
    prints it instead of dying: a wrong path is a receipt, not a crash.

    SHAPE-AGNOSTIC BY DESIGN, the extract_username() posture: every
    top-level scalar prints as key: value and every container as its size,
    so an unfamiliar payload SHOWS rather than vanishes, and the receipt
    teaches the field names for any later tightening.

    TIGHTENED 2026-09-10 FROM THAT FIRST RECEIPT: the running crawl read
    status crawling, date_launched 2026-09-07T14:00:31Z, and in
    crawl_statistics pages_dones 10,954,595 of pages_known 11,983,866 at
    depth_current 6 -- 37.7 URLs/s against a 40/s cap, JS rendering and all.
    ## Verdict now leads (crawl_verdict); ## Analysis prints only
    ANALYSIS_KEYS, with the full scalar dump as the fallback when none of
    them exist; the crawl_statistics dump stays whole because every one of
    its ten keys is a counter a human reads. A third bounded call reads the
    six newest /light siblings for the cadence clock, and a failure there
    costs the eta line, never the verdict. The light rows carried no
    date_crawl_done (2026-09-10), so up to three detail fetches on the newest
    siblings supply the crawl-done clock; --grep then prints every leaf path
    in the detail matching -- the generic "where does this config live".
    """
    base = f"{API_BASE}/analyses/{org}/{project}/{slug}"
    detail = get_json(client, base)
    stats, stats_note = {}, None
    resp = client.get(f"{base}/crawl_statistics")
    if resp.status_code != 200:
        stats_note = f"HTTP {resp.status_code} from {base}/crawl_statistics -- {resp.text[:200]!r}"
    else:
        try:
            stats = resp.json()
        except ValueError:
            stats_note = "crawl_statistics answered 200 but not JSON"
    if not isinstance(stats, dict):
        stats = {}
    try:
        siblings = follow_pages(client, f"{API_BASE}/analyses/{org}/{project}/light", 6)
    except SystemExit:
        siblings = []
    # THE LIGHT ROWS CARRY NO date_crawl_done (receipt 2026-09-10): /light
    # timed the finished clock and left the crawl-done clock blank. Three
    # detail fetches on the newest finished siblings supply it -- bounded,
    # tolerant, and only when the light rows lack it, so the morning command
    # drops back to three calls the day the light endpoint carries the field.
    if siblings and not any(_iso(s.get("date_crawl_done")) for s in siblings):
        for s in [x for x in siblings if x.get("slug") and x.get("slug") != slug][:3]:
            r = client.get(f"{API_BASE}/analyses/{org}/{project}/{s['slug']}")
            if r.status_code != 200:
                continue
            try:
                full = r.json()
            except ValueError:
                continue
            if isinstance(full, dict):
                s["date_crawl_done"] = full.get("date_crawl_done")
                s.setdefault("date_launched", full.get("date_launched"))
    print(f"# Botify analysis {org}/{project}/{slug}\n")
    print("## Verdict")
    for line in crawl_verdict(detail, stats, siblings):
        print(line)
    print("\n## Analysis")
    curated = [(key, detail.get(key)) for key in ANALYSIS_KEYS if key in detail]
    for key, value in curated or scalar_rows(detail, max_items):
        print(f"{key}: {value}")
    print("\n## Crawl statistics")
    if stats_note:
        print(f"({stats_note})")
    for key, value in scalar_rows(stats, max_items):
        print(f"{key}: {value}")
    if grep:
        hits, total = grep_tree(detail, grep, max_items)
        print(f"\n## grep {grep!r}: {len(hits)} of {total} leaf(ves) in the analysis detail   (path: value)")
        for path, value in hits:
            print(f"{path}: {value}")
    print(f"\n# Next: python connectors/botify.py {org}/{project}   (every finished analysis)")


def row_label(item):
    """(ident, date, name) for one list row from whichever keys it carries:
    the ident is what the # Next: FETCH takes, the date is what a human
    sorts by, the name is what they recognize. Generic by design."""
    def first(keys, width=None):
        for k in keys:
            v = item.get(k)
            if v not in (None, "", [], {}):
                return str(v)[:width] if width else str(v)
        return ""
    return (first(("uuid", "id", "slug")) or "?",
            first(("modified_date", "date_finished", "date", "created_date"), 10),
            first(("name", "slug", "id")))


def dump_item(obj, max_items):
    """One object in full: scalars as rows, then each non-empty container as
    its JSON on one line, capped -- the shape a saved explorer's `query` or
    a collection's datamodel needs, with the cap visible, never silent."""
    if not isinstance(obj, dict):
        print(json.dumps(obj, indent=2, default=str)[:max_items * 200])
        return
    containers = []
    for key, value in obj.items():
        if isinstance(value, (dict, list)):
            if value:
                containers.append((key, value))
        else:
            print(f"{key}: {value}")
    for key, value in containers[:max_items]:
        text = json.dumps(value, default=str)
        print(f"\n## {key}")
        print(text[:2000] + (f" ... (+{len(text) - 2000} chars)" if len(text) > 2000 else ""))
    if len(containers) > max_items:
        print(f"\n# ... +{len(containers) - max_items} more container(s) (raise -n/--max)")


def grep_tree(obj, needle, cap):
    """FIND, generic: every leaf of a JSON tree whose dotted path or value
    contains needle (case-insensitive), as (path, value) pairs, capped at
    cap with the uncapped total returned beside them so a cut is visible.
    Written 2026-09-10 because a collection datamodel and an analysis
    config are both one object thousands of leaves deep, and "where in
    here is the link attribute" is a question about paths, not rows.
    EARMARK (dismount 2026-09-10): a str leaf that is itself serialized JSON
    is opaque here. config.extra_admin_config matched 'link' somewhere past
    the 160-char display cut and could not be descended, and that leaf is
    the one candidate home for the custom link-attribute definitions this
    hunt stopped short of; the `previous` subtree, the prior analysis riding
    inside the current one, also spent 30 rows of a 40-row cap on echoes.
    The cure is a second pass -- a str leaf that starts with '{' or '[' and
    parses walks its parse under the same path -- plus a way to skip a
    subtree. Neither landed; the ad hoc crawl article owns them."""
    needle = needle.lower()
    hits = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        else:
            text = json.dumps(node, default=str)
            if needle in path.lower() or needle in text.lower():
                hits.append((path, text[:160]))

    walk(obj, "")
    return hits[:cap], len(hits)


def walk_path(client, org, project, rest, max_items, grep=None):
    """DRILL-DOWN, generic: any path under a project or an analysis, rendered
    by shape, never by name.

    KEEP IT GENERIC (the operator's rule, 2026-09-10): no object path is
    hardwired here. org/project/<resource> GETs
    /projects/<org>/<project>/<resource>; org/project/<slug>/<sub> GETs
    /analyses/<org>/<project>/<slug>/<sub>; a trailing ?k=v rides as query
    parameters. Every sub-resource the app's own frame was seen calling
    (saved_explorers, collections, datasources, events, jobs) and every one
    it was not is therefore one argument away. A list renders as
    ident | date | name rows with a # Next: that names the FETCH; a single
    object renders through dump_item. --grep narrows a list by
    case-insensitive substring over each row's whole JSON, which is how 667
    saved explorers become the few about links without anyone reading 667
    names. The cap is -n; a paginated envelope says when more pages exist.
    On a single object --grep switches from dump to FIND: every leaf whose
    dotted path or value contains the needle, as path: value, bounded by -n.
    """
    joined = "/".join(rest)
    path, _, qs = joined.partition("?")
    params = dict(parse_qsl(qs)) if qs else None
    segs = [p for p in path.split("/") if p]
    if segs and segs[0].isdigit():
        url = f"{API_BASE}/analyses/{org}/{project}/" + "/".join(segs)
    else:
        url = f"{API_BASE}/projects/{org}/{project}/" + "/".join(segs)
    data = get_json(client, url, params=params)
    print(f"# Botify {org}/{project}/{joined}\n")
    rows = None
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and isinstance(data.get("results"), list):
        rows = data["results"]
    if rows is None:
        if grep:
            hits, total = grep_tree(data, grep, max_items)
            print(f"# {len(hits)} of {total} leaf(ves) matching {grep!r}   (path: value)\n")
            for path, value in hits:
                print(f"{path}: {value}")
            return
        dump_item(data, max_items)
        return
    total = len(rows)
    if grep:
        needle = grep.lower()
        rows = [r for r in rows if needle in json.dumps(r, default=str).lower()]
    shown = rows[:max_items]
    tally = f"# {len(shown)} of {len(rows)} row(s)"
    if grep:
        tally += f" matching {grep!r} ({total} before the grep)"
    print(tally + "   (ident | date | name)\n")
    for r in shown:
        if isinstance(r, dict):
            ident, date, name = row_label(r)
            print(f"{ident}  {date}  {name}")
        else:
            print(json.dumps(r, default=str)[:200])
    if isinstance(data, dict) and data.get("next"):
        print("\n# (more pages exist on the server; this printed the first)")
    print(f"\n# Next: python connectors/botify.py {org}/{project}/{'/'.join(segs)}/<ident>   (one item in full)")


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
# Census (the admin export door)
# ----------------------------------------------------------------------------
# TWO PULLS PER PROJECT (wire-proved 2026-09-23).
#   1. SiteCrawler: GET the server-rendered Advanced Settings document and read
#      only textarea[name=extra_admin_config] -> beta.pap_mini_rules and
#      ftl.websiteID. The same blob contains credential material, so the whole
#      object must never be persisted.
#   2. SpeedWorkers: use ftl.websiteID against Activation GraphQL. The direct
#      productionVersion -> configs/sections optimization answered HTTP 400, so
#      resolve productionVersion.id first, then fetch websiteVersion(id) in a
#      second POST. One warmed Botify cookie jar authenticates both products.
ADMIN_PROJECTS = "https://app.botify.com/admin/projects/project"
ACTIVATION_GRAPHQL = "https://api.activation.botify.com/graphql"

# Cut from the SAMPLE ROW this prints, never from the file on disk. The file is
# the corpus and keeps everything; stdout rides into a compiled payload, so the
# columns that name a client are shown as <cut> there and nowhere else.
CENSUS_CUT = ("project_links", "webproperty_link", "scope",
              "subscription_details", "automated_export_target")

# Same courtesy-sound convention already proved by the scraper. Keep the wavs
# outside git under ~/.local/share/pipulate/. Missing sound is non-fatal but
# LOUD so "file absent", "player absent", and "sound happened" are different
# worlds. This local copy is intentional until tools/scraper_tools.py is in a
# compile beside us and the second consumer can be factored without guessing.
SOUND_ROOT = Path.home() / ".local" / "share" / "pipulate"


def _sound_args(name):
    path = SOUND_ROOT / name
    if not path.is_file():
        return None, f"missing {path}"

    if sys.platform == "darwin":
        player = shutil.which("afplay")
        if player:
            return [player, str(path)], None
        return None, "afplay not found"

    for command in ("pw-play", "paplay", "aplay"):
        player = shutil.which(command)
        if player:
            return [player, str(path)], None
    return None, "no pw-play, paplay, or aplay found"


def _play_sound(name, wait=False):
    args, problem = _sound_args(name)
    if not args:
        sys.stderr.write(f"  sound skipped: {name} ({problem})\n")
        return None
    sys.stderr.write(f"  sound: {name}\n")
    try:
        if wait:
            subprocess.run(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False)
            return None
        return subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        sys.stderr.write(f"  sound failed: {name} ({exc})\n")
        return None


def _stop_sound(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        proc.kill()


# THE LOOP CONTRACT (operator ruling, 2026-09-23): the bulk pull over the
# census queue is IDEMPOTENT CHUNKS, never keep-awake. No caffeinate, no
# nohup. One file per project per pull under data/botify_pulls/ORG/PROJECT/,
# written to a temp name then renamed, so the file existing means done. A
# clean absence (no SpeedWorkers, empty config) writes {"absent": true} and
# is also done. A transient error (5xx, timeout, dropped wifi) writes
# nothing and the next run retries it. An auth failure stops the run, marks
# nothing, and exits nonzero. Every run takes a bounded --limit and ends
# with one line: queue, done, written, absent, errored, remaining. Finished
# is remaining 0, reached by typing the same command again.


def _admin_cookies(profile_name, headless=False):
    # THE WRAPPER IS NOT THE MEASUREMENT. The export POST prints its own
    # elapsed; this half did not, so 6 minutes of headful Chrome hid inside
    # a shell `real` and got misread as export cost. Second clock, same rule.
    import time as _t
    _t0 = _t.monotonic()
    sys.stderr.write(
        f"  harvesting the admin cookie: profile={profile_name!r}, "
        f"headless={headless}\n"
        "  undetected-chromedriver launches a real Chrome. On cafe wifi this\n"
        "  took about 6 minutes on 2026-09-22. It is SETUP, not the export.\n"
        "  LET IT RUN.\n")
    try:
        return _admin_cookies_inner(profile_name, headless=headless)
    finally:
        sys.stderr.write(
            f"  cookie harvest finished in {_t.monotonic() - _t0:.1f}s\n")


def _admin_cookies_inner(profile_name, headless=False):
    """Session cookies from weblogin's warmed uc profile: one launch, then done.

    THE EXPORT IS AN ORDINARY FORM POST, so a browser is needed for exactly one
    thing -- the sessionid weblogin parked in data/uc_profiles/<name>. No API
    token is involved anywhere in this lane: BOTIFY_API_TOKEN read ABSENT on the
    machine this was written for (probe, 2026-09-21) and the census works
    regardless, which is the whole point. The token cannot enumerate; the cookie
    can.
    CHROME LOCKS THE PROFILE, so a window still open from weblogin makes this
    fail, and the error says which door to close rather than leaving the
    operator to guess at a selenium traceback.
    """
    import re
    import undetected_chromedriver as uc

    profile_path = project_root / "data" / "uc_profiles" / profile_name
    if not profile_path.exists():
        sys.stderr.write(
            f"No warmed profile at {profile_path}.\n"
            f"Run: weblogin --profile {profile_name} app.botify.com\n")
        sys.exit(1)

    browser_path = None
    if sys.platform == "darwin":
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ):
            if Path(candidate).exists():
                browser_path = candidate
                break

    def launch(version_main=None):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return uc.Chrome(options=options, user_data_dir=str(profile_path),
                         browser_executable_path=browser_path,
                         version_main=version_main)

    driver = None
    try:
        try:
            driver = launch()
        except Exception as exc:
            found = re.search(r"Current browser version is (\d+)", str(exc))
            if not found:
                raise
            driver = launch(version_main=int(found.group(1)))
        driver.get(f"{ADMIN_PROJECTS}/")
        landed = driver.current_url
        jar = {c["name"]: c["value"] for c in driver.get_cookies()}
        # THE HEADFUL WINDOW NOBODY COULD SEE (2026-09-21). Headful was made
        # the default so a human could look at the page, and then driver.quit()
        # fired one line later, so the window flashed and died. Set CENSUS_HOLD
        # to a number of seconds to actually look at it:
        #   CENSUS_HOLD=20 .venv/bin/python connectors/botify.py --census --q X
        # An env var on purpose: no signature, no argparse, no call site,
        # nothing to thread wrong. The float parse owns its own failure so a
        # typo cannot surface as "could not read cookies" from the outer try.
        try:
            hold = float(os.environ.get("CENSUS_HOLD") or 0)
        except ValueError:
            hold = 0.0
        if hold:
            import time
            sys.stderr.write(f"  holding the window open {hold}s -- look at it\n")
            time.sleep(hold)
    except Exception as exc:
        sys.stderr.write(
            f"Could not read cookies from {profile_path}: {exc}\n"
            "Close any Chrome window still open on that profile, then retry.\n")
        sys.exit(1)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    # THE GUARD NAMED A COOKIE IT NEVER VERIFIED (convicted 2026-09-21, by the
    # refusal written one turn earlier expressly to be readable). "sessionid"
    # is Django's DEFAULT session cookie name. Botify sets SESSION_COOKIE_NAME,
    # so the jar comes back carrying botify_sid and this guard refused a
    # session that was working. The receipt that convicted it is the refusal's
    # own first line: the load STAYED on app.botify.com/admin/projects/project/.
    # An anonymous Django admin request REDIRECTS to a login page. It did not
    # redirect. Both branches of that refusal were therefore wrong, because
    # both assumed the NAME was right and only the world was in question.
    # THE RULE: do not assert a vendor default you have never read. Test the
    # thing you actually want. What is wanted is a warm admin page, so test
    # that the load is still ON the admin and the jar is not empty, and let
    # the export form's own presence downstream be the authentication verdict.
    if not jar or "/admin/projects/project" not in landed:
        # THE REFUSAL MUST NAME WHAT IT SAW (convicted 2026-09-21, by the very
        # first smoke this guard ever fired on). The original line said only
        # "the warm has expired", so the operator re-ran weblogin, WATCHED IT
        # COME UP ALREADY LOGGED IN, ran the census again, and got the identical
        # sentence. One message for two different worlds: a genuinely cold
        # profile, and a warm profile whose session THIS LAUNCH could not see.
        # THE DISCRIMINATION QUESTION failing inside a guard's own error text,
        # which is the shape this repo keeps convicting everywhere else.
        # The LANDING URL separates them. A bounce off app.botify.com is a
        # session that did not restore; staying on app.botify.com with no
        # sessionid is a cookie store this launch could not read. The cookie
        # NAMES say which jar came back. Names only, never values: a name is a
        # diagnosis and a value is a credential.
        host = urlparse(landed).netloc or "(unknown)"
        sys.stderr.write(
            "The admin did not open a warm session.\n"
            f"  landed on : {landed}\n"
            f"  cookies   : {', '.join(sorted(jar)) or '(none)'}\n")
        if "botify.com" not in host:
            sys.stderr.write(
                "  reading   : the load bounced OFF app.botify.com, so the "
                "session did not restore in this launch.\n"
                "              Retry WITHOUT --headless; headful is the lane "
                "weblogin and ?URL both use and both prove.\n")
        else:
            sys.stderr.write(
                "  reading   : it stayed on botify.com but never reached the "
                "admin changelist, so this session is not authenticated for "
                "the admin, or the admin moved.\n")
        sys.stderr.write(
            f"  if truly cold: weblogin --profile {profile_name} app.botify.com\n")
        sys.exit(1)
    return jar


class PullAuthError(RuntimeError):
    """The warmed Botify session is no longer accepted."""


class PullTransientError(RuntimeError):
    """A retryable network/server failure; write no completion marker."""


class PullDataError(RuntimeError):
    """A non-auth response whose shape cannot be safely interpreted."""


def _atomic_json(path, payload):
    """Write one completion artifact atomically; existence means done."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _pull_response(client, method, url, **kwargs):
    """One HTTP call with Loop Contract error classes."""
    try:
        response = client.request(method, url, **kwargs)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PullTransientError(str(exc)) from exc
    if response.status_code in (401, 403):
        raise PullAuthError(f"HTTP {response.status_code} for {url}")
    if 300 <= response.status_code <= 399:
        location = response.headers.get("location", "")
        if "login" in location.lower() or "auth" in location.lower():
            raise PullAuthError(
                f"HTTP {response.status_code} redirect to {location!r}")
        raise PullDataError(
            f"HTTP {response.status_code} redirect to {location!r}")
    if 500 <= response.status_code <= 599:
        raise PullTransientError(f"HTTP {response.status_code} for {url}")
    if response.status_code != 200:
        raise PullDataError(f"HTTP {response.status_code} for {url}")
    return response


def _activation_data(client, query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = _pull_response(
        client, "POST", ACTIVATION_GRAPHQL,
        headers={"Origin": "https://app.botify.com",
                 "Referer": "https://app.botify.com/"},
        json=payload,
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise PullDataError("Activation GraphQL answered 200 but not JSON") from exc
    errors = body.get("errors") if isinstance(body, dict) else None
    if errors:
        message = "; ".join(
            str(e.get("message", e)) if isinstance(e, dict) else str(e)
            for e in errors
        )
        lowered = message.lower()
        if any(word in lowered for word in
               ("auth", "forbidden", "permission", "credential", "login")):
            raise PullAuthError(f"Activation GraphQL: {message[:300]}")
        raise PullDataError(f"Activation GraphQL: {message[:300]}")
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise PullDataError("Activation GraphQL returned no data object")
    return data


def _sitecrawler_config(client, org, project):
    """Whitelist the two non-secret fields proved in extra_admin_config."""
    import lxml.etree
    import lxml.html

    url = f"https://app.botify.com/spa/{org}/{project}/settings/crawler/advanced"
    response = _pull_response(client, "GET", url)
    try:
        doc = lxml.html.fromstring(response.text)
    except (ValueError, lxml.etree.ParserError) as exc:
        raise PullDataError("SiteCrawler Advanced answered invalid HTML") from exc

    fields = doc.xpath('//textarea[@name="extra_admin_config"]')
    if len(fields) != 1:
        raise PullDataError(
            f"expected one extra_admin_config textarea, found {len(fields)}")

    raw = fields[0].text_content().strip()
    if not raw:
        return {"absent": True}
    try:
        config = json.loads(raw)
    except ValueError as exc:
        raise PullDataError("extra_admin_config is not valid JSON") from exc
    if not isinstance(config, dict):
        raise PullDataError("extra_admin_config is not a JSON object")

    safe = {}
    beta = config.get("beta")
    rules = beta.get("pap_mini_rules") if isinstance(beta, dict) else None
    if rules not in (None, []) and not isinstance(rules, list):
        raise PullDataError("beta.pap_mini_rules is not a list")
    if rules:
        safe["beta"] = {"pap_mini_rules": rules}

    ftl = config.get("ftl")
    website_id = ftl.get("websiteID") if isinstance(ftl, dict) else None
    if website_id is not None and not isinstance(website_id, str):
        raise PullDataError("ftl.websiteID is not a string")
    if website_id:
        safe["ftl"] = {"websiteID": website_id}

    return safe or {"absent": True}


def _speedworkers_config(client, website_id):
    """Read the production graph in two POSTs; the one-POST shortcut is invalid."""
    website_literal = json.dumps(website_id)
    version_data = _activation_data(
        client,
        f"""query {{
          website(id: {website_literal}) {{
            id
            productionVersion {{ id version }}
          }}
        }}""",
    )
    website = version_data.get("website")
    if not isinstance(website, dict):
        raise PullDataError("Activation website lookup returned no website")
    production = website.get("productionVersion")
    if production is None:
        return {"absent": True}
    if not isinstance(production, dict) or not production.get("id"):
        raise PullDataError("productionVersion has no id")

    version_literal = json.dumps(production["id"])
    detail_data = _activation_data(
        client,
        f"""query {{
          websiteVersion(id: {version_literal}) {{
            id
            version
            isProductionVersion
            configs {{
              id
              name
              renderingRules
            }}
            sections(includeDeleted: true) {{
              id
              stableId
              deletedAt
              name
              rules
              desktopConfig {{ id name }}
              mobileConfig {{ id name }}
            }}
          }}
        }}""",
    )
    version = detail_data.get("websiteVersion")
    if not isinstance(version, dict):
        raise PullDataError("production websiteVersion lookup returned no version")
    if version.get("isProductionVersion") is not True:
        raise PullDataError(
            f"websiteVersion {version.get('id')!r} is not marked production")

    configs = [
        {"id": item.get("id"),
         "name": item.get("name"),
         "renderingRules": item.get("renderingRules")}
        for item in (version.get("configs") or [])
        if isinstance(item, dict)
    ]
    sections = []
    for item in version.get("sections") or []:
        if not isinstance(item, dict) or item.get("deletedAt"):
            continue
        desktop = item.get("desktopConfig")
        mobile = item.get("mobileConfig")
        sections.append({
            "id": item.get("id"),
            "stableId": item.get("stableId"),
            "name": item.get("name"),
            "rules": item.get("rules"),
            "desktopConfig": (
                {"id": desktop.get("id"), "name": desktop.get("name")}
                if isinstance(desktop, dict) else None
            ),
            "mobileConfig": (
                {"id": mobile.get("id"), "name": mobile.get("name")}
                if isinstance(mobile, dict) else None
            ),
        })

    if not configs and not sections:
        return {"absent": True}
    return {
        "website": {"id": website_id},
        "productionVersion": {
            "id": version.get("id"),
            "version": version.get("version"),
        },
        "configs": configs,
        "sections": sections,
    }


def _pull_summary(rows, root, written, absent, errored):
    done = 0
    for row in rows:
        base = root / row["org"] / row["project"]
        if ((base / "sitecrawler.json").exists()
                and (base / "speedworkers.json").exists()):
            done += 1
    total = len(rows)
    print(f"queue={total} done={done} written={written} absent={absent} "
          f"errored={errored} remaining={total - done}")


def pull_configs(queue_path, limit, profile_name="botify", headless=False):
    """Run a bounded, resumable two-file config pull over the census queue."""
    queue = Path(queue_path).expanduser()
    if not queue.is_absolute():
        queue = project_root / queue
    if not queue.exists():
        sys.stderr.write(f"Queue not found: {queue}\n")
        return 1
    if limit < 1:
        sys.stderr.write("--limit must be at least 1\n")
        return 1

    rows = []
    try:
        with queue.open(encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if (not isinstance(row, dict)
                        or not all(row.get(k) not in (None, "")
                                   for k in ("id", "org", "project"))):
                    raise ValueError(
                        f"line {lineno} needs id, org, project")
                rows.append({k: row[k] for k in ("id", "org", "project")})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Could not read queue {queue}: {exc}\n")
        return 1

    root = project_root / "data" / "botify_pulls"
    pending = []
    for row in rows:
        base = root / row["org"] / row["project"]
        if not ((base / "sitecrawler.json").exists()
                and (base / "speedworkers.json").exists()):
            pending.append(row)
            if len(pending) >= limit:
                break

    if not pending:
        _pull_summary(rows, root, 0, 0, 0)
        return 0

    try:
        cookies = _admin_cookies(profile_name, headless=headless)
    except SystemExit as exc:
        _pull_summary(rows, root, 0, 0, 0)
        return int(exc.code or 1)

    written = absent = errored = 0
    auth_failed = False
    with httpx.Client(cookies=cookies, timeout=60.0,
                      follow_redirects=False) as client:
        for row in pending:
            base = root / row["org"] / row["project"]
            site_path = base / "sitecrawler.json"
            sw_path = base / "speedworkers.json"

            if site_path.exists():
                try:
                    site = json.loads(site_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    errored += 1
                    sys.stderr.write(
                        f"project {row['id']}: existing SiteCrawler artifact "
                        f"is unreadable: {exc}\n")
                    continue
            else:
                try:
                    site = _sitecrawler_config(
                        client, row["org"], row["project"])
                except PullAuthError as exc:
                    sys.stderr.write(
                        f"project {row['id']}: authentication failed: {exc}\n")
                    auth_failed = True
                    break
                except (PullTransientError, PullDataError) as exc:
                    errored += 1
                    sys.stderr.write(
                        f"project {row['id']}: SiteCrawler pull failed: {exc}\n")
                    continue
                _atomic_json(site_path, site)
                if site.get("absent") is True:
                    absent += 1
                else:
                    written += 1

            if sw_path.exists():
                continue

            website_id = None
            if isinstance(site, dict):
                ftl = site.get("ftl")
                if isinstance(ftl, dict):
                    website_id = ftl.get("websiteID")
            if not website_id:
                errored += 1
                sys.stderr.write(
                    f"project {row['id']}: no ftl.websiteID; "
                    "SpeedWorkers remains unresolved and unmarked\n")
                continue

            try:
                speedworkers = _speedworkers_config(client, website_id)
            except PullAuthError as exc:
                sys.stderr.write(
                    f"project {row['id']}: authentication failed: {exc}\n")
                auth_failed = True
                break
            except (PullTransientError, PullDataError) as exc:
                errored += 1
                sys.stderr.write(
                    f"project {row['id']}: SpeedWorkers pull failed: {exc}\n")
                continue

            _atomic_json(sw_path, speedworkers)
            if speedworkers.get("absent") is True:
                absent += 1
            else:
                written += 1

    _pull_summary(rows, root, written, absent, errored)
    return 1 if auth_failed else 0


def census(q=None, profile_name="botify", fmt="json", out_dir=None, max_items=25,
           headless=False, params=None, fields=None, allow_full=False):
    """CENSUS: the whole project table, through the Django admin's export form.

    WHY THE ADMIN AT ALL (witnessed 2026-09-21): the API has no org-listing
    endpoint. 46 swagger paths, and both project endpoints are per-username, so
    a token with across-all-client READ scope still cannot ENUMERATE. The admin
    changelist is the only enumeration surface, django-import-export sits on top
    of it, and its export form inherits the changelist's own querystring -- which
    turns the 859-page pager nobody wrote into one POST.

    NOTHING HERE IS HARDCODED FROM A GREP. The form is fetched and parsed every
    run, so the checkbox names, the hidden `resource` value and the format select
    are read off the live page. That matters: the 2026-09-21 receipt read 28
    checkboxes named projectresource_<field> and a format select whose option
    VALUES are numeric indexes (0-4), NOT format names. Matching the option LABEL
    instead is why a version bump that renumbers them cannot silently export the
    wrong format -- the failure this design exists to refuse.

    BOTH OF THE THINGS THIS DID NOT KNOW ARE NOW ANSWERED (2026-09-21), and
    both answers are receipts rather than inferences.
    ROWS: 85,790 do NOT survive one synchronous request. The unfiltered pull
    answered 502 from nginx, so the guard at the top of this function refuses
    that call and the corpus gets assembled from filtered slices instead.
    THE SLICE THAT WORKS is category__exact, measured rather than hoped:
    category 1 (Web Property) returned 10,880 rows of one column in 67.7
    seconds. That is the SpeedWorkers candidate pool, not the SpeedWorkers
    list -- Web Property is a project TYPE and SpeedWorkers is some subset of
    it. But since SpeedWorkers only lives in Web Property, the Has SW
    changelist filter, whose parameter five instruments failed to name, is an
    optimization nobody needs rather than a blocker. Membership comes from
    somewhere else: the FTL admin lists SpeedWorkers sites on one page, or
    botify_config returns has_speedworkers at one GET per project.
    PROJECT LINKS: it arrives as FLATTENED TEXT and carries nothing but
    "<org-slug>/<project-slug>" -- mikelev.in's row read
    'michaellevin-org/mikelev.in'. The changelist CELL renders five anchors
    (org, project, current settings, Botify Team, SF account id); the EXPORT
    cell keeps only the pair. So the parse is one split on "/", the admin
    project id is the separate `id` column, and the projectsettings id is not
    in the export at all -- which is a relief, since that is the page
    apply.py convicts for sealing credentials into a payload.
    """
    import lxml.html

    # THE UNBOUNDED EXPORT IS A 502 (convicted 2026-09-21, against production).
    # `--census --fields id`, no q and no filter, answered "502 Bad Gateway /
    # nginx". Not our own 300s timeout, which would have raised on this side:
    # nginx reporting that the upstream Django worker died or blew its own
    # gateway limit. ONE SYNCHRONOUS REQUEST DOES NOT CARRY 85,790 ROWS, and
    # narrowing the COLUMNS cannot save it, because --fields narrows what is
    # SERIALIZED and never what is EVALUATED. The queryset is the cost. That
    # is exactly what the id-only dress rehearsal was built to measure, and
    # the measurement came back no.
    # THIS GUARD EXISTS BECAUSE THAT 502 LANDED ON SOMEONE ELSE'S PRODUCTION.
    # An unbounded pull is opt-in from here on, so it cannot be one keystroke
    # away by accident, and the refusal names the only two axes that narrow it.
    if not q and not params and not allow_full:
        sys.stderr.write(
            "Refusing an unfiltered export of the whole project table.\n"
            "  why  : this exact call answered 502 Bad Gateway from nginx on "
            "2026-09-21; one request does not survive 85,790 rows.\n"
            "  fix  : scope it with --q <term>, or narrow it with "
            "--param <filter>=<value>.\n"
            "  force: --all, to try the whole table anyway.\n")
        sys.exit(1)

    url = f"{ADMIN_PROJECTS}/export/"
    cookies = _admin_cookies(profile_name, headless=headless)
    with httpx.Client(cookies=cookies, timeout=300.0, follow_redirects=True) as client:
        # THE EXPORT INHERITS THE CHANGELIST QUERYSTRING, so any changelist
        # filter rides here as an ordinary parameter. `?q=` is proven by the
        # export link's own href. `category__exact` is a registered list_filter
        # witnessed in a Confluence URL (_changelist_filters=q%3D...%26
        # category__exact%3D1) and is therefore a receipt, not a guess, but no
        # OTHER filter key has been read off anything. That is why this is a
        # passthrough and not a menu: a wrong key changes nothing, and the row
        # count not moving is the receipt that it did not take.
        query = dict(params or {})
        if q:
            query["q"] = q
        page = client.get(url, params=query or None)
        if page.status_code != 200:
            sys.stderr.write(f"HTTP {page.status_code} for {url}\n{page.text[:300]}\n")
            sys.exit(1)
        # PROVEN-LIVE FILTER KEYS (receipts, 2026-09-21, against production):
        #   category__exact=1  -- accepted, no ?e=1, returned mikelev.in
        # Everything else is a guess, and THE 500 IS THE OTHER OUTCOME
        # (convicted 2026-09-21, one turn after the ?e=1 guard was written).
        # Four guessed keys -- has_sw__exact, has_pw__exact,
        # has_speedworkers__exact, speedworkers__isnull -- did NOT redirect to
        # ?e=1. Every one answered HTTP 500 with Botify's own error page on
        # the GET. The changelist catches IncorrectLookupParameters and
        # redirects; THIS view, django-import-export's export, does not, and
        # an unregistered key reaches the ORM and dies there.
        # THE CORRECTION: the ?e=1 guard makes a wrong key VISIBLE, never
        # cheap. Each guess costs a 500 on someone else's production. Do not
        # brute-force filter names. A key gets tried only after it has been
        # READ off a live page, and the Has SW filter is an ARIA widget with
        # no name attribute in source.html OR hydrated_dom.html, so no such
        # reading exists.
        # MEASURED CEILING (2026-09-21): category__exact=1, --fields id, no q
        # -- 10,880 rows in 67.7s wall. The unbounded pull is about eight
        # times that queryset, which is what the 502 was. 67.7s also sits
        # close to whatever gateway limit killed it, so a slice that adds
        # per-row related lookups can still die.
        # THE SECOND MEASUREMENT WAS INTERRUPTED, NOT REFUSED (2026-09-22).
        # The same slice with --fields id,project_links was still alive at 159s
        # when the operator killed it: no 502, no timeout, and `time` read user
        # 0m0.567s, so the entire wait was server-side. 2m39s therefore proves
        # only that this call costs MORE than 67.7s. It is an open measurement,
        # not a ceiling, and the next run of it must be allowed to finish or to
        # time out on its own.
        # A WRONG FILTER KEY MUST REFUSE, NOT WIDEN (guard written 2026-09-21,
        # before --param was ever used in anger). Django's ChangeList raises
        # IncorrectLookupParameters for any querystring key that is not a
        # registered list_filter, and the admin catches it and REDIRECTS to
        # ?e=1 -- which is a 200, renders the export form, and would export the
        # UNFILTERED queryset. A typo would therefore become the 502 above, or
        # worse, a quietly complete export wearing a filter's label. The
        # redirect is visible in page.url and nowhere else, so read it.
        if "e=1" in str(page.url):
            sys.stderr.write(
                f"The admin rejected a querystring parameter: {page.url}\n"
                "  Django redirects to ?e=1 when a key is not a registered\n"
                "  list_filter, so one of these is not a real filter name:\n"
                f"  {sorted(query)}\n")
            sys.exit(1)
        doc = lxml.html.fromstring(page.text)
        form = None
        for candidate in doc.forms:
            if candidate.xpath('.//select[@name="format"]'):
                form = candidate
                break
        if form is None:
            sys.stderr.write(
                f"No export form at {page.url} -- a login wall, or the admin moved.\n"
                f"Re-run: weblogin --profile {profile_name} app.botify.com\n")
            sys.exit(1)

        data, checkboxes = {}, 0
        for el in form.xpath('.//input'):
            name = el.get("name")
            kind = (el.get("type") or "text").lower()
            if not name or name == "select-all-toggle":
                continue
            if kind == "checkbox":
                # A NARROWED EXPORT IS THE CHEAP DRESS REHEARSAL (2026-09-21).
                # One row of all 28 fields was 842 bytes, so the whole table is
                # roughly 69 MB through one synchronous request, and every one
                # of those rows builds a marked-safe HTML cell with related
                # lookups behind it. Exporting the id alone answers BOTH open
                # questions -- does one request survive the whole table, and
                # what is the true row count -- for about 1.7 MB. An unchecked
                # box is simply not submitted, which is what `continue` does
                # here. The names come off the LIVE form, so a --fields value
                # matching nothing yields zero columns, and the guard below
                # refuses rather than shipping a silent partial export.
                if fields and name.split("projectresource_", 1)[-1] not in fields:
                    continue
                data[name] = el.get("value") or "on"
                checkboxes += 1
            elif kind in ("hidden", "text"):
                data[name] = el.get("value") or ""

        if fields and not checkboxes:
            sys.stderr.write(
                f"--fields {sorted(fields)} matched none of the form's "
                "checkboxes, so the POST would export zero columns.\n"
                "Run once without --fields and read the column names off the "
                "sample row.\n")
            sys.exit(1)

        choices = [(o.get("value"), (o.text or "").strip())
                   for o in form.xpath('.//select[@name="format"]//option')]
        picked = next((v for v, label in choices if label.lower() == fmt.lower()), None)
        if picked is None:
            sys.stderr.write(f"Format {fmt!r} is not offered here. Options: {choices}\n")
            sys.exit(1)
        data["format"] = picked

        action = form.get("action") or ""
        post_url = str(httpx.URL(str(page.url)).join(action)) if action else str(page.url)
        # THE SILENT WAIT INVITES THE CTRL-C (convicted 2026-09-22, at an
        # internet cafe on a borrowed hour). From the browser flash to the
        # first line of output this function printed NOTHING, and the export
        # POST is one blocking request that can run for minutes. The operator
        # watched a dead terminal and killed a run at 2m39s. It was not
        # failing: `time` read user 0m0.567s, so our side was idle and the
        # server was still working, well inside the 300s client timeout. A
        # measurement was lost to silence rather than to an error.
        # THE RULE: a call that can outlast a human's patience says so BEFORE
        # it blocks, names the wait it already knows about, and prints its own
        # elapsed time when it returns. stderr, so stdout stays payload-clean.
        import time as _time
        _started = _time.monotonic()
        sys.stderr.write(
            f"  posting the export: {checkboxes} field(s), q={q!r}, "
            f"filters={sorted(query)}\n"
            "  ONE blocking request, server-side. 10,880 rows of one column\n"
            "  took 67.7s on 2026-09-21; more columns cost more. The client\n"
            "  timeout is 300s and it will fire on its own.\n"
            "  LET IT RUN. Ctrl-C throws away the measurement.\n")
        resp = client.post(post_url, data=data, headers={"Referer": str(page.url)})
        sys.stderr.write(
            f"  export POST returned in {_time.monotonic() - _started:.1f}s\n")

    if resp.status_code != 200:
        sys.stderr.write(f"HTTP {resp.status_code} on the export POST\n{resp.text[:300]}\n")
        sys.exit(1)
    ctype = resp.headers.get("content-type", "")
    if "text/html" in ctype and fmt.lower() != "html":
        sys.stderr.write(
            f"The export POST answered with HTML, not a file ({ctype}).\n"
            "That is what a login wall looks like from here; re-run weblogin.\n")
        sys.exit(1)

    target = Path(out_dir) if out_dir else (project_root / "data" / "botify_census")
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = target / f"projects-{stamp}.{fmt}"
    path.write_bytes(resp.content)

    print(f"# Botify project census -> {path}")
    print(f"# {len(resp.content):,} bytes | {checkboxes} field(s) requested | "
          f"format {fmt} (option value {picked!r}) | q={q!r}")
    if fmt.lower() != "json":
        print("\n# Non-JSON format: the file is on disk, no row summary attempted.")
        return
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"\n# The body is not JSON ({exc}); the bytes are on disk regardless.")
        return
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        print(f"\n# Unexpected JSON shape ({type(rows).__name__}); bytes are on disk.")
        return
    columns = list(rows[0])
    print(f"\n## {len(rows):,} row(s), {len(columns)} column(s)")
    print(", ".join(str(c) for c in columns))
    # THE EMPTY BOOLEAN (witnessed 2026-09-21, the first successful export).
    # The columns arrive as snake_case FIELD names, not verbose labels, so this
    # counter fires and no later join needs a name map. But has_sw, has_pw,
    # has_smartcontent and has_smartlink all came back EMPTY on a row where
    # has_la read False and has_rk/ab/ap/ea read True. Empty is not False and
    # it is not None; it is a third thing, and ONE ROW CANNOT TELL "absent
    # means no" from "this column is broken in the export". The counter below
    # scores empty as not-true, which is arithmetically right and semantically
    # unproven, so it now prints the blanks beside the trues instead of hiding
    # them inside a denominator. THE DISCRIMINATING TEST is a row known to
    # carry SpeedWorkers: --q Z9UNVX, carrefour-espana, Has SW True on the
    # changelist. THE TEST RAN AND THE COLUMNS LOST: project 56555 exported
    # has_sw BLANK, identical to the DEMO project that has no SpeedWorkers at
    # all. Two rows, one of them known True, both blank. These four columns
    # are DEAD in the export. In those same two rows has_segmentation and
    # has_la both moved False to True, so booleans are not broken generally;
    # these four are. Probably list_display methods the Resource declares but
    # cannot resolve, serializing as empty rather than raising -- labelled
    # inference, because the receipt is only the two blanks.
    # WHAT REPLACES THEM IS THE FILTER, NOT THE COLUMN. Has SW is a registered
    # changelist list_filter and the export inherits the changelist QUERYSET,
    # so a filtered export returns only SpeedWorkers rows whether or not the
    # column admits it. Naming that filter's querystring parameter is now the
    # one blocking question, and --param is how it gets sent.
    for key in columns:
        flat = str(key).strip().lower().replace(" ", "_")
        if flat in ("has_sw", "has_pw"):
            vals = [str(r.get(key) if r.get(key) is not None else "").strip()
                    for r in rows]
            on = sum(1 for v in vals if v.lower() in ("true", "1", "yes"))
            blank = sum(1 for v in vals if not v)
            print(f"{key}: {on:,} true, {blank:,} blank, "
                  f"{len(rows) - on - blank:,} other, of {len(rows):,}")
    print("\n## one row (client identifiers cut)")
    for key, value in list(rows[0].items())[:max_items]:
        flat = str(key).strip().lower().replace(" ", "_")
        shown = "<cut>" if any(m in flat for m in CENSUS_CUT) else str(value)[:120]
        print(f"{key}: {shown}")
    print(f"\n# The corpus is at {path} and nothing about it rides into a payload.")


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
        help="Nothing (identity walk), 'org', 'org/project', 'org/project/analysis', an app.botify.com URL, or a BQL/JSON query string."
    )
    parser.add_argument('--org', default=os.getenv('BOTIFY_ORG'),
                        help='Org slug for FETCH mode (default: BOTIFY_ORG env).')
    parser.add_argument('--project', default=os.getenv('BOTIFY_PROJECT'),
                        help='Project slug for FETCH mode (default: BOTIFY_PROJECT env).')
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Output cap per THE PROBE ECONOMY RULE (default: 25).')
    parser.add_argument('--grep', default=None,
                        help='DRILL: on a list keep rows whose JSON contains this '
                             'substring; on one object, or after a verdict, print every leaf path matching -- case-insensitive.')
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    parser.add_argument('--census', action='store_true',
                        help='CENSUS: pull the project table through the Django '
                             'admin export form on the warmed weblogin profile. '
                             'Uses a session cookie, never BOTIFY_API_TOKEN.')
    parser.add_argument('--pull-configs', action='store_true',
                        help='PULL-CONFIGS: bounded, resumable SiteCrawler + '
                             'SpeedWorkers extraction from a census queue.')
    parser.add_argument('--queue', default=None,
                        help='PULL-CONFIGS: JSONL queue with id/org/project keys.')
    parser.add_argument('--limit', type=int, default=10,
                        help='PULL-CONFIGS: maximum unfinished projects attempted '
                             'this run (default: 10).')
    parser.add_argument('--q', default=None,
                        help='CENSUS: the changelist search term the export '
                             'inherits (project id/slug, username, SF account id, '
                             'or activation website id).')
    parser.add_argument('--profile', default='botify',
                        help='CENSUS/PULL-CONFIGS: uc profile under data/uc_profiles (default: botify).')
    parser.add_argument('--format', default='json',
                        help='CENSUS: export format, matched against the option '
                             'labels the form itself renders (default: json).')
    parser.add_argument('--out', default=None,
                        help='CENSUS: directory for the corpus file '
                             '(default: data/botify_census, which is gitignored).')
    parser.add_argument('--headless', action='store_true',
                        help='CENSUS/PULL-CONFIGS: run the cookie-harvest browser headless. '
                             'OFF by default so the window can be watched. The '
                             'headless hypothesis for the first failed smoke '
                             'was WRONG -- the guard was looking for a cookie '
                             'name Botify does not use -- but headful is still '
                             'the lane weblogin and ?URL both prove.')
    parser.add_argument('--param', action='append', default=None, metavar='K=V',
                        help='CENSUS: an extra changelist querystring parameter '
                             'the export inherits, repeatable. Example: '
                             '--param category__exact=1. A wrong key changes '
                             'nothing, so compare row counts to prove it took.')
    parser.add_argument('--fields', default=None,
                        help='CENSUS: comma-separated column names to export '
                             '(default: every field the form offers). '
                             '--fields id is the cheap full-pull dress '
                             'rehearsal: the true row count, a fraction of the bytes.')
    parser.add_argument('--all', action='store_true',
                        help='CENSUS: allow an export with no --q and no '
                             '--param. OFF by default because that exact call '
                             'answered 502 from nginx on 2026-09-21.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

    if args.pull_configs:
        if not args.queue:
            sys.stderr.write("--pull-configs requires --queue PATH\n")
            sys.exit(1)
        sys.exit(pull_configs(
            args.queue, args.limit, profile_name=args.profile,
            headless=args.headless))

    if args.census:
        bad = [p for p in (args.param or []) if "=" not in p]
        if bad:
            sys.stderr.write(f"--param needs K=V form, got: {bad}\n")
            sys.exit(1)
        census(q=args.q, profile_name=args.profile, fmt=args.format,
               out_dir=args.out, max_items=args.max, headless=args.headless,
               params=dict(p.split("=", 1) for p in args.param or []),
               fields={f.strip() for f in args.fields.split(",") if f.strip()}
               if args.fields else None,
               allow_full=args.all)
        return

    if args.query:
        args.query = normalize_query(args.query.strip())

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
            elif len(parts) == 2:
                list_analyses(client, parts[0], parts[1], args.max)
            elif len(parts) == 3 and parts[2].isdigit():
                fetch_analysis(client, parts[0], parts[1], parts[2], args.max, args.grep)
            elif len(parts) >= 3:
                walk_path(client, parts[0], parts[1], parts[2:], args.max, args.grep)
            else:
                list_identity(client, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
