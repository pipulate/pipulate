#!/usr/bin/env python3
# scripts/connectors/gsc.py
"""
gsc.py — A Unix-philosophy gateway to Google Search Console for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/gsc.py                          # LIST: properties visible to the service account
  python scripts/connectors/gsc.py sc-domain:example.com    # LIST: top queries, last 28 days
  python scripts/connectors/gsc.py '{"startDate": ...}'     # FETCH: raw searchanalytics JSON body

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/gsc.py
  ! python scripts/connectors/gsc.py sc-domain:mikelev.in
  ! python scripts/connectors/gsc.py '{"startDate":"2026-06-01","endDate":"2026-06-28","dimensions":["page"]}' --site sc-domain:mikelev.in

Disambiguation rule: an argument that starts with '{' or contains whitespace is
a raw searchanalytics query body (FETCH mode; needs --site or PIPULATE_GSC_SITE);
any other bare token is a property coordinate (LIST top queries); no argument
at all lists properties.

Auth (oauth_token_file — the same user-OAuth walk as gmail.py and sheets.py):
  token:       PIPULATE_GSC_TOKEN env var
    -> ~/.config/pipulate/connectors.json gsc.paths.token
      -> ~/.config/pipulate/gsc_token.json
  credentials: PIPULATE_GSC_CREDENTIALS env var
    -> ~/.config/pipulate/connectors.json gsc.paths.credentials
      -> ~/.config/pipulate/credentials.json  (the shared Desktop-app client)
  A valid token refreshes headlessly, and the token file is REWRITTEN on
  every refresh so the wallet's offline mtime heuristic tracks "last
  refreshed". A missing or dead token browser-mints ONLY on a real TTY —
  `python scripts/connectors/wallet.py login gsc` is the one-time mint,
  exactly as for gmail and sheets. No service account anywhere.

Output is capped by -n/--max (default 25) per THE PROBE ECONOMY RULE: stdout is
destined for compiled context payloads, so the bound is a feature.

COMPILE-LANE CAUTION: LIST output contains property URLs, which are domains —
potentially client domains. Make sure pii_substitutions.txt covers any real
client identifiers before a `!` invocation rides to a cloud chat window.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import date, timedelta

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
WALLET_FILE = Path.home() / '.config' / 'pipulate' / 'connectors.json'


# ----------------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------------
def die(msg, code=1):
    sys.stderr.write(msg.rstrip('\n') + '\n')
    sys.exit(code)


def _wallet_path(key):
    """gsc.paths.<key> from the wallet, or None. Names and paths only."""
    if WALLET_FILE.exists():
        try:
            wallet = json.loads(WALLET_FILE.read_text(encoding='utf-8'))
            p = (wallet.get('gsc') or {}).get('paths', {}).get(key)
            if p:
                return Path(p).expanduser()
        except (json.JSONDecodeError, OSError):
            pass
    return None


def resolve_token_path():
    """PIPULATE_GSC_TOKEN env -> wallet gsc.paths.token -> canonical default."""
    env = os.environ.get('PIPULATE_GSC_TOKEN')
    if env:
        return Path(env).expanduser()
    return _wallet_path('token') or Path.home() / '.config' / 'pipulate' / 'gsc_token.json'


def resolve_credentials_path():
    """PIPULATE_GSC_CREDENTIALS env -> wallet gsc.paths.credentials -> the
    shared Desktop-app OAuth client JSON the other Google connectors mint from."""
    env = os.environ.get('PIPULATE_GSC_CREDENTIALS')
    if env:
        return Path(env).expanduser()
    return _wallet_path('credentials') or Path.home() / '.config' / 'pipulate' / 'credentials.json'


def _write_token(token_path, creds):
    """Rewrite the token file on every mint AND refresh, 0600. The rewrite is
    what makes the wallet's offline mtime heuristic track 'last refreshed'."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding='utf-8')
    os.chmod(token_path, 0o600)


def _load_creds():
    """(creds_or_None, reason). Headless by construction: refreshes when it
    can, rewrites the token file when it does, and NEVER opens a browser."""
    token_path = resolve_token_path()
    if not token_path.exists():
        return None, f"no OAuth token at {token_path}"
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except (ValueError, OSError) as e:
        return None, f"token unreadable ({e})"
    if creds.valid:
        return creds, 'live'
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            return None, f"refresh rejected ({e})"
        _write_token(token_path, creds)
        return creds, 'refreshed'
    return None, 'token expired and holds no refresh_token'


def get_service():
    """Refresh headlessly, or browser-mint on a real TTY — the same walk
    wallet.py's login verb reuses for gmail and sheets. A `!` chisel-strike
    can never block here: no TTY means a clean die(), never a browser."""
    creds, reason = _load_creds()
    if creds is None:
        creds_path = resolve_credentials_path()
        if not creds_path.exists():
            die(
                f"GSC OAuth needs the Desktop-app client JSON at: {creds_path}\n"
                "It is the same credentials.json the gmail/sheets connectors mint\n"
                "from. Download it once from the Google Cloud Console, then run:\n"
                "    python scripts/connectors/wallet.py login gsc"
            )
        if not sys.stdin.isatty():
            die(
                f"GSC token not usable ({reason}) and no TTY to browser-mint.\n"
                "In a real terminal, run:\n"
                "    python scripts/connectors/wallet.py login gsc"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)
        _write_token(resolve_token_path(), creds)
    return build('webmasters', 'v3', credentials=creds)


def check():
    """SELECT 1 for the `warm` board: exit 0 GREEN, exit 1 RED (gate-named).

    Modeled on botify.py's two-gate probe. gate1 is "credential present and
    loadable" — headless refresh allowed, because the durable credential
    scored is the refresh token, exactly as for every other oauth slot.
    gate2 is "the live API accepted it": one bounded sites().list() call.
    15s budget via socket default timeout, stdin-safe: this path NEVER
    browser-mints, so it can never hang the board on a prompt.
    """
    import socket
    creds, reason = _load_creds()
    if creds is None:
        sys.stderr.write(
            f"gsc RED gate1: {reason} -- run "
            "`python scripts/connectors/wallet.py login gsc`\n")
        return 1
    socket.setdefaulttimeout(15)
    try:
        service = build('webmasters', 'v3', credentials=creds)
        resp = service.sites().list().execute()
    except HttpError as e:
        sys.stderr.write(f"gsc RED gate2: API rejected the call: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"gsc RED gate2: transport failure: {e}\n")
        return 1
    entries = resp.get('siteEntry', [])
    noun = 'property' if len(entries) == 1 else 'properties'
    print(f"gsc GREEN {len(entries)} {noun} visible ({reason})")
    return 0


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def list_properties(service, max_items):
    """LIST mode, no argument: every property visible to the service account."""
    resp = service.sites().list().execute()
    entries = resp.get('siteEntry', [])
    print(f"# GSC properties visible to this service account "
          f"({len(entries)} total, showing up to {max_items})\n")
    if not entries:
        print("(no properties — does this Google account have access to any "
              "Search Console properties?)")
        return
    for e in sorted(entries, key=lambda x: x.get('siteUrl', ''))[:max_items]:
        print(f"{e.get('siteUrl', '?')}  [{e.get('permissionLevel', '?')}]")
    print("\n# Next: python scripts/connectors/gsc.py sc-domain:example.com   "
          "(top queries, last 28 days)")


def list_top_queries(service, site, max_items):
    """LIST mode, property token: top queries over the trailing 28 complete days."""
    end = date.today() - timedelta(days=3)   # GSC data lags ~2-3 days
    start = end - timedelta(days=27)
    body = {
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'dimensions': ['query'],
        'rowLimit': max_items,
    }
    resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
    rows = resp.get('rows', [])
    print(f"# GSC top queries for {site} ({start} .. {end}, cap {max_items})\n")
    if not rows:
        print("(no rows — check the property token: 'sc-domain:example.com' "
              "or 'https://example.com/')")
        return
    print(f"{'clicks':>7}  {'impr':>8}  {'ctr%':>6}  {'pos':>6}  query")
    for r in rows[:max_items]:
        q = (r.get('keys') or ['?'])[0]
        print(f"{int(r.get('clicks', 0)):>7}  {int(r.get('impressions', 0)):>8}  "
              f"{100 * r.get('ctr', 0):>6.2f}  {r.get('position', 0):>6.1f}  {q}")
    print("\n# Next: python scripts/connectors/gsc.py "
          "'{\"startDate\":\"" + start.isoformat() + "\",\"endDate\":\"" + end.isoformat() +
          "\",\"dimensions\":[\"page\"]}' --site " + site)


def run_query(service, site, raw_query, max_items):
    """FETCH mode: raw searchanalytics JSON body against one property."""
    if not site:
        die(
            "FETCH mode needs a property coordinate: pass --site sc-domain:example.com\n"
            "or set PIPULATE_GSC_SITE in your environment."
        )
    stripped = raw_query.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as e:
        die(
            f"FETCH mode expects a raw searchanalytics JSON body ({e}).\n"
            "Example: '{\"startDate\":\"2026-06-01\",\"endDate\":\"2026-06-28\","
            "\"dimensions\":[\"page\",\"query\"]}'"
        )
    payload.setdefault('rowLimit', max_items)
    resp = service.searchanalytics().query(siteUrl=site, body=payload).execute()
    rows = resp.get('rows')
    if isinstance(rows, list):
        rows = rows[:max_items]
        print(f"# GSC query results for {site} ({len(rows)} row(s), cap {max_items})\n")
        print(json.dumps(rows, indent=2, default=str))
    else:
        print(json.dumps(resp, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to Google Search Console for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (list properties), a property token (top queries), "
             "or a raw searchanalytics JSON body."
    )
    parser.add_argument('--site', default=os.getenv('PIPULATE_GSC_SITE'),
                        help='Property coordinate for FETCH mode '
                             '(default: PIPULATE_GSC_SITE env).')
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Output cap per THE PROBE ECONOMY RULE (default: 25).')
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

    service = get_service()
    try:
        arg = args.query
        if arg is None:
            list_properties(service, args.max)
        elif arg.strip().startswith('{') or any(ch.isspace() for ch in arg.strip()):
            run_query(service, args.site, arg, args.max)
        else:
            list_top_queries(service, arg, args.max)
    except HttpError as e:
        die(f"GSC API error: {e}")


if __name__ == '__main__':
    main()
