#!/usr/bin/env python3
# scripts/connectors/slack.py
"""
slack.py — Bring a Slack channel or message thread into context.

A Unix-philosophy gateway to the Slack Web API for Prompt Fu context.

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

# TOKEN CLASS, READ BEFORE THE NETWORK CALL. Slack's settings pages hand out at
# least five credential families and only two of them can ever reach
# conversations.*. Convicted 2026-08-27 across five cycles: a configuration
# token (xoxe), then an app-level token (xapp-), then a bare app credential
# were each pasted into SLACK_USER_TOKEN, and each produced a DIFFERENT
# downstream error -- missing_scope, then not_allowed_token_type, then
# invalid_auth -- so the symptom kept moving while the actual mistake, which is
# WHICH PAGE the string was copied from, was never named by anything.
# THE PREFIX IS DECISIVE AND FREE: Slack documents these prefixes, so this
# refusal costs no round trip, reads no value, and names the remedy by page
# instead of by scope. It is strictly earlier and more specific than check()'s
# gate 3, which can only speak after auth.test answers.
# FAIL-OPEN ON THE UNKNOWN, deliberately: an unrecognized prefix passes straight
# through to the API, because a family Slack invents next year must not be
# locally unusable. Only classes KNOWN to be incapable are refused.
WRONG_TOKEN_CLASS = {
    "xapp-": ("app-level", "Basic Information -> App-Level Tokens"),
    "xoxe": ("configuration", "the app index page -> Your App Configuration Tokens"),
    "xwfp-": ("workflow", "a workflow run"),
}


def refuse_wrong_class(token, var_name):
    """Exit loudly when a prefix proves this token can never read a message."""
    for prefix, (label, origin) in WRONG_TOKEN_CLASS.items():
        if token.startswith(prefix):
            sys.stderr.write(
                f"{var_name} holds a {label} token ({prefix}...), which can "
                "never call conversations.* no matter which scopes it carries.\n"
                f"That string is minted on {origin}.\n"
                "The one you want is on OAuth & Permissions, in the section "
                "headed 'OAuth Tokens for Your Workspace', labelled User OAuth "
                "Token, beginning xoxp-. If that section instead PROMISES to "
                "generate tokens once you finish installing, the app is not "
                "installed and no workspace token exists yet.\n"
            )
            sys.exit(1)


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
    if user:
        refuse_wrong_class(user, "SLACK_USER_TOKEN")
    if bot:
        refuse_wrong_class(bot, "SLACK_BOT_TOKEN")
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
    # THE FRONT DOOR NAMED THE WRONG TOKEN (convicted 2026-08-27, by the whole
    # week). This branch fires when NOTHING is set -- the earliest moment a
    # stranger, or a fresh machine, or the operator after a revoke, meets this
    # connector -- and it said "copy the bot token (xoxb-...)". A bot reads
    # only channels it has been INVITED to, so for the permalink workflow this
    # connector exists to serve, a bot token is the one credential that cannot
    # work. The golden path settled today is a USER token carrying four read
    # scopes and zero bot scopes. Six days of token-class confusion, and the
    # message at the front door was pointing at the wrong page throughout.
    # THE VARIABLE ORDER IS PART OF THE MESSAGE. get_token PREFERS the user
    # token, check() reads it first, and the module docstring says a user
    # token dodges the bot-token thread-read restriction -- only this string
    # listed the bot token first. The one surface that speaks to someone
    # holding NOTHING contradicted every surface that speaks to someone
    # holding SOMETHING, which is the direction that misleads.
    # THE APPROVAL SENTENCE IS NOT DECORATION. Workspace app approval is
    # STRUCTURALLY INVISIBLE from a terminal: this connector cannot tell "no
    # token yet" from "no token POSSIBLE until an admin acts", and those two
    # worlds have entirely different next moves. Naming the second costs one
    # line and stops the reader hunting a button that is not there.
    sys.stderr.write(
        "Missing environment variable(s): SLACK_USER_TOKEN (or SLACK_BOT_TOKEN)\n"
        "The golden path is a USER token (xoxp-), not a bot token: a bot reads "
        "only channels it was invited to, which cannot serve the permalink "
        "mode. Create an app from a manifest at https://api.slack.com/apps "
        "declaring FOUR user scopes -- channels:read, groups:read, "
        "channels:history, groups:history -- and zero bot scopes, install it, "
        "then copy the User OAuth Token.\n"
        "If your workspace requires admin approval the install button reads "
        "'Request to Install' and NO token exists until a human approves it. "
        "That is a person, not a setting you can change.\n"
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
        if err == "invalid_auth":
            # THE MOST-SEEN ERROR HAD NO HINT AT ALL until 2026-08-26, when it
            # was hit three times across one ride while the two errors that DID
            # carry a hint carried the WRONG one. invalid_auth means Slack does
            # not recognize the string, which is a different repair from every
            # other rung: not a scope to add, not a class to swap, a token to
            # obtain. Ordered by how often each cause is the real one.
            hint = ("\nHint: Slack does not recognize this string at all. In "
                    "order: (1) the app was never INSTALLED, so no workspace "
                    "token exists yet -- OAuth & Permissions shows a promise to "
                    "generate tokens rather than tokens; (2) a later scope "
                    "change forced a reinstall, and reinstalling REVOKES the "
                    "previous token; (3) what was pasted is an app credential "
                    "(Client Secret, Signing Secret) rather than an OAuth "
                    "token -- those carry no xox prefix.")
        elif err == "not_allowed_token_type":
            # WRONG CLASS IS NOT A MISSING SCOPE, AND THE TWO REPAIRS DIVERGE.
            # These errors shared one hint until 2026-08-26, when an app-level
            # token answered not_allowed_token_type and the hint sent the
            # operator back to the scopes page -- where no grant could ever
            # have helped, because Slack refused the token's CLASS before it
            # looked at a single scope.
            hint = ("\nHint: WRONG TOKEN CLASS -- not a scope problem, and no "
                    "grant can fix it. conversations.* needs a WORKSPACE token "
                    "(xoxp- user, or xoxb- bot) copied from OAuth & Permissions. "
                    "An app-level token (xapp-, minted on Basic Information), a "
                    "configuration token, or a workflow token can never call it.")
        elif err == "missing_scope":
            hint = ("\nHint: right token class, insufficient grants. Add the "
                    "scopes named above under OAuth & Permissions -> Scopes -> "
                    "USER Token Scopes (scroll past Bot Token Scopes), click "
                    "Reinstall, then paste the NEW token -- reinstalling "
                    "revokes the old one.")
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


# ----------------------------------------------------------------------------
# Health check (THE EXIT-CODE PROTOCOL: the exit code IS the whole answer)
# ----------------------------------------------------------------------------
def scope_clause(granted):
    """Render the scope gap for one auth.test X-OAuth-Scopes header.

    SEARCH IS OPTIONAL, AND THE OLD SPELLING CALLED IT MISSING. The need set
    added search:read for every user token, so the app manifest authored on
    2026-08-27 -- four read scopes, search DELIBERATELY excluded because
    workspace-wide search is the one scope an approver actually argues about
    -- was guaranteed to print MISSING search:read on its FIRST successful
    green. A warning that fires on the DESIGNED configuration is the
    retire-the-canary failure with a loaded gun attached: after a week of
    scope-chasing it would send the operator back to the scopes page for a
    reinstall, and reinstalling REVOKES the token he just pasted.

    THE GOLDEN PATH IS LIST AND FETCH. Those four scopes are required by the
    two modes this connector is actually used for, so their absence is a real
    MISSING. search:read enables a mode the connector supports and the
    operator does not use, so it is reported as a CAPABILITY (+ SEARCH) and
    never as a deficiency. The bot-token case needs no special branch: a bot
    can never hold search:read, and the caller's note line already says so.

    EXTRACTED SO IT CAN BE PROBED WITHOUT A CREDENTIAL. check()'s green branch
    needs a LIVE token, and the workspace install sits in an admin approval
    queue, so the change is structurally unstraddleable in situ -- the same
    shape as gate 3, which is still unwitnessed for exactly that reason. A
    pure function over the header string is testable from an import, in both
    worlds, with no network and no secret. Fail-soft is preserved: no header
    means no clause, because an absent header is a fact about Slack's response
    and must never read as zero scopes.
    """
    if not granted:
        return ""
    have = {s.strip() for s in granted.split(",") if s.strip()}
    need = {"channels:read", "groups:read",
            "channels:history", "groups:history"}
    gap = sorted(need - have)
    if gap:
        return f" | {len(have)} scope(s), MISSING {','.join(gap)}"
    extra = " + SEARCH" if "search:read" in have else ""
    return f" | {len(have)} scope(s), LIST+FETCH covered{extra}"


def check():
    """SELECT 1 for the wallet board: exit 0 GREEN, exit 1 RED.

    ONE row, not two. A bot token that cannot call search.messages is not a
    BAD credential, it is a NARROWER one, and a red row for a working token
    would teach the wrong thing. auth.test is the SELECT 1; the green line
    names which token answered and what that costs, so the honesty rides in
    the receipt instead of in an extra color.

    Slack answers HTTP 200 even on failure, so the verdict is the `ok` field.
    """
    user = os.getenv("SLACK_USER_TOKEN")
    bot = os.getenv("SLACK_BOT_TOKEN")
    token, kind = (user, "user") if user else (bot, "bot")
    if not token:
        sys.stderr.write(
            "slack RED gate1: neither SLACK_USER_TOKEN nor SLACK_BOT_TOKEN set\n")
        return 1
    # GATE 1, SECOND CLAUSE -- THE BOARD COULD NOT SEE THE CLASS.
    # get_token() gained refuse_wrong_class on 2026-08-27, but check() reads
    # os.getenv directly and never calls it, so the wallet board kept spending
    # a network round trip and rendering "gate2: user token rejected
    # (invalid_auth)" for a string whose PREFIX already said app-level.
    # WITNESSED IN THAT SAME COMPILE, two instruments disagreeing about one
    # token: the class probe read `class: app-level` while `wallet check slack`
    # read gate2. The board is the surface an operator actually looks at after
    # pasting a credential, and it named the wrong organ.
    # A LOCAL CLAUSE OF GATE 1, not a new gate number: gate1 is the pre-flight
    # (do we hold a usable credential at all), gate2 is the network verdict,
    # gate3 is identity. A wrong CLASS is decided before any socket opens, so
    # it belongs to gate1 and must not consume a round trip to say so.
    # ONE LINE ON STDERR, deliberately: wallet.check_slot renders err[-1] as
    # the row, so a multi-line refusal arrives on the board truncated to its
    # last sentence. refuse_wrong_class is the right message for a human at a
    # terminal and the wrong SHAPE for a table row; this is the board's
    # spelling of the same finding.
    for prefix, (label, origin) in WRONG_TOKEN_CLASS.items():
        if token.startswith(prefix):
            sys.stderr.write(
                f"slack RED gate1: that is a {label} token ({prefix}...), "
                f"minted on {origin}; conversations.* needs the User OAuth "
                "Token (xoxp-) from OAuth & Permissions\n")
            return 1
    try:
        with httpx.Client(base_url=API_BASE, timeout=15.0,
                          headers={"Authorization": f"Bearer {token}",
                                   "Accept": "application/json"}) as client:
            resp = client.get("/auth.test")
    except httpx.HTTPError as e:
        sys.stderr.write(f"slack RED gate2: transport failure: {e}\n")
        return 1
    if resp.status_code != 200:
        sys.stderr.write(f"slack RED gate2: HTTP {resp.status_code}\n")
        return 1
    try:
        data = resp.json()
    except ValueError:
        sys.stderr.write("slack RED gate2: non-JSON response from auth.test\n")
        return 1
    if not data.get("ok"):
        sys.stderr.write(
            f"slack RED gate2: {kind} token rejected "
            f"({data.get('error', 'unknown_error')})\n")
        return 1
    # GATE 3 -- IS THIS A WORKSPACE TOKEN AT ALL? auth.test needs no scopes and
    # succeeds for token classes that can never touch conversations.*, and it
    # answers those with NO user field. Witnessed 2026-08-26: an app-level token
    # (scopes connections:write, authorizations:read, app_configurations:write)
    # printed `slack GREEN ? @ ? (user token)` and carried the board to GOLD,
    # while every real read died on not_allowed_token_type in the same minute.
    # The two question marks WERE the finding; the row rendered them as
    # decoration and the tally counted the credential as live.
    # THIS IS NOT NARROWNESS, which is why it reds where a thin bot token does
    # not. Narrower is not worse -- see this function's docstring. A wrong CLASS
    # is worse: no grant can ever repair it, so a green row sends the operator
    # to the scopes page for a cycle that cannot succeed.
    # OBSERVED, NOT INFERRED: the absent user field is read off a receipt rather
    # than guessed from a token prefix, so a class Slack invents next year trips
    # the same gate with no lookup table to maintain.
    # UNWITNESSED ON SHIP: a dead token dies at gate 2 before reaching here, so
    # this branch cannot be straddled while the credential is invalid. It needs
    # a LIVE non-workspace token to fire, and that is a manufactured failure,
    # not a probe.
    if not data.get("user"):
        sys.stderr.write(
            "slack RED gate3: auth.test succeeded but named no user, so this "
            "is not a workspace token -- most likely an app-level (xapp-), "
            "configuration, or workflow token. Copy the User OAuth Token from "
            "OAuth & Permissions instead; nothing on the Basic Information "
            "page can read a message.\n")
        return 1
    # THE CREDENTIAL IS NOT THE CAPABILITY. auth.test requires NO scopes, so a
    # token granted nothing at all still prints GREEN here and takes the board
    # to GOLD. Witnessed 2026-08-26: a freshly minted token greened this row
    # while bare `slack` died on conversations.list with missing_scope, in the
    # same minute -- so the board answered "is this credential live" while the
    # human was asking "can it read anything". Slack returns the grant list in
    # an X-OAuth-Scopes response header on this very call, so visibility costs
    # nothing. STILL GREEN WHEN NARROW, deliberately: a narrower token is not a
    # bad one (see this docstring), so narrowness becomes visible without
    # becoming a failure. FAIL-SOFT: no header, no clause -- a missing header
    # is a fact about Slack's response and must not read as zero scopes.
    note = "" if kind == "user" else "; SEARCH needs SLACK_USER_TOKEN"
    scopes = scope_clause(resp.headers.get("x-oauth-scopes"))
    print(f"slack GREEN {data.get('user', '?')} @ {data.get('team', '?')} "
          f"({kind} token{note}){scopes}")
    return 0


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
    parser.add_argument('--check', action='store_true',
                        help='SELECT 1 health check: one GREEN line on stdout and '
                             'exit 0, or one gate-named RED line on stderr and '
                             'exit 1. Never interactive.')
    args = parser.parse_args()

    if args.check:
        sys.exit(check())

    arg = args.query.strip() if args.query else None
    if arg is None:
        mode = "list"
    elif PERMALINK_RE.match(arg):
        # A SLACK URL CARRIES TWO DIFFERENT COORDINATES UNDER ONE SHAPE.
        # "Copy link" on a MESSAGE yields /archives/<CID>/p<digits> -- channel
        # plus thread ts. The same control on a CHANNEL yields /archives/<CID>
        # alone. Both match PERMALINK_RE, so routing every match to FETCH made
        # the channel form die on "could not parse channel + thread ts": an
        # error about threads, shown to someone who never named one, whose only
        # suggested remedy is a URL form they do not have. Read the ts to
        # decide -- present means a thread was named, absent means a channel
        # was. A parse miss falls through to fetch_thread so ONE authority owns
        # the honest parse error instead of a second copy being written here.
        url_channel, url_ts = parse_permalink(arg)
        if url_ts:
            mode = "fetch"
        elif url_channel:
            mode = "history"
            arg = url_channel
        else:
            mode = "fetch"
    elif CHANNEL_ID_RE.match(arg) or (' ' not in arg):
        mode = "history"
    else:
        mode = "search"

    # THE SIBLING-COMMAND HINT (convicted 2026-08-27, operator transcript).
    # The disambiguation rule routes ANY single word to channel-history mode,
    # so `slack check` -- a plausible typo for `slack --check` -- becomes a
    # lookup for a channel named "check", and `slack warm` becomes a lookup
    # for one named "warm". WITNESSED: the operator typed `slack warm` twice,
    # once on each side of an ignition, meaning to run `warm slack` (wallet
    # first). Both times the token-class refusal fired and printed a message
    # about OAuth pages, so the wallet warm never ran and nothing said so.
    # TWO MISTAKES, ONE PRINTOUT, in his own hands.
    # A HINT, NEVER A REFUSAL, and that is the whole design. A workspace may
    # legitimately contain a channel named #warm, so refusing would break a
    # real invocation to protect against a typo -- the same fail-open polarity
    # WRONG_TOKEN_CLASS uses for prefixes it does not recognize. This writes
    # one line to stderr and falls straight through; if the channel exists it
    # is fetched exactly as before, and the note reads as a note.
    # LOCAL, AND USED ONCE. Module scope was rejected: nothing imports this,
    # no probe reads it, and a module-level constant would imply a contract
    # with a consumer that does not exist.
    # ABOVE get_token ON PURPOSE, so the hint survives a dead credential --
    # the exact world the transcript was recorded in. A hint that only prints
    # once auth already works cannot fire on the day it was needed.
    sibling = {
        "check": "did you mean `slack --check`? (the health check is a flag)",
        "help": "did you mean `slack --help`?",
        "warm": "did you mean `warm slack`? (the wallet is the first word)",
    }
    if mode == "history" and arg in sibling:
        sys.stderr.write(f"# note: {sibling[arg]} -- reading it as a channel name.\n")
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
