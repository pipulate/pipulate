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

CENSUS mode uses NEITHER. It rides the session cookie weblogin parked in
data/uc_profiles/<profile>, because the API cannot enumerate projects at all --
46 swagger paths and both project endpoints per-username. The corpus lands in
data/botify_census/ (gitignored) and only counts and column names reach stdout.

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
ADMIN_PROJECTS = "https://app.botify.com/admin/projects/project"

# Cut from the SAMPLE ROW this prints, never from the file on disk. The file is
# the corpus and keeps everything; stdout rides into a compiled payload, so the
# columns that name a client are shown as <cut> there and nowhere else.
CENSUS_CUT = ("project_links", "webproperty_link", "scope",
              "subscription_details", "automated_export_target")


def _admin_cookies(profile_name, headless=False):
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

    if "sessionid" not in jar:
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
            "No sessionid cookie after loading the admin.\n"
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
                "  reading   : it stayed on app.botify.com and still handed "
                "back no session cookie, so this launch could not read the "
                "profile's cookie store.\n")
        sys.stderr.write(
            f"  if truly cold: weblogin --profile {profile_name} app.botify.com\n")
        sys.exit(1)
    return jar


def census(q=None, profile_name="botify", fmt="json", out_dir=None, max_items=25):
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

    TWO THINGS THIS DOES NOT KNOW, stated rather than assumed. Whether all 85,790
    rows survive one synchronous request: hence --q, to smoke it on a single row
    first, and a 300s timeout. And whether the Project Links column arrives as
    anchor HTML or as flattened text: the file keeps whatever came, and the slug
    parse is a later step that is deliberately not attempted here.
    """
    import lxml.html

    url = f"{ADMIN_PROJECTS}/export/"
    cookies = _admin_cookies(profile_name)
    with httpx.Client(cookies=cookies, timeout=300.0, follow_redirects=True) as client:
        page = client.get(url, params={"q": q} if q else None)
        if page.status_code != 200:
            sys.stderr.write(f"HTTP {page.status_code} for {url}\n{page.text[:300]}\n")
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
                data[name] = el.get("value") or "on"
                checkboxes += 1
            elif kind in ("hidden", "text"):
                data[name] = el.get("value") or ""

        choices = [(o.get("value"), (o.text or "").strip())
                   for o in form.xpath('.//select[@name="format"]//option')]
        picked = next((v for v, label in choices if label.lower() == fmt.lower()), None)
        if picked is None:
            sys.stderr.write(f"Format {fmt!r} is not offered here. Options: {choices}\n")
            sys.exit(1)
        data["format"] = picked

        action = form.get("action") or ""
        post_url = str(httpx.URL(str(page.url)).join(action)) if action else str(page.url)
        resp = client.post(post_url, data=data, headers={"Referer": str(page.url)})

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
    for key in columns:
        flat = str(key).strip().lower().replace(" ", "_")
        if flat in ("has_sw", "has_pw"):
            on = sum(1 for r in rows
                     if str(r.get(key)).strip().lower() in ("true", "1", "yes"))
            print(f"{key}: {on:,} of {len(rows):,}")
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
    parser.add_argument('--q', default=None,
                        help='CENSUS: the changelist search term the export '
                             'inherits (project id/slug, username, SF account id, '
                             'or activation website id).')
    parser.add_argument('--profile', default='botify',
                        help='CENSUS: uc profile under data/uc_profiles (default: botify).')
    parser.add_argument('--format', default='json',
                        help='CENSUS: export format, matched against the option '
                             'labels the form itself renders (default: json).')
    parser.add_argument('--out', default=None,
                        help='CENSUS: directory for the corpus file '
                             '(default: data/botify_census, which is gitignored).')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

    if args.census:
        census(q=args.q, profile_name=args.profile, fmt=args.format,
               out_dir=args.out, max_items=args.max)
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
