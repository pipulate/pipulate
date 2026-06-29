#!/usr/bin/env python3
# scripts/gmail.py
"""
gmail.py — A Unix-philosophy gateway to the Gmail API for Prompt Fu context.

Two golden-path modes, auto-detected from the single positional argument:

  python scripts/gmail.py user@domain.com   # LIST: recent threads involving them
  python scripts/gmail.py <thread_id>       # FETCH: full clean transcript of a thread

Designed to be dropped into foo_files.py as a `!` chisel-strike, e.g.:

  ! python scripts/gmail.py michael.levin@botify.com
  ! python scripts/gmail.py 18f4ad923b1c83e2

Disambiguation rule: if the argument contains '@' it is treated as an email
address (LIST mode); otherwise it is treated as a Gmail thread ID (FETCH mode).

Auth:
  - App identity:  credentials.json in repo root (override: PIPULATE_GMAIL_CREDENTIALS)
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
CREDS_PATH = os.environ.get('PIPULATE_GMAIL_CREDENTIALS') or str(REPO_ROOT / 'credentials.json')
TOKEN_PATH = os.environ.get('PIPULATE_GMAIL_TOKEN') or str(
    Path.home() / '.config' / 'pipulate' / 'gmail_token.json'
)


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
            print(f"    snippet: {snippet[:80]}")
        print()


def fetch_thread(service, thread_id):
    """FETCH mode: full clean transcript of one thread, chronological, no attachments."""
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
        print(extract_body(msg.get('payload', {})))
        print()
        if i < len(messages):
            print("---\n")


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Gmail API for Prompt Fu context."
    )
    parser.add_argument(
        'query',
        help='Email address (LIST mode) or Gmail thread ID (FETCH mode).'
    )
    parser.add_argument(
        '-n', '--max', type=int, default=10,
        help='Max threads to list in LIST mode (default: 10).'
    )
    args = parser.parse_args()

    try:
        service = get_service()
        if '@' in args.query:
            list_threads(service, args.query, args.max)
        else:
            fetch_thread(service, args.query)
    except HttpError as e:
        sys.stderr.write(f"Gmail API error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
