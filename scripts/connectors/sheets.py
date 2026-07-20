#!/usr/bin/env python3
# scripts/connectors/sheets.py
"""
sheets.py — A Unix-philosophy gateway to Google Sheets for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/sheets.py                        # IDENTITY: OAuth wiring status; mints the token interactively
  python scripts/connectors/sheets.py <URL-or-ID>            # STACK: every tab's ACTUAL data rectangle, timestamped and stacked vertically with payload-grammar sentinels + clickable per-tab #gid= URLs (over --budget: true-extent gauge instead)
  python scripts/connectors/sheets.py <URL-or-ID> --list     # LIST: metadata-only gauge (grid ALLOCATION, zero cell data fetched)
  python scripts/connectors/sheets.py <URL-or-ID> --sheet Metrics             # FETCH: first --max rows of one named tab
  python scripts/connectors/sheets.py <URL-or-ID> --range "'Metrics'!A1:F50"  # FETCH: explicit A1 range

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/sheets.py "https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0"
  ! python scripts/connectors/sheets.py <ID> --sheet Metrics --max 50
  ! python scripts/connectors/sheets.py <ID> --range "'Metrics'!A1:F50" --format json

Disambiguation rule: no argument prints identity/usage; anything else is a
spreadsheet coordinate — a full docs.google.com URL (the /d/<ID>/ segment is
extracted; a #gid= fragment selects that tab and triggers a bounded fetch of
it) or a bare spreadsheet ID.

SIZE DEFENSE (context windows are finite): STACK mode is governed by a TOTAL
data-cell --budget (default 10,000); over budget nothing dumps — a true-extent
gauge prints instead, which IS the drill-down map. --sheet fetches are
row-bounded SERVER-side ('{Tab}'!1:N) and every --sheet/--range fetch is
row-capped client-side by -n/--max (default 25), per THE PROBE ECONOMY RULE.

GRID-VS-DATA (convicted 2026-07-20): metadata gridProperties report grid
ALLOCATION (new tabs read 1000x26 whether they hold 3 rows or 900), while
spreadsheets.values responses return the TRIMMED used rectangle — trailing
empty rows/cols never cross the wire. Data extents therefore come from values
responses (len of rows x max row width), never from metadata; and no Pandas
is needed for acquisition — Pandas belongs downstream in measure.py.

Auth (oauth_token_file — the gmail.py pattern; the human's OWN Google account):
  App identity:  ~/.config/pipulate/credentials.json
                 (override: PIPULATE_SHEETS_CREDENTIALS; the same Desktop-app
                 OAuth client gmail.py uses — Cloud project
                 work-integrations-500916)
  User session:  ~/.config/pipulate/sheets_token.json
                 (override: PIPULATE_SHEETS_TOKEN — a SEPARATE token from
                 gmail_token.json, because token files are scope-scoped and
                 one connector must never poison another's token)

The first run must happen INTERACTIVELY in a real terminal so the one-time
browser OAuth handshake can mint the durable token (running with no argument
does this). After that, `!` invocations in the compile lane refresh the token
silently and never block. There is NO sharing gate in this lane: whatever
Sheets your Google account can open, this connector can read.

AUTH-KIND RESIDUE conviction (2026-07-20): v1 of this file inherited gsc's
service_account plumbing by pattern-proximity, sending the API-enablement
toggle to the wrong project for the wrong credential. Auth kind is a USER
story decision: Pipulate humans own Google accounts -> OAuth.

COMPILE-LANE CAUTION: LIST/FETCH output can contain spreadsheet titles, tab
names, and cell data. This lane assumes non-training AI accounts; still, keep
credentials out of Sheets and let pii_substitutions.txt cover anything you
would not paste yourself.
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
CREDS_PATH = os.environ.get('PIPULATE_SHEETS_CREDENTIALS') or str(
    Path.home() / '.config' / 'pipulate' / 'credentials.json')
TOKEN_PATH = os.environ.get('PIPULATE_SHEETS_TOKEN') or str(
    Path.home() / '.config' / 'pipulate' / 'sheets_token.json')
BIG_TAB_CELLS = 5000  # LIST-mode warning threshold: likely context overflow

_URL_ID_RE = re.compile(r'/spreadsheets/d/([a-zA-Z0-9_-]+)')
_GID_RE = re.compile(r'[#?&]gid=(\d+)')
_BARE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{20,}$')


# ----------------------------------------------------------------------------
# Plumbing
# ----------------------------------------------------------------------------
def die(msg, code=1):
    sys.stderr.write(msg.rstrip('\n') + '\n')
    sys.exit(code)


def parse_spreadsheet_ref(ref):
    """Normalize a Sheets URL or bare ID to (spreadsheet_id, gid_or_None)."""
    ref = ref.strip()
    m = _URL_ID_RE.search(ref)
    if m:
        gid_m = _GID_RE.search(ref)
        return m.group(1), (int(gid_m.group(1)) if gid_m else None)
    if _BARE_ID_RE.match(ref):
        return ref, None
    die(
        f"Could not parse a spreadsheet ID from: {ref}\n"
        "Pass a full https://docs.google.com/spreadsheets/d/<ID>/... URL "
        "or the bare <ID>."
    )


def _save_token(creds):
    """Persist the user session token to the durable, gitignored path."""
    token_path = Path(TOKEN_PATH)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())


def get_service():
    """Authenticated Sheets service; mints/refreshes the OAuth token as needed."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (json.JSONDecodeError, ValueError):
            # Empty or poisoned token (the truncated-write trap). Re-auth.
            creds = None

    if creds and creds.valid:
        return build('sheets', 'v4', credentials=creds)

    # Headless refresh is safe even without a TTY.
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return build('sheets', 'v4', credentials=creds)
        except Exception:
            creds = None

    # From here we need the interactive browser loopback flow.
    if not sys.stdout.isatty():
        die(
            "Sheets auth needs a one-time interactive login.\n"
            "Run this directly in your terminal first to mint the token:\n"
            "    python scripts/connectors/sheets.py\n"
            "After that, `!` invocations inside the compile lane run silently."
        )

    if not os.path.exists(CREDS_PATH):
        die(
            f"Missing credentials.json at: {CREDS_PATH}\n"
            "Download the Desktop-app OAuth client JSON from Google Cloud\n"
            "Console (project work-integrations-500916) — the same file\n"
            "gmail.py uses."
        )

    print("Opening local browser window for Google OAuth negotiation...",
          file=sys.stderr)
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return build('sheets', 'v4', credentials=creds)


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def identity():
    """No-argument mode: OAuth wiring status; mints the token when interactive."""
    creds_ok = os.path.exists(CREDS_PATH)
    token_ok = os.path.exists(TOKEN_PATH)
    project = '(credentials.json missing)'
    if creds_ok:
        try:
            blob = json.loads(Path(CREDS_PATH).read_text(encoding='utf-8'))
            project = (blob.get('installed') or blob.get('web') or {}).get(
                'project_id', '(project_id absent)')
        except (json.JSONDecodeError, OSError) as e:
            project = f'(unreadable credentials.json: {e})'
    print("# sheets.py — read-only Google Sheets gateway (OAuth: your own account)\n")
    print(f"credentials : {CREDS_PATH}  [{'present' if creds_ok else 'MISSING'}]")
    print(f"project_id  : {project}")
    print(f"token       : {TOKEN_PATH}  [{'minted' if token_ok else 'not yet minted'}]")
    if not token_ok and sys.stdout.isatty():
        print("\nMinting the token now (one-time browser handshake)...")
        get_service()
        print("Token minted. Headless `!` runs will work from here on.")
    elif not token_ok:
        print("\nRun this same command once in a real terminal to mint the token.")
    print("\n# Next: python scripts/connectors/sheets.py "
          '"https://docs.google.com/spreadsheets/d/<ID>/edit"   (LIST tabs + sizes)')


def list_tabs(service, sid, gid, max_items):
    """LIST mode: title + every tab's size gauge, so overflow is visible BEFORE fetching."""
    meta = service.spreadsheets().get(
        spreadsheetId=sid,
        fields='properties.title,sheets.properties'
    ).execute()
    title = meta.get('properties', {}).get('title', '(untitled)')
    tabs = meta.get('sheets', [])
    print(f"# {title}  [spreadsheetId: {sid}] — {len(tabs)} tab(s)\n")
    print(f"{'rows':>7}  {'cols':>5}  {'~cells':>9}  tab")
    first_tab = None
    for t in tabs[:max_items]:
        p = t.get('properties', {})
        g = p.get('gridProperties', {})
        rows, cols = g.get('rowCount', 0), g.get('columnCount', 0)
        cells = rows * cols
        name = p.get('title', '?')
        if first_tab is None:
            first_tab = name
        marks = []
        if gid is not None and p.get('sheetId') == gid:
            marks.append('<- gid in URL')
        if cells > BIG_TAB_CELLS:
            marks.append('WARNING: big — fetch with an explicit --range, not a bare --sheet')
        mark = ('  ' + ' | '.join(marks)) if marks else ''
        print(f"{rows:>7}  {cols:>5}  {cells:>9,}  {name}{mark}")
    if len(tabs) > max_items:
        print(f"... +{len(tabs) - max_items} more tab(s) (raise -n/--max)")
    target = first_tab or 'Sheet1'
    print(f"\n# Next: python scripts/connectors/sheets.py {sid} "
          f"--sheet \"{target}\"   (first rows, capped by --max)")


def stack_tabs(service, sid, fmt, budget):
    """STACK mode (the bare-ID default): every tab's ACTUAL data rectangle,
    stacked vertically with payload-grammar sentinels and a clickable #gid=
    URL per tab. One metadata call resolves titles/gids; one values.batchGet
    pulls every used rectangle. Governed by a total-cell budget: over budget,
    nothing dumps — the true-extent gauge prints instead.
    """
    meta = service.spreadsheets().get(
        spreadsheetId=sid,
        fields='properties.title,sheets.properties'
    ).execute()
    title = meta.get('properties', {}).get('title', '(untitled)')
    tabs = [t.get('properties', {}) for t in meta.get('sheets', [])]
    if not tabs:
        print(f"# {title}  [spreadsheetId: {sid}] — no tabs")
        return
    resp = service.spreadsheets().values().batchGet(
        spreadsheetId=sid,
        ranges=["'" + p.get('title', '').replace("'", "''") + "'" for p in tabs],
        majorDimension='ROWS'
    ).execute()
    value_ranges = resp.get('valueRanges', [])
    extents = []
    for p, vr in zip(tabs, value_ranges):
        rows = vr.get('values', [])
        n_rows = len(rows)
        n_cols = max((len(r) for r in rows), default=0)
        extents.append((p, rows, n_rows, n_cols))
    total_cells = sum(r * c for _, _, r, c in extents)
    base_url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    acquired_at = datetime.now(timezone.utc).isoformat(
        timespec='seconds').replace('+00:00', 'Z')

    if total_cells > budget:
        print(f"# {title}  [spreadsheetId: {sid}] — {len(extents)} tab(s), "
              f"{total_cells:,} data cells > budget {budget:,} — STACK withheld")
        print(f"# acquired_at_utc: {acquired_at}\n")
        print(f"{'rows':>7}  {'cols':>5}  {'cells':>9}  tab | tab URL")
        for p, _, r, c in extents:
            print(f"{r:>7}  {c:>5}  {r * c:>9,}  {p.get('title', '?')} | "
                  f"{base_url}#gid={p.get('sheetId', 0)}")
        print(f"\n# Next: python scripts/connectors/sheets.py {sid} "
              "--sheet \"<Tab>\"   (one bounded tab)")
        print(f"# Or raise the ceiling: python scripts/connectors/sheets.py "
              f"{sid} --budget {total_cells}")
        return

    print(f"# {title}  [spreadsheetId: {sid}] — {len(extents)} tab(s), "
          f"{total_cells:,} data cells (full stack)")
    print(f"# acquired_at_utc: {acquired_at}\n")
    for p, rows, n_rows, n_cols in extents:
        name = p.get('title', '?')
        print(f'--- START: TAB "{name}" ({n_rows} rows x {n_cols} cols) ---')
        print(f"# {base_url}#gid={p.get('sheetId', 0)}")
        if rows:
            _emit(rows, fmt)
        else:
            print("(empty tab)")
        print(f'--- END: TAB "{name}" ---\n')
    print(f"# Next: python scripts/connectors/sheets.py {sid} "
          "--range \"'<Tab>'!A1:Z50\" --format json   (one precise slab)")


def resolve_gid_title(service, sid, gid):
    """Map a URL's #gid= fragment to its tab title (None when not found)."""
    meta = service.spreadsheets().get(
        spreadsheetId=sid, fields='sheets.properties').execute()
    for t in meta.get('sheets', []):
        p = t.get('properties', {})
        if p.get('sheetId') == gid:
            return p.get('title')
    return None


def _emit(rows, fmt):
    if fmt == 'json':
        print(json.dumps(rows, indent=2, default=str))
        return
    if fmt == 'markdown':
        width = max(len(r) for r in rows)
        norm = [list(r) + [''] * (width - len(r)) for r in rows]
        print('| ' + ' | '.join(str(c) for c in norm[0]) + ' |')
        print('|' + '---|' * width)
        for r in norm[1:]:
            print('| ' + ' | '.join(str(c) for c in r) + ' |')
        return
    # tsv default: compact, diffable, pandas-friendly; cells sanitized so the
    # container stays one-row-per-line parseable.
    for r in rows:
        print('\t'.join(
            str(c).replace('\t', ' ').replace('\n', ' ') for c in r))


def fetch_values(service, sid, sheet, rng, fmt, max_rows):
    """FETCH mode: bounded values via spreadsheets.values.get."""
    if rng and '!' in rng:
        a1 = rng
    elif rng:
        a1 = f"'{sheet}'!{rng}" if sheet else rng
    else:
        # --sheet alone: bound the request server-side, not just client-side.
        a1 = f"'{sheet}'!1:{max_rows}"
    resp = service.spreadsheets().values().get(
        spreadsheetId=sid, range=a1, majorDimension='ROWS').execute()
    rows = resp.get('values', [])
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    note = ' (truncated by --max)' if truncated else ''
    print(f"# {resp.get('range', a1)}  [spreadsheetId: {sid}] — "
          f"{len(rows)} row(s) shown{note}\n")
    if not rows:
        print("(no values — empty range, or check the tab name / A1 spelling)")
        return
    _emit(rows, fmt)
    tab_hint = sheet if sheet else '<Tab>'
    print(f"\n# Next: python scripts/connectors/sheets.py {sid} "
          f"--range \"'{tab_hint}'!A1:Z{max_rows}\" --format json")


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to Google Sheets for Prompt Fu context."
    )
    parser.add_argument(
        'ref', nargs='?', default=None,
        help='Google Sheets URL or bare spreadsheet ID; omit for identity/usage.'
    )
    parser.add_argument('--sheet', default=None,
                        help='Tab name to fetch (quote it if it contains spaces).')
    parser.add_argument('--range', dest='cell_range', default=None,
                        help="A1 range, e.g. A1:F50 or 'Metrics'!A1:F50 "
                             '(a range containing ! overrides --sheet framing).')
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Row/tab cap per THE PROBE ECONOMY RULE (default: 25).')
    parser.add_argument('--format', choices=['tsv', 'json', 'markdown'],
                        default='tsv',
                        help='Output format (default: tsv — compact and diffable).')
    parser.add_argument('--list', action='store_true',
                        help='Metadata-only tab gauge (grid allocation; zero cell data fetched).')
    parser.add_argument('--budget', type=int, default=10000,
                        help='STACK-mode ceiling in TOTAL data cells (default: 10000).')
    args = parser.parse_args()

    if args.ref is None:
        identity()
        return

    sid, gid = parse_spreadsheet_ref(args.ref)
    service = get_service()
    try:
        if args.sheet is None and args.cell_range is None:
            if gid is not None:
                # The URL named a specific tab: fetch it, bounded.
                title = resolve_gid_title(service, sid, gid)
                if title:
                    fetch_values(service, sid, title, None,
                                 args.format, args.max)
                    return
            if args.list:
                list_tabs(service, sid, gid, args.max)
            else:
                stack_tabs(service, sid, args.format, args.budget)
        else:
            fetch_values(service, sid, args.sheet, args.cell_range,
                         args.format, args.max)
    except HttpError as e:
        die(
            f"Sheets API error: {e}\n"
            "If this is 403 SERVICE_DISABLED: enable the Google Sheets API in the\n"
            "OAuth client's Cloud project (run with no argument to print its\n"
            "project_id). If 403/404 otherwise: confirm YOUR Google account can\n"
            "open this spreadsheet in a browser — OAuth reads as you."
        )


if __name__ == '__main__':
    main()
