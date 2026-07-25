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

Auth: Authorization: Bearer resolved from --token-env, then MCP_BEARER_TOKEN,
then BOTIFY_API_TOKEN. Which token a given server accepts is ITSELF
unwitnessed until --check says so.

Output is capped by --max / --max-bytes per THE PROBE ECONOMY RULE.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# THE ENVELOPE — INFERRED until witnessed by a GREEN --check. Marked per line.
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "2025-06-18"      # INFERRED: spec revision string
SESSION_HEADER = "Mcp-Session-Id"    # INFERRED: optional per spec
CLIENT_INFO = {"name": "pipulate-mcp", "version": "0.1"}
TIMEOUT = 30.0

DCLASS_NOTE = {
    "D0": "deterministic — same args, same bytes, forever",
    "D1": "stable read — reproducible until server-side state mutates",
    "D2": "time-varying — a NEW OBSERVATION, never a reproduction",
}


def die(msg, code=1):
    sys.stderr.write(msg.rstrip("\n") + "\n")
    sys.exit(code)


def resolve_token(token_env=None):
    """(env_var_name, value) for the first set var; (None, None) if cold.
    If value points to a JSON token file, extracts the access_token field.
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

    default_token_file = Path.home() / ".config" / "pipulate" / "mcp_botify_token.json"
    if default_token_file.is_file():
        try:
            data = json.loads(default_token_file.read_text(encoding="utf-8"))
            tok = data.get("access_token") or data.get("token")
            if tok:
                return "mcp_botify_token.json", tok
        except Exception:
            pass

    val = os.environ.get("BOTIFY_API_TOKEN")
    if val:
        return "BOTIFY_API_TOKEN", val

    return None, None


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
    return client.post(server, json=payload, headers=headers)


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
    # notifications/initialized: a notification (no id). Spec expects 202;
    # fail-soft because a server that skips it should not kill the receipt.
    try:
        post(client, server, {"jsonrpc": "2.0",
                              "method": "notifications/initialized"}, session_id)
    except httpx.HTTPError:
        pass
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
    token_name, token = resolve_token(token_env)
    if not token:
        try:
            with httpx.Client(timeout=15.0, headers={
                    "Accept": "application/json, text/event-stream"}) as c:
                resp = c.post(server, json={"jsonrpc": "2.0", "id": 1,
                                            "method": "tools/list"})
            sys.stderr.write(
                "mcp RED gate1: no bearer token in env (tried "
                "MCP_BEARER_TOKEN, BOTIFY_API_TOKEN); unauthenticated "
                f"envelope reads HTTP {resp.status_code}\n")
        except httpx.HTTPError as e:
            sys.stderr.write(f"mcp RED gate1: no token AND transport failure: {e}\n")
        return 1
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
    tools = ((parse_body(resp) or {}).get("result") or {}).get("tools") or []
    print(f"mcp GREEN {server} protocol={negotiated} "
          f"session={'yes' if session_id else 'no'} tools={len(tools)} "
          f"auth={token_name}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Replay client and envelope witness for remote MCP servers.")
    parser.add_argument("server", help="MCP server URL, e.g. https://mcp.botify.com")
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

    if args.check:
        sys.exit(check(args.server, args.token_env))

    token_name, token = resolve_token(args.token_env)
    if not token:
        die("Missing bearer token: set MCP_BEARER_TOKEN (or BOTIFY_API_TOKEN, "
            "or --token-env NAME). The unauthenticated envelope reading is "
            "available via --check.")
    declared = args.dclass is not None
    dclass = args.dclass or "D2"
    with make_client(token) as client:
        if args.tool:
            call_tool(client, args.server, args.tool, args.args_json,
                      dclass, declared, args.max_bytes)
        else:
            list_tools(client, args.server, args.max)


if __name__ == "__main__":
    main()
