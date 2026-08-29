#!/usr/bin/env python3
# scripts/connectors/mcp.py
"""
mcp.py — Replay client for remote MCP servers (Streamable HTTP transport).

THE INSTRUMENT THAT WITNESSES THE ENVELOPE. Every handshake constant below is
INFERRED from the MCP spec (2025-06-18 revision) until this file's own --check
goes GREEN against a live server. That first GREEN is the banking receipt for
THE MCP RECEIPT RULE in foo_files.py. Wrong inferences must die LOUD at a
named gate; nothing here silently falls back.

Golden-path modes, auto-detected from positionals:

  python scripts/connectors/mcp.py                                # IDENTITY: token state + usage; opens no socket
  python scripts/connectors/mcp.py <server>                       # LIST: initialize -> tools/list
  python scripts/connectors/mcp.py <server> <tool> '<args-json>'  # CALL: initialize -> tools/call
  python scripts/connectors/mcp.py <server> --check               # CHECK: envelope health; exit code is the answer

Designed to be dropped into adhoc.txt as a `!` chisel-strike:

  ! python scripts/connectors/mcp.py https://mcp.botify.com --check; echo "exit=$?"

THE FOUR-TUPLE RECEIPT: every call prints (server, verb, tool, args) with args
echoed BYTE-FOR-BYTE from argv — the raw string as submitted, never a
re-serialized parse. A paraphrased receipt is not a receipt.

DETERMINISM CLASS rides every receipt (--dclass D0|D1|D2). The connector
cannot know a tool's class, so the CALLER declares it; an undeclared class
clamps to D2 and says so — a possibly-time-varying result must never be
mistaken for a reproduction.

Auth: Authorization: <scheme> <token>. The token is resolved from --token-env,
then MCP_BEARER_TOKEN, then the derived warmed file, then BOTIFY_API_TOKEN. The
SCHEME defaults to Bearer and is overridden per call with --auth-scheme, because
it is a per-SERVER fact and not a per-vendor one: mcp.botify.com wants an OAuth
Bearer, while a static-token MCP server under the same vendor wants "Token".
Which token AND which scheme a given server accepts is ITSELF unwitnessed until
--check says so.

Output is capped by --max / --max-bytes per THE PROBE ECONOMY RULE.
"""

import os
import sys
import json
import time
import atexit
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, quote

import httpx

# ---------------------------------------------------------------------------
# THE ENVELOPE — INFERRED until witnessed by a GREEN --check. Marked per line.
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "2025-06-18"      # INFERRED: spec revision string
SESSION_HEADER = "Mcp-Session-Id"    # INFERRED: optional per spec
CLIENT_INFO = {"name": "pipulate-mcp", "version": "0.1"}
TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# THE FDR CHANNEL (landed 2026-07-29; PENDING until a compiled receipt shows a
# written file). Convicted same day: this client READ status codes,
# content-type, and Mcp-Session-Id -- gated on them, printed them on RED --
# and PERSISTED NOTHING. Gate-and-print is a CVR habit wearing an FDR label.
# Every exchange now records the response side; the atexit hook flushes the
# receipt, so the recorder survives die() -- a RED check still writes a GREEN
# receipt, which is the defining FDR property: the recording exists BECAUSE
# of the crash, not despite it.
#
# FRAME DOC (mcp-receipt-v1) -- an FDR is undecodable without its frame:
#   frame, recorded_at, protocol_version_sent, client_info,
#   server, verb, tool, args_raw (byte-for-byte, per the four-tuple),
#   dclass, auth_env (env var NAME only; the token value NEVER touches disk),
#   exchanges[]: jsonrpc_method, http_status, response_headers (full dict),
#     session_id_sent, session_id_returned, elapsed_seconds,
#     body_sha256, body_bytes.
# Receipts land under browser_cache/mcp/<host>/ -- gitignored wire-truth
# territory, same as every other capture lane in this repo.
# ---------------------------------------------------------------------------
RECEIPT_FRAME = "mcp-receipt-v1"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXCHANGES = []
_RECEIPT_META = {}


def arm_receipt(server, verb, tool=None, raw_args=None, dclass=None,
                auth_env=None):
    """Arm the recorder before takeoff; the atexit hook is the flush."""
    _RECEIPT_META.update({
        "server": server, "verb": verb, "tool": tool,
        "args_raw": raw_args, "dclass": dclass, "auth_env": auth_env,
    })


def _record_exchange(method, resp, started, sent_session_id=None):
    body = resp.content or b""
    _EXCHANGES.append({
        "jsonrpc_method": method,
        "http_status": resp.status_code,
        "response_headers": dict(resp.headers),
        "session_id_sent": sent_session_id,
        "session_id_returned": resp.headers.get(SESSION_HEADER),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
    })


def _flush_receipt():
    if not _EXCHANGES or not _RECEIPT_META.get("server"):
        return
    try:
        host = urlparse(_RECEIPT_META["server"]).netloc or "unknown-host"
        out_dir = _REPO_ROOT / "browser_cache" / "mcp" / host
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        verb_slug = (_RECEIPT_META.get("verb") or "session").replace("/", "_")
        path = out_dir / f"{stamp}__{verb_slug}.json"
        path.write_text(json.dumps({
            "frame": RECEIPT_FRAME,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "protocol_version_sent": PROTOCOL_VERSION,
            "client_info": CLIENT_INFO,
            **_RECEIPT_META,
            "exchanges": _EXCHANGES,
        }, indent=2, default=str), encoding="utf-8")
        sys.stderr.write(f"# FDR receipt: {path}\n")
    except OSError as exc:
        sys.stderr.write(f"# FDR receipt write failed: {exc}\n")


atexit.register(_flush_receipt)

DCLASS_NOTE = {
    "D0": "deterministic — same args, same bytes, forever",
    "D1": "stable read — reproducible until server-side state mutates",
    "D2": "time-varying — a NEW OBSERVATION, never a reproduction",
}


# ---------------------------------------------------------------------------
# THE DERIVED CREDENTIAL PATH. The DERIVED-PATH RULE aimed at credentials
# rather than at writes: the file a client reads is a pure function of the
# server it is talking to, so a bearer minted for one resource is structurally
# incapable of being sent to another. Collision is unrepresentable because
# quote() escapes every character a path could carry, and adding an Nth server
# costs zero configuration lines.
#
# token_path_for IS DUPLICATED VERBATIM in scripts/connectors/mcp_warm.py, on
# purpose: the connector contract makes each file self-contained (no shared
# imports), and walk_cartridge.py already duplicates foo_cartridge's primitives
# for the same reason. The two definitions must stay byte-identical, so the
# straddle probe COMPARES THEIR OUTPUT instead of trusting that they agree.
# ---------------------------------------------------------------------------
TOKEN_DIR = Path.home() / ".config" / "pipulate" / "mcp"
LEGACY_TOKEN_FILE = Path.home() / ".config" / "pipulate" / "mcp_botify_token.json"


def token_path_for(resource):
    """Credential path for one MCP server. A root path collapses to the host."""
    parsed = urlparse(resource or "")
    host = (parsed.netloc or "unknown-host").lower()
    path = (parsed.path or "").strip("/")
    stem = host if not path else f"{host}__{quote(path, safe='')}"
    return TOKEN_DIR / f"{stem}.json"


def resolve_existing_token_file(resource):
    """(path, is_legacy). Derived first; the pre-derivation file second.

    NO SILENT MOVE. Relocating a credential from inside a resolver is a
    mutation wearing a read path's label. The legacy branch is self-clearing:
    the next browser warm writes the derived path and it stops firing.
    """
    derived = token_path_for(resource)
    if derived.is_file():
        return derived, False
    if LEGACY_TOKEN_FILE.is_file():
        return LEGACY_TOKEN_FILE, True
    return derived, False


def die(msg, code=1):
    sys.stderr.write(msg.rstrip("\n") + "\n")
    sys.exit(code)


def _expiry_note(data):
    """Return a human-readable verdict on a warmed token's clock, or None
    when the record carries none.

    THE CINDERELLA RUNG, READ-ONLY HALF. mcp_warm.py stamps obtained_at
    (ISO, UTC) and expires_in; the 2026-07-29 vendor flight minted a
    300-second access token, which goes stale long before the operator's
    memory of minting it does. Until a refresh actuation exists, a stale
    token arrives disguised as an HTTP 401 at gate2 -- a symptom pointing
    nowhere near its cause. This function only READS the clock and names
    what it sees; refreshing is a separate actuation and this must never
    grow into one, because a token resolver that silently re-mints is a
    resolver whose failures stop being visible.

    The token VALUE never touches this function's output.
    """
    obtained_at = data.get("obtained_at")
    expires_in = data.get("expires_in")
    if not obtained_at or not expires_in:
        return None
    try:
        minted = datetime.fromisoformat(obtained_at)
        if minted.tzinfo is None:
            minted = minted.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - minted).total_seconds()
        life = float(expires_in)
    except (TypeError, ValueError):
        return None
    remaining = life - age
    if remaining > 0:
        return f"~{int(remaining)}s left of a {int(life)}s life"
    has_refresh = "yes" if data.get("refresh_token") else "no"
    return (f"EXPIRED {int(-remaining)}s ago (life was {int(life)}s); "
            f"refresh_token present: {has_refresh}; re-mint with "
            "python scripts/connectors/mcp_warm.py")


def resolve_token(token_env=None, server=None):
    """(env_var_name, value) for the first set var; (None, None) if cold.
    If value points to a JSON token file, extracts the access_token field.
    When a server is named, the warmed-file rung is DERIVED from it
    (~/.config/pipulate/mcp/<host>.json) and the pre-derivation
    mcp_botify_token.json is read only as a fallback, with a note on stderr.
    """
    from pathlib import Path
    names = ([token_env] if token_env else []) + [
        "MCP_BEARER_TOKEN",
        "MCP_TOKEN_FILE",
        "BOTIFY_TOKEN_FILE",
    ]
    for name in names:
        val = os.environ.get(name)
        if val:
            expanded = Path(val).expanduser()
            if expanded.is_file():
                try:
                    data = json.loads(expanded.read_text(encoding="utf-8"))
                    tok = data.get("access_token") or data.get("token") or val
                    return f"{name}:{expanded.name}", tok
                except Exception:
                    pass
            return name, val

    if server:
        default_token_file, is_legacy = resolve_existing_token_file(server)
        if is_legacy:
            sys.stderr.write(
                f"# mcp credential: reading the pre-derivation file "
                f"{LEGACY_TOKEN_FILE.name}; the next browser warm writes "
                f"{token_path_for(server)}\n")
    else:
        default_token_file = LEGACY_TOKEN_FILE
    if default_token_file.is_file():
        try:
            data = json.loads(default_token_file.read_text(encoding="utf-8"))
            tok = data.get("access_token") or data.get("token")
            if tok:
                note = _expiry_note(data)
                if note:
                    sys.stderr.write(f"# mcp token clock: {note}\n")
                return default_token_file.name, tok
        except Exception:
            pass

    val = os.environ.get("BOTIFY_API_TOKEN")
    if val:
        return "BOTIFY_API_TOKEN", val

    return None, None


def identity():
    """No-argument mode: what this client holds, and what it still needs.

    THE FREED WORD ARRIVED EMPTY-HANDED (2026-08-25). `mcp` came free when the
    human roster was renamed to `sources`, and an alias pointing at a REQUIRED
    positional would have answered the freed word with argparse exit 2 -- a
    worse first keypress than the roster it replaced. Every other connector
    already has a bare-word identity walk; this is that walk, and it is why
    freeing the word and claiming it rode in the same car.

    IT REPORTS, IT NEVER ASSERTS (ATTRIBUTED-VOICE): a token RESOLVING is not a
    token being ACCEPTED. Only --check can say accepted, because only --check
    posts. resolve_token's own stderr clock note rides along unchanged, so an
    expired token says so HERE instead of arriving disguised as a 401 later.

    READ-ONLY BY CONSTRUCTION: no socket opens, no receipt is armed (so the
    atexit flush returns early and writes nothing), and no token VALUE is ever
    printed. Safe to echo as a `!` chisel-strike.
    """
    token_name, token = resolve_token()
    print("# mcp.py -- replay client for remote MCP servers (Streamable HTTP)")
    print(f"# protocol : {PROTOCOL_VERSION} (INFERRED until a GREEN --check)")
    if token:
        # THE LANE IS PART OF THE CLAIM (convicted 2026-08-29 by this walk's own
        # receipt). The prior string said "env lane resolved from
        # mcp_botify_token.json" while every env var was unset and the FILE rung
        # had fired -- a label naming a lane that did not run, which is the
        # ATTRIBUTED-VOICE mechanical test failing on the first line a newcomer
        # reads. It was also a REGRESSION: the string it replaced said only
        # "resolved from", which was correct. resolve_token returns a bare env
        # var NAME, or "NAME:file.json" when an env var pointed at a file, or a
        # bare "<stem>.json" when the warmed-file rung fired; only the last of
        # those carries a .json suffix and no colon, so the discrimination is
        # exact rather than heuristic.
        lane = "file lane" if (":" not in token_name
                               and token_name.endswith(".json")) else "env lane"
        print(f"# token    : {lane} resolved from {token_name} (value never printed)")
        print("#            resolved is not accepted -- only --check posts")
    else:
        print("# token    : no env-lane token (MCP_BEARER_TOKEN, MCP_TOKEN_FILE,")
        print("#            BOTIFY_TOKEN_FILE, BOTIFY_API_TOKEN all unset)")
    known = sorted(TOKEN_DIR.glob("*.json")) if TOKEN_DIR.is_dir() else []
    if LEGACY_TOKEN_FILE.is_file():
        known.append(LEGACY_TOKEN_FILE)
    if known:
        print(f"# creds    : {len(known)} warmed file(s); values never printed")
        for path in known:
            tag = " (pre-derivation)" if path == LEGACY_TOKEN_FILE else ""
            try:
                note = _expiry_note(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                note = "unreadable"
            print(f"#            {path.stem}{tag} -- {note or 'no clock recorded'}")
    else:
        print(f"# creds    : none warmed yet; they land under {TOKEN_DIR}")
    print("#")
    print("# This client never guesses a server. Name one:")
    print("#   mcp <server> --check           envelope health; exit code is the answer")
    print("#   mcp <server>                   initialize -> tools/list")
    print("#   mcp <server> <tool> '<json>'   initialize -> tools/call")
    print("#")
    print("# Mint or refresh a bearer:  python scripts/connectors/mcp_warm.py")


def make_client(token):
    return httpx.Client(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=TIMEOUT,
    )


def parse_body(resp):
    """Plain JSON or SSE framing (`data: {...}` lines). Returns the last
    JSON object seen, or None. SSE-vs-JSON is itself an INFERRED seam."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        objs = []
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                try:
                    objs.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
        return objs[-1] if objs else None
    try:
        return resp.json()
    except ValueError:
        return None


def post(client, server, payload, session_id=None):
    headers = {SESSION_HEADER: session_id} if session_id else {}
    started = time.perf_counter()
    resp = client.post(server, json=payload, headers=headers)
    _record_exchange(payload.get("method", "?"), resp, started,
                     sent_session_id=session_id)
    return resp


def initialize(client, server):
    """The INFERRED handshake: initialize, capture session id, notify.
    Dies at a named gate on any surprise; success returns
    (session_id_or_None, negotiated_protocol, server_info)."""
    payload = {
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {},
                   "clientInfo": CLIENT_INFO},
    }
    resp = post(client, server, payload)
    if resp.status_code in (401, 403):
        die(f"mcp RED gate2: token rejected at initialize (HTTP {resp.status_code})")
    if resp.status_code != 200:
        die(f"mcp RED gate2: initialize HTTP {resp.status_code} — handshake "
            f"inference wrong?\n{resp.text[:300]}")
    body = parse_body(resp) or {}
    if body.get("error") is not None:
        die(f"mcp RED gate2: initialize returned JSON-RPC error "
            f"{body['error']} — HTTP 200 is not JSON-RPC success")
    result = body.get("result") or {}
    negotiated = result.get("protocolVersion")
    session_id = resp.headers.get(SESSION_HEADER)
    # notifications/initialized: a notification (no id), spec expects 202.
    # Stay fail-soft on a TRANSPORT error and on a server that merely ignores
    # the notification (any 2xx), but be LOUD on an explicit 4xx REFUSAL:
    # httpx does not raise on 4xx, so the old bare `except: pass` swallowed a
    # server refusing half the handshake and greened downstream. Convicted by
    # the fault harness's red.notify-rejected scenario (19/20, the one FAIL).
    # This CANNOT touch the Botify 401 -- that fires at the FIRST initialize
    # POST, above, before any notification exists.
    try:
        ack = post(client, server, {"jsonrpc": "2.0",
                                    "method": "notifications/initialized"}, session_id)
    except httpx.HTTPError:
        ack = None
    if ack is not None and ack.status_code >= 400:
        die(f"mcp RED gate2: server refused notifications/initialized "
            f"(HTTP {ack.status_code}) -- the handshake is incomplete")
    return session_id, negotiated, result.get("serverInfo") or {}


def print_receipt(server, verb, tool, raw_args, dclass, declared):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag = "declared" if declared else "UNDECLARED — clamped to D2"
    print("# MCP RECEIPT (four-tuple; args byte-for-byte as submitted)")
    print(f"# server: {server}")
    print(f"# verb:   {verb}")
    print(f"# tool:   {tool or '-'}")
    print(f"# args:   {raw_args if raw_args is not None else '-'}")
    print(f"# determinism: {dclass} ({tag}) — {DCLASS_NOTE[dclass]}")
    print(f"# observed_at: {now}")


def list_tools(client, server, max_items):
    session_id, negotiated, sinfo = initialize(client, server)
    resp = post(client, server,
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, session_id)
    if resp.status_code != 200:
        die(f"mcp RED gate3: tools/list HTTP {resp.status_code}\n{resp.text[:300]}")
    parsed = parse_body(resp) or {}
    if parsed.get("error") is not None:
        die(f"mcp RED gate3: tools/list returned JSON-RPC error {parsed['error']}")
    tools = (parsed.get("result") or {}).get("tools") or []
    print(f"# {server} — protocol {negotiated} | server "
          f"{sinfo.get('name', '?')} | {len(tools)} tool(s) | "
          f"session={'yes' if session_id else 'no'}\n")
    for t in tools[:max_items]:
        print(f"{t.get('name', '?')}  {str(t.get('description', ''))[:80]}")
    if len(tools) > max_items:
        print(f"... +{len(tools) - max_items} more (raise -n/--max)")


def call_tool(client, server, tool, raw_args, dclass, declared, max_bytes):
    try:
        args = json.loads(raw_args) if raw_args.strip() else {}
    except json.JSONDecodeError as e:
        die(f"args-json failed to parse: {e}")
    session_id, _negotiated, _sinfo = initialize(client, server)
    print_receipt(server, "tools/call", tool, raw_args, dclass, declared)
    resp = post(client, server,
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": tool, "arguments": args}}, session_id)
    if resp.status_code != 200:
        die(f"mcp RED gate3: tools/call HTTP {resp.status_code}\n{resp.text[:300]}")
    text = json.dumps(parse_body(resp), indent=2, default=str)
    if len(text) > max_bytes:
        text = text[:max_bytes] + (f"\n... [truncated at {max_bytes} bytes "
                                   "per THE PROBE ECONOMY RULE]")
    print(text)


def check(server, token_env):
    """SELECT 1 for the envelope. Exit 0 GREEN, exit 1 RED, gate-named stderr.
    Tokenless runs still take the unauthenticated envelope reading, because
    401/400/404 discriminates address-right / handshake-wrong / join-wrong."""
    token_name, token = resolve_token(token_env, server)
    if not token:
        arm_receipt(server, "check-unauthenticated")
        try:
            with httpx.Client(timeout=15.0, headers={
                    "Accept": "application/json, text/event-stream"}) as c:
                started = time.perf_counter()
                resp = c.post(server, json={"jsonrpc": "2.0", "id": 1,
                                            "method": "tools/list"})
                _record_exchange("tools/list", resp, started)
            sys.stderr.write(
                "mcp RED gate1: no bearer token in env (tried "
                "MCP_BEARER_TOKEN, BOTIFY_API_TOKEN); unauthenticated "
                f"envelope reads HTTP {resp.status_code}\n")
        except httpx.HTTPError as e:
            sys.stderr.write(f"mcp RED gate1: no token AND transport failure: {e}\n")
        return 1
    arm_receipt(server, "check", auth_env=token_name)
    try:
        with make_client(token) as client:
            session_id, negotiated, _sinfo = initialize(client, server)
            resp = post(client, server,
                        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                        session_id)
    except httpx.HTTPError as e:
        sys.stderr.write(f"mcp RED gate2: transport failure: {e}\n")
        return 1
    if resp.status_code != 200:
        sys.stderr.write(f"mcp RED gate3: tools/list HTTP {resp.status_code}\n")
        return 1
    parsed = parse_body(resp) or {}
    if parsed.get("error") is not None:
        sys.stderr.write(f"mcp RED gate3: tools/list JSON-RPC error {parsed['error']}\n")
        return 1
    tools = (parsed.get("result") or {}).get("tools") or []
    print(f"mcp GREEN {server} protocol={negotiated} "
          f"session={'yes' if session_id else 'no'} tools={len(tools)} "
          f"auth={token_name}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Replay client and envelope witness for remote MCP servers.")
    parser.add_argument("server", nargs="?", default=None,
                        help="MCP server URL, e.g. https://mcp.botify.com. "
                             "Omit for the identity walk.")
    parser.add_argument("tool", nargs="?", default=None,
                        help="Tool name for CALL mode; omit for tools/list.")
    parser.add_argument("args_json", nargs="?", default="{}",
                        help="Arguments JSON for CALL mode (default: {}).")
    parser.add_argument("--check", action="store_true",
                        help="Envelope health probe; exit code is the answer.")
    parser.add_argument("--dclass", choices=["D0", "D1", "D2"], default=None,
                        help="Determinism class of THIS call, declared by the "
                             "caller. Undeclared clamps to D2.")
    parser.add_argument("-n", "--max", type=int, default=25,
                        help="LIST cap per THE PROBE ECONOMY RULE (default: 25).")
    parser.add_argument("--max-bytes", type=int, default=4000,
                        help="CALL result cap in bytes (default: 4000).")
    parser.add_argument("--token-env", default=None,
                        help="Env var holding the bearer token (default: "
                             "MCP_BEARER_TOKEN, then BOTIFY_API_TOKEN).")
    args = parser.parse_args()

    if args.server is None:
        identity()
        return

    if args.check:
        sys.exit(check(args.server, args.token_env))

    token_name, token = resolve_token(args.token_env, args.server)
    if not token:
        die("Missing bearer token: set MCP_BEARER_TOKEN (or BOTIFY_API_TOKEN, "
            "or --token-env NAME). The unauthenticated envelope reading is "
            "available via --check.")
    declared = args.dclass is not None
    dclass = args.dclass or "D2"
    with make_client(token) as client:
        if args.tool:
            arm_receipt(args.server, "tools/call", tool=args.tool,
                        raw_args=args.args_json, dclass=dclass,
                        auth_env=token_name)
            call_tool(client, args.server, args.tool, args.args_json,
                      dclass, declared, args.max_bytes)
        else:
            arm_receipt(args.server, "tools/list", auth_env=token_name)
            list_tools(client, args.server, args.max)


if __name__ == "__main__":
    main()
