#!/usr/bin/env python3
# scripts/connectors/slack.py
"""
slack.py — A Unix-philosophy gateway to the Slack Web API for Prompt Fu context.

Golden-path modes, auto-detected from the single positional argument:

  python scripts/connectors/slack.py                 # LIST: channels you can see (+ identity)
  python scripts/connectors/slack.py C0123ABCD        # LIST: recent messages in that channel
  python scripts/connectors/slack.py general          # LIST: same, resolving a bare #name to its id
  python scripts/connectors/slack.py https://you.slack.com/archives/C0123ABCD/p1699999999123456
                                                      # FETCH: that thread's parent + all replies
  python scripts/connectors/slack.py 'deploy failed checkout'   # SEARCH: search.messages (user token)

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/slack.py
  ! python scripts/connectors/slack.py C0123ABCD

Disambiguation rule (checked in this order):
  - no argument                              -> identity (auth.test) + LIST channels
  - a slack.com/archives/... permalink URL   -> FETCH that thread (conversations.replies)
  - a channel id (C.../G.../D...) or #name   -> LIST that channel's recent messages (conversations.history)
  - anything with whitespace                 -> SEARCH (search.messages)

Auth (bearer_token -- the botify.py shape):
  SLACK_BOT_TOKEN   xoxb-... ; scopes channels:read groups:read channels:history
                    groups:history users:read. Covers LIST and (for DMs/MPDMs, and
                    for channels the bot is invited to) FETCH.
  SLACK_USER_TOKEN  xoxp-... with search:read (and read scopes). REQUIRED for SEARCH
                    (bot tokens cannot call search.messages). When present it is also
                    PREFERRED for reads, because bot tokens are restricted from reading
                    thread replies on public/private channels -- a user token dodges that.

Endpoint notes (verified against Slack's current Web API):
  - Legacy channels.list/groups.list are retired; conversations.* is canonical.
  - conversations.replies needs BOTH channel and the PARENT thread ts; the permalink
    carries both, so FETCH takes a permalink rather than two coordinates.
  - As of 2026-03-03, non-Marketplace apps see conversations.* clamped to ~15 objects
    per call and ~1 request/minute. --max defaults to 25 for cross-connector consistency,
    but reads may silently return only 15; that clamp IS the Probe Economy Rule for free.
  - Slack returns HTTP 200 even on API errors; the real status is the JSON `ok` field.

COMPILE-LANE CAUTION: channel names, message text, and user ids are client identifiers
and client content. Any `!` invocation bound for a cloud chat window rides through the
compile-lane sanitizer -- make sure pii_substitutions.txt covers the relevant identifiers
first. (For an internal-Confluence-only lane, a disclosure profile that leaves names in
place is the intended path.)
"""

import os
import re
import sys
import argparse
from urllib.parse import urlparse, parse_qs

import httpx

API_BASE = "https://slack.com/api"
CHANNEL_ID_RE = re.compile(r'^[CGD][A-Z0-9]{6,}$')
PERMALINK_RE = re.compile(r'^https?://[^/]+\.slack\.com/archives/', re.I)


# ----------------------------------------------------------------------------
# Auth & transport
# ----------------------------------------------------------------------------
def get_token(mode):
    """Resolve the right token for the mode, failing loud and named.

    SEARCH needs a user token (bot tokens cannot call search.messages). For
    LIST/FETCH a user token is PREFERRED when present (it dodges the bot-token
    channel-read restriction), else the bot token is used.
    """
    bot = os.getenv("SLACK_BOT_TOKEN")
    user = os.getenv("SLACK_USER_TOKEN")
    if mode == "search":
        if user:
            return user, "user"
        sys.stderr.write(
            "SEARCH requires SLACK_USER_TOKEN (a user token xoxp- with the "
            "search:read scope).\nBot tokens cannot call search.messages. "
            "LIST and FETCH still work with SLACK_BOT_TOKEN alone.\n"
        )
        sys.exit(1)
    if user:
        return user, "user"
    if bot:
        return bot, "bot"
    sys.stderr.write(
        "Missing environment variable(s): SLACK_BOT_TOKEN (or SLACK_USER_TOKEN)\n"
        "Create a Slack app at https://api.slack.com/apps, add the read scopes, "
        "install it to the workspace, and copy the bot token (xoxb-...).\n"
    )
    sys.exit(1)


def make_client(token):
    return httpx.Client(
        base_url=API_BASE, timeout=60.0,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )


def call(client, method, params=None):
    """GET a Web API method. Slack returns HTTP 200 even on failure, so the
    real verdict is the JSON `ok` field; a false `ok` is a loud named receipt."""
    resp = client.get(f"/{method}", params=params or {})
    if resp.status_code != 200:
        sys.stderr.write(f"HTTP {resp.status_code} for {method}\n{resp.text[:500]}\n")
        sys.exit(1)
    data = resp.json()
    if not data.get("ok"):
        err = data.get("error", "unknown_error")
        needed = data.get("needed", "")
        hint = ""
        if err in ("not_allowed_token_type", "missing_scope"):
            hint = ("\nHint: set SLACK_USER_TOKEN (xoxp-, with the read/search scopes), "
                    "or grant the bot the named scope and re-install the app.")
        elif err == "not_in_channel":
            hint = "\nHint: invite the bot to that channel, or use a user token."
        elif err == "channel_not_found":
            hint = "\nHint: pass the channel id (C...) from `slack.py` with no argument."
        sys.stderr.write(
            f"Slack API error on {method}: {err}"
            + (f" (needed: {needed})" if needed else "") + hint + "\n"
        )
        sys.exit(1)
    return data


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _clip(text, width=100):
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[:width - 1] + "…"


def parse_permalink(url):
    """A Slack archive permalink carries both coordinates conversations.replies
    needs. Path form: /archives/<CID>/p<digits> where the ts is <digits> with a
    dot inserted 6 from the right. Query params cid/thread_ts win when present."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    parts = [p for p in parsed.path.split('/') if p]
    channel = qs.get('cid', [None])[0]
    ts = qs.get('thread_ts', [None])[0]
    if not channel and len(parts) >= 2 and parts[0] == 'archives':
        channel = parts[1]
    if not ts and len(parts) >= 3 and parts[2].startswith('p'):
        digits = parts[2][1:]
        if len(digits) > 6 and digits.isdigit():
            ts = digits[:-6] + '.' + digits[-6:]
    return channel, ts


def resolve_channel(client, name, max_items):
    """Turn a bare #name into a channel id via one conversations.list page.
    Falls back to a clear instruction if it is not on the first page."""
    name = name.lstrip('#')
    data = call(client, "conversations.list",
                {"types": "public_channel,private_channel",
                 "exclude_archived": "true", "limit": 200})
    for ch in data.get("channels", []):
        if ch.get("name") == name:
            return ch.get("id")
    sys.stderr.write(
        f"Channel '#{name}' not found on the first page. Run `slack.py` with no "
        f"argument to list channels, then pass the channel id (C...) directly.\n"
    )
    sys.exit(1)


# ----------------------------------------------------------------------------
# Modes
# ----------------------------------------------------------------------------
def identity_and_list(client, max_items):
    who = call(client, "auth.test")
    print(f"# Slack identity: {who.get('user', '?')} @ {who.get('team', '?')} "
          f"({who.get('url', '')})\n")
    data = call(client, "conversations.list",
                {"types": "public_channel,private_channel",
                 "exclude_archived": "true", "limit": max_items})
    channels = data.get("channels", [])
    print("# Channels visible to this token (id | name | members | topic)\n")
    if not channels:
        print("(no channels visible -- check read scopes / channel membership)")
        return
    for ch in channels[:max_items]:
        topic = _clip((ch.get("topic") or {}).get("value", ""), 60)
        priv = "🔒" if ch.get("is_private") else "#"
        print(f"{ch.get('id', '?')}  {priv}{ch.get('name', '')}  "
              f"[{ch.get('num_members', '?')}]  {topic}")
    print("\n# Next: python scripts/connectors/slack.py <CHANNEL_ID>   (recent messages)")


def list_channel_history(client, channel_arg, max_items):
    channel = channel_arg
    if not CHANNEL_ID_RE.match(channel_arg):
        channel = resolve_channel(client, channel_arg, max_items)
    data = call(client, "conversations.history",
                {"channel": channel, "limit": max_items})
    messages = data.get("messages", [])
    print(f"# Recent messages in {channel} (ts | user | text)\n")
    if not messages:
        print("(no messages -- check history scope / channel membership)")
        return
    for m in messages[:max_items]:
        replies = m.get("reply_count")
        tag = f" [thread: {replies} replies]" if replies else ""
        print(f"{m.get('ts', '?')}  {m.get('user', m.get('bot_id', '?'))}  "
              f"{_clip(m.get('text', ''))}{tag}")
    print("\n# Next: paste a message permalink to FETCH its full thread.")


def fetch_thread(client, url, max_items):
    channel, ts = parse_permalink(url)
    if not channel or not ts:
        sys.stderr.write(
            "Could not parse channel + thread ts from that permalink.\n"
            "Expected form: https://you.slack.com/archives/C0123ABCD/p1699999999123456\n"
        )
        sys.exit(1)
    data = call(client, "conversations.replies",
                {"channel": channel, "ts": ts, "limit": max_items})
    messages = data.get("messages", [])
    print(f"# Thread {channel} @ {ts}  ({len(messages)} message(s))\n")
    if not messages:
        print("(empty thread)")
        return
    for i, m in enumerate(messages):
        role = "PARENT" if i == 0 else f"reply {i}"
        print(f"## [{role}] {m.get('ts', '?')}  {m.get('user', m.get('bot_id', '?'))}")
        print(" ".join((m.get("text", "") or "").split()) or "(no text)")
        print("\n---\n")


def search_messages(client, query, max_items):
    data = call(client, "search.messages", {"query": query, "count": max_items})
    matches = (data.get("messages") or {}).get("matches", [])
    print(f"# Slack search: {query}  (channel | user | text | permalink)\n")
    if not matches:
        print("(no matches)")
        return
    for m in matches[:max_items]:
        ch = (m.get("channel") or {}).get("name", "?")
        who = m.get("username") or m.get("user", "?")
        print(f"#{ch}  {who}  {_clip(m.get('text', ''))}")
        print(f"    {m.get('permalink', '')}")
    print("\n# Next: paste one of those permalinks to FETCH its full thread.")


def main():
    parser = argparse.ArgumentParser(
        description="Unix-philosophy gateway to the Slack Web API for Prompt Fu context."
    )
    parser.add_argument(
        'query', nargs='?', default=None,
        help="Nothing (identity + channels), a channel id/#name, a message permalink, or a search string."
    )
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Output cap per THE PROBE ECONOMY RULE (default: 25; Slack may clamp reads to 15).')
    args = parser.parse_args()

    arg = args.query.strip() if args.query else None
    if arg is None:
        mode = "list"
    elif PERMALINK_RE.match(arg):
        mode = "fetch"
    elif CHANNEL_ID_RE.match(arg) or (' ' not in arg):
        mode = "history"
    else:
        mode = "search"

    token, kind = get_token(mode)
    client = make_client(token)
    try:
        if mode == "list":
            identity_and_list(client, args.max)
        elif mode == "fetch":
            fetch_thread(client, arg, args.max)
        elif mode == "history":
            list_channel_history(client, arg, args.max)
        else:
            search_messages(client, arg, args.max)
    finally:
        client.close()


if __name__ == '__main__':
    main()
