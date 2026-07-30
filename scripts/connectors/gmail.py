#!/usr/bin/env python3
# scripts/gmail.py
"""
gmail.py — Bring an email thread or a sender's threads into context.

A Unix-philosophy gateway to the Gmail API for Prompt Fu context.

Two golden-path modes, auto-detected from the single positional argument:

  python scripts/gmail.py user@domain.com   # LIST: recent threads involving them
  python scripts/gmail.py <thread_id>       # FETCH: full clean transcript of a thread

Designed to be dropped into foo_files.py as a `!` chisel-strike, e.g.:

  ! python scripts/gmail.py michael.levin@botify.com
  ! python scripts/gmail.py 18f4ad923b1c83e2

A subject search and a Gmail web thread URL are also accepted:

  python scripts/gmail.py 'SM Store Locator upgrade'                      # SEARCH by subject
  python scripts/gmail.py 'https://mail.google.com/mail/u/0/#all/<hexId>'  # FETCH via URL

Disambiguation rule (checked in this order): an argument starting with http(s)
is a Gmail web URL (FETCH the hex thread id in its fragment; a legacy
#all/<hexId> or #label/<hexId> URL carries one, while an opaque FMfcg... web id
cannot be converted and fails loud, pointing you at subject search); an argument
containing '@' is an email address (LIST); an argument with whitespace, or any
non-hex bare token, is a subject SEARCH; a bare hex token is a thread id (FETCH).

A subject SEARCH prints the COMPLETE transcript of every matching thread — the
same output a thread id gives, attachments included — so an exact subject drops
the whole discussion into context. Add --list for a lighter snippet browse-list.

Auth:
  - App identity:  ~/.config/pipulate/credentials.json (override: PIPULATE_GMAIL_CREDENTIALS)
  - User session:  ~/.config/pipulate/gmail_token.json (override: PIPULATE_GMAIL_TOKEN)

The first run must happen INTERACTIVELY in a real terminal so the one-time
browser OAuth handshake can mint the durable token. After that, runs inside
foo_files (captured stdout, no TTY) refresh the token silently and never block.
"""

import os
import re
import sys
import json
import base64
import argparse
import html as html_lib
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

REPO_ROOT = Path(__file__).resolve().parent.parent
CREDS_PATH = os.environ.get('PIPULATE_GMAIL_CREDENTIALS') or str(
    Path.home() / '.config' / 'pipulate' / 'credentials.json'
)
TOKEN_PATH = os.environ.get('PIPULATE_GMAIL_TOKEN') or str(
    Path.home() / '.config' / 'pipulate' / 'gmail_token.json'
)

# A Gmail API thread id is lowercase hex (e.g. 18f4ad923b1c83e2). Gmail's
# opaque web ids (FMfcg..., Ktbx..., CXKn...) carry letters outside [a-f], so
# this regex cleanly discriminates a usable id from an unconvertible web id.
_HEX_ID_RE = re.compile(r'^[0-9a-fA-F]{10,}$')


def parse_gmail_url(url):
    """Pull a thread identifier out of a Gmail web URL fragment.

    Returns (kind, segment):
      ('thread_id', '<hex>')  — a usable API hex thread id (legacy
                                #all/<hexId> or #label/<hexId> URLs carry one).
      ('opaque',   '<seg>')   — Gmail's opaque, per-account web id (FMfcg...).
                                The API never returns it and it cannot be
                                converted offline, so the caller must fail loud
                                and steer the human to subject search.
    The fragment is the last '/'-delimited segment after the '#'.
    """
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    frag = unquote(parsed.fragment)
    seg = frag.rstrip('/').split('/')[-1] if frag else ''
    return ('thread_id', seg) if _HEX_ID_RE.match(seg) else ('opaque', seg)


# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------
def _save_token(creds):
    """Persist the user session token to the durable, gitignored path."""
    token_path = Path(TOKEN_PATH)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())


def get_service():
    """Return an authenticated Gmail service, minting/refreshing tokens as needed."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (json.JSONDecodeError, ValueError):
            # Empty or poisoned token (the classic truncated-write trap). Re-auth.
            creds = None

    if creds and creds.valid:
        return build('gmail', 'v1', credentials=creds)

    # Headless refresh is safe even without a TTY.
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return build('gmail', 'v1', credentials=creds)
        except Exception:
            creds = None

    # From here we need the interactive browser loopback flow.
    if not sys.stdout.isatty():
        sys.stderr.write(
            "Gmail auth needs a one-time interactive login.\n"
            "Run this directly in your terminal first to mint the token:\n"
            "    python scripts/gmail.py your-email@domain.com\n"
            "After that, the `!` invocation inside foo_files runs silently.\n"
        )
        sys.exit(1)

    if not os.path.exists(CREDS_PATH):
        sys.stderr.write(
            f"Missing credentials.json at: {CREDS_PATH}\n"
            "Download the Desktop-app OAuth client JSON from Google Cloud Console.\n"
        )
        sys.exit(1)

    print("Opening local browser window for Workspace OAuth negotiation...",
          file=sys.stderr)
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return build('gmail', 'v1', credentials=creds)


# ----------------------------------------------------------------------------
# Message parsing helpers
# ----------------------------------------------------------------------------
def _headers(msg):
    raw = msg.get('payload', {}).get('headers', [])
    return {h['name'].lower(): h['value'] for h in raw}


def _message_date(msg):
    ts = msg.get('internalDate')
    if ts:
        return datetime.fromtimestamp(int(ts) / 1000).strftime('%Y-%m-%d %H:%M')
    return _headers(msg).get('date', '')


def _decode_b64url(data):
    if not data:
        return ''
    return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8', errors='replace')


def _strip_html(s):
    s = re.sub(r'(?is)<(script|style).*?</\1>', '', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</p\s*>', '\n\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_lib.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s


def _collect_mime(payload, target):
    """Depth-first collect bodies matching `target` mime, skipping attachments."""
    out = []
    if payload.get('filename'):  # an attachment or inline file part — skip it
        return out
    if payload.get('mimeType', '') == target:
        data = payload.get('body', {}).get('data')
        if data:
            out.append(_decode_b64url(data))
    for part in payload.get('parts', []) or []:
        out.extend(_collect_mime(part, target))
    return out


def extract_body(payload):
    """Prefer text/plain; fall back to crudely-stripped text/html. No attachments."""
    plain = _collect_mime(payload, 'text/plain')
    if plain:
        return '\n'.join(plain).strip()
    html_parts = _collect_mime(payload, 'text/html')
    if html_parts:
        return _strip_html('\n'.join(html_parts)).strip()
    return '(no text body found)'


def _collect_attachments(payload):
    """Depth-first collect attachment metadata only — never the bytes.

    Returns a list of {filename, mime, size, attachment_id} dicts. This is the
    token-cheap 'there is more here if you want it' hook: enough to know an
    attachment exists and to fetch it later via
    users.messages.attachments.get(userId, messageId, id=attachment_id),
    without ever pulling the (potentially huge, often non-text) payload into
    the prompt. Wiring that fetch up is a deliberate future move, not this one.
    """
    out = []
    filename = payload.get('filename')
    if filename:
        body = payload.get('body', {})
        out.append({
            'filename': filename,
            'mime': payload.get('mimeType', 'application/octet-stream'),
            'size': body.get('size', 0),
            'attachment_id': body.get('attachmentId', ''),
        })
    for part in payload.get('parts', []) or []:
        out.extend(_collect_attachments(part))
    return out


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def list_threads(service, address, max_results):
    """LIST mode: recent threads involving `address`, newest-update first."""
    query = f'from:{address} OR to:{address}'
    resp = service.users().threads().list(
        userId='me', q=query, maxResults=max_results
    ).execute()
    threads = resp.get('threads', [])

    print(f"# Gmail threads involving {address} (most recent first)\n")
    if not threads:
        print("(no threads found)")
        return

    for t in threads:
        meta = service.users().threads().get(
            userId='me', id=t['id'], format='metadata',
            metadataHeaders=['Subject', 'From', 'Date'],
        ).execute()
        msgs = meta.get('messages', [])
        if not msgs:
            continue
        last = msgs[-1]
        h = _headers(last)
        subject = h.get('subject', '(no subject)')
        sender = h.get('from', '(unknown sender)')
        date = _message_date(last)
        snippet = (t.get('snippet') or '').strip()

        print(f"[{date}] {t['id']}  {subject}")
        print(f"    from: {sender}  |  messages: {len(msgs)}")
        if snippet:
            print(f"    snippet: {snippet}")
        print()


def search_threads(service, subject, max_results, full=True):
    """SEARCH mode: find threads whose subject matches, newest-update first.

    Default (full=True) prints the COMPLETE transcript of every matching
    thread — bodies and attachment metadata included — by reusing
    fetch_thread, so an exact subject drops the whole discussion into context
    exactly as a thread id would. Pass full=False (the --list flag) for the
    lighter snippet browse-list, which prints each hit's FETCH-able hex id.
    """
    q = 'subject:"' + subject.replace('"', '') + '"'
    resp = service.users().threads().list(
        userId='me', q=q, maxResults=max_results
    ).execute()
    threads = resp.get('threads', [])

    if not threads:
        print(f'# No Gmail threads with subject matching "{subject}"')
        print("(try fewer or different subject words)")
        return

    if full:
        print(f'# Full transcript(s) for subject "{subject}" — '
              f"{len(threads)} thread(s), most recent first\n")
        for i, t in enumerate(threads):
            fetch_thread(service, t['id'])
            if i < len(threads) - 1:
                print("\n" + "=" * 78 + "\n")
        return

    print(f'# Gmail threads with subject matching "{subject}" (most recent first)\n')
    for t in threads:
        meta = service.users().threads().get(
            userId='me', id=t['id'], format='metadata',
            metadataHeaders=['Subject', 'From', 'Date'],
        ).execute()
        msgs = meta.get('messages', [])
        if not msgs:
            continue
        last = msgs[-1]
        h = _headers(last)
        subj = h.get('subject', '(no subject)')
        sender = h.get('from', '(unknown sender)')
        date = _message_date(last)
        snippet = (t.get('snippet') or '').strip()

        print(f"[{date}] {t['id']}  {subj}")
        print(f"    from: {sender}  |  messages: {len(msgs)}")
        if snippet:
            print(f"    snippet: {snippet}")
        print()
    print("# Next: python scripts/connectors/gmail.py <thread_id>   (full transcript)")


def fetch_thread(service, thread_id):
    """FETCH mode: full clean transcript of one thread, chronological.

    Bodies are emitted in full with no truncation. Attachments are NOT pulled
    into the prompt — instead each one is surfaced as a metadata-only hook
    (filename, mime, size, messageId, attachmentId) so a future turn can decide
    whether to wire up the actual fetch.
    """
    thread = service.users().threads().get(
        userId='me', id=thread_id, format='full'
    ).execute()
    messages = thread.get('messages', [])
    if not messages:
        print(f"# Gmail thread {thread_id}\n\n(no messages found)")
        return

    subject = _headers(messages[0]).get('subject', '(no subject)')
    print(f'# Gmail thread {thread_id} — "{subject}"\n')

    for i, msg in enumerate(messages, start=1):
        h = _headers(msg)
        print(f"## Message {i} — {_message_date(msg)}")
        print(f"From: {h.get('from', '(unknown)')}")
        if h.get('to'):
            print(f"To: {h['to']}")
        print()
        payload = msg.get('payload', {})
        print(extract_body(payload))
        print()
        attachments = _collect_attachments(payload)
        if attachments:
            print(f"### Attachments ({len(attachments)}) — metadata only, bytes not fetched")
            for a in attachments:
                print(
                    f"- {a['filename']} ({a['mime']}, {a['size']:,} bytes) "
                    f"[messageId: {msg.get('id', '')} | attachmentId: {a['attachment_id']}]"
                )
            print("> Fetch hook (deferred): users.messages.attachments.get(userId='me', messageId=…, id=attachmentId)")
            print()
        if i < len(messages):
            print("---\n")


# ----------------------------------------------------------------------------
# Health check (THE EXIT-CODE PROTOCOL: the exit code IS the whole answer)
# ----------------------------------------------------------------------------
def check():
    """SELECT 1 for the wallet board: exit 0 GREEN, exit 1 RED.

    Gate 1 is "a usable token exists on disk" -- present, parseable, and
    either valid or silently refreshable. Gate 2 is "Gmail accepts it right
    now": one users.getProfile call.

    Deliberately does NOT call get_service(), because get_service() may open
    a browser on a TTY. An unminted or unrefreshable token is RED, never a
    popup: a check that can block is a check that can hang the whole board.
    """
    if not os.path.exists(TOKEN_PATH):
        sys.stderr.write(f"gmail RED gate1: no token at {TOKEN_PATH}\n")
        return 1
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"gmail RED gate1: unreadable token ({e})\n")
        return 1
    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            sys.stderr.write(
                "gmail RED gate1: token invalid and not refreshable -- run "
                "`python scripts/connectors/wallet.py login gmail`\n")
            return 1
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as e:
            sys.stderr.write(f"gmail RED gate1: refresh failed ({e})\n")
            return 1
    try:
        profile = build('gmail', 'v1', credentials=creds).users().getProfile(
            userId='me').execute()
    except HttpError as e:
        status = getattr(getattr(e, 'resp', None), 'status', '?')
        sys.stderr.write(f"gmail RED gate2: API rejected (HTTP {status})\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"gmail RED gate2: transport failure: {e}\n")
        return 1
    email = profile.get('emailAddress')
    if not email:
        sys.stderr.write("gmail RED gate2: authenticated but no emailAddress\n")
        return 1
    print(f"gmail GREEN {email}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Gmail API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help='Email address (LIST), Gmail thread URL or hex id (FETCH), '
             'or "subject words" (SEARCH).'
    )
    parser.add_argument(
        '-n', '--max', type=int, default=10,
        help='Max threads to list/fetch in LIST or SEARCH mode (default: 10).'
    )
    parser.add_argument(
        '--list', action='store_true',
        help='In SEARCH mode, print the snippet browse-list instead of full '
             'transcripts.'
    )
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())
    if args.query is None:
        parser.error(
            'a query is required: an email address (LIST), a Gmail thread URL '
            'or hex id (FETCH), or "subject words" (SEARCH)')

    query = args.query.strip()
    try:
        service = get_service()
        if query.startswith(('http://', 'https://')):
            kind, seg = parse_gmail_url(query)
            if kind == 'thread_id':
                fetch_thread(service, seg)
            else:
                sys.stderr.write(
                    f"That Gmail URL carries an opaque web id ({seg or '(empty)'}), "
                    "which the Gmail\nAPI never returns and cannot convert to a "
                    "thread id. Search by subject\ninstead and FETCH the hex thread "
                    "id it prints:\n"
                    '    python scripts/connectors/gmail.py "SM Store Locator upgrade"\n'
                )
                sys.exit(1)
        elif '@' in query:
            list_threads(service, query, args.max)
        elif any(ch.isspace() for ch in query) or not _HEX_ID_RE.match(query):
            search_threads(service, query, args.max, full=not args.list)
        else:
            fetch_thread(service, query)
    except HttpError as e:
        sys.stderr.write(f"Gmail API error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
