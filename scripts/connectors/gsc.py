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

Auth (service_account_file — headless by construction, no browser dance ever):
  PIPULATE_GSC_KEY env var
    -> ~/.config/pipulate/connectors.json gsc.paths.service_account
      -> clean failure naming the missing variable.

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

from google.oauth2 import service_account
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


def resolve_key_path():
    """PIPULATE_GSC_KEY env -> wallet gsc.paths.service_account -> None."""
    env = os.environ.get('PIPULATE_GSC_KEY')
    if env:
        return Path(env).expanduser()
    if WALLET_FILE.exists():
        try:
            wallet = json.loads(WALLET_FILE.read_text(encoding='utf-8'))
            p = (wallet.get('gsc') or {}).get('paths', {}).get('service_account')
            if p:
                return Path(p).expanduser()
        except (json.JSONDecodeError, OSError):
            pass
    return None


def get_service():
    key_path = resolve_key_path()
    if not key_path:
        die(
            "No GSC key path configured.\n"
            "Set PIPULATE_GSC_KEY=~/.config/pipulate/service-account-key.json\n"
            "or add gsc.paths.service_account to ~/.config/pipulate/connectors.json."
        )
    if not key_path.exists():
        die(
            f"GSC service-account key not found at: {key_path}\n"
            "Download the JSON key for the service account from Google Cloud Console,\n"
            "save it at that path, and chmod 600 it. Then add the service account's\n"
            "email as a user on each Search Console property it should read."
        )
    creds = service_account.Credentials.from_service_account_file(
        str(key_path), scopes=SCOPES)
    return build('webmasters', 'v3', credentials=creds)


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
        print("(no properties — has the service account's email been added as a "
              "user in Search Console?)")
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
    args = parser.parse_args()

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
