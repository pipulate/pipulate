#!/usr/bin/env python3
# scripts/mcp_dummy_server.py
"""
mcp_dummy_server.py — a FAULT HARNESS for scripts/connectors/mcp.py.

NOT a conformance witness, and the distinction is the whole point. This rig
and mcp.py were written from the SAME spec reading, so their agreement is a
TAUTOLOGY, not a corroboration. What this rig can do is MANUFACTURE FAILURE
and check whether the instrument notices.

  WITNESSED by a full pass:
    - the handshake SEQUENCE executes end to end (initialize -> session
      capture -> notifications/initialized -> tools/list -> tools/call)
    - the Mcp-Session-Id round trip works, and the rig's enforcement of it
      is REAL: a raw-httpx control posts without the header and must be
      refused, or a client that merely echoes correctly proves nothing
    - both body framings parse: application/json and text/event-stream
    - --dclass is FALSIFIABLE, not decorative: D0 must repeat byte-identically,
      D1 must advance, an undeclared class must clamp to D2 and say so
    - the client DISTINGUISHES HTTP success from JSON-RPC success, at every
      gate, and names the RIGHT gate when it fails

  STILL INFERRED after any number of passes:
    - that "2025-06-18" is a protocolVersion a REAL server accepts
    - that "Mcp-Session-Id" is the header a REAL server sets
    - that tools/list and tools/call are spelled as a REAL server spells them
  Only a server of INDEPENDENT AUTHORSHIP promotes those three to OBSERVED.
  The tunnel measured lift coefficients; it did not fly the airplane.

WHY THE REMOTE 401 IS NOT A CONTROL. mcp.botify.com does AUTH BEFORE PARSING,
and this compile's receipt says the rejection fired at INITIALIZE -- the first
request. A reading that cannot vary with the envelope can never confirm one.
Keep it as a regression canary; never cite it as evidence about the handshake.

WHY red.init-rpc-error AND red.notify-rejected EXIST. Three earlier harness
designs all manufactured the version-mismatch red as HTTP 400, which mcp.py's
`status_code != 200` guard catches -- masking the fact that initialize() has
the SAME false-green disease as check(). And no design tested a REFUSED
notifications/initialized, which httpx does not raise on, so a server
rejecting half the handshake produced a clean downstream GREEN. A harness that
only manufactures failures the instrument already survives is decoration.

FAIRNESS NOTE: red.notify-rejected may not describe any real server. That is
irrelevant. A client that silently discards a 4xx on a REQUIRED handshake step
is defective regardless of whether anyone in the wild does this to it.

DELIBERATELY A NOTE, NOT A GATE: the 2025-06-18 revision appears to require
MCP-Protocol-Version on every post-handshake request, and mcp.py sends only
the session header. This rig NOTES that rather than failing on it, because the
reading is unsettled and an independently-authored server (the official MCP
Python SDK's FastMCP over Streamable HTTP) can adjudicate it for the cost of
one flight. Manufacturing a red from a reading is how a rig teaches its own
mistakes back to the code.

SECURITY: binds 127.0.0.1 and there is no reason to widen that. A zero-auth
MCP server reachable off-box is a remote tool-call endpoint for the network.

Usage:
  python scripts/mcp_dummy_server.py --selftest     # the whole flight card
  python scripts/mcp_dummy_server.py --serve        # hold one open by hand
  python scripts/mcp_dummy_server.py --serve --sse
  python scripts/mcp_dummy_server.py --serve --no-session
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SESSION_HEADER = "Mcp-Session-Id"
SERVER_INFO = {"name": "pipulate-mcp-faultharness", "version": "1.0"}
CLIENT = Path(__file__).resolve().parent / "connectors" / "mcp.py"
LINE_CAP = 104  # THE PROBE ECONOMY RULE: bounded rows, always

BASE_CONFIG = {
    "protocol_versions": [PROTOCOL_VERSION],
    "sse": False,
    "session": True,
    "strict_accept": True,
    "require_token": None,
    "rpc_error_on_list": False,
    "init_rpc_error": False,
    "reject_notify": False,
    "log": False,
}
CONFIG = dict(BASE_CONFIG)
SESSIONS = {}
NOTES = []
_COUNTER = {"n": 0}
_LOCK = threading.Lock()

_OPEN_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": True}


# ---------------------------------------------------------------------------
# Tools — one per determinism class, so --dclass becomes falsifiable
# ---------------------------------------------------------------------------
def _echo(args):
    return json.dumps(args, sort_keys=True, separators=(",", ":"))


def _counter(args):
    with _LOCK:
        _COUNTER["n"] += 1
        return str(_COUNTER["n"])


def _now(args):
    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds").replace("+00:00", "Z")


TOOLS = {
    "echo": {"description": "D0 deterministic — arguments as canonical JSON.",
             "inputSchema": _OPEN_SCHEMA, "handler": _echo},
    "counter": {"description": "D1 stable read — advances on every call.",
                "inputSchema": _OPEN_SCHEMA, "handler": _counter},
    "now": {"description": "D2 time-varying — current UTC timestamp.",
            "inputSchema": _OPEN_SCHEMA, "handler": _now},
}


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------
class MCPHandler(BaseHTTPRequestHandler):
    # HTTP/1.1 so httpx keeps the connection alive across the three-call
    # handshake — which makes an accurate Content-Length mandatory on EVERY
    # response, including the empty ones. _send is the only writer.
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        pass  # the rig narrates deliberately, or not at all

    def _say(self, msg):
        if CONFIG["log"]:
            sys.stderr.write(f"  {msg}\n")
            sys.stderr.flush()

    def _note(self, msg):
        if msg not in NOTES:
            NOTES.append(msg)
        self._say(f"NOTE  {msg}")

    def _send(self, status, body=b"", ctype=None, extra=None):
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _rpc(self, obj, status=200, extra=None):
        text = json.dumps(obj)
        if CONFIG["sse"] and status == 200:
            body = f"event: message\ndata: {text}\n\n".encode("utf-8")
            ctype = "text/event-stream"
        else:
            body = text.encode("utf-8")
            ctype = "application/json"
        self._send(status, body, ctype, extra)

    def _err(self, code, message, status=400, rid=None):
        self._rpc({"jsonrpc": "2.0", "id": rid,
                   "error": {"code": code, "message": message}}, status=status)

    def do_GET(self):
        # The spec's server-initiated SSE stream. mcp.py never opens one, and
        # pretending to support it would be the map outrunning the territory.
        self._say("GET — server-initiated stream not implemented (405)")
        self._send(405)

    def do_DELETE(self):
        sid = self.headers.get(SESSION_HEADER)
        SESSIONS.pop(sid, None)
        self._say(f"DELETE — session {(sid or '-')[:8]} terminated")
        self._send(200)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            msg = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._say("PARSE ERROR — body was not JSON")
            return self._err(-32700, "Parse error")

        if isinstance(msg, list):
            # Batching is legal and unexercised by mcp.py. A rig that silently
            # MISHANDLES something is worse than one that refuses it.
            self._say("400 batch request (not implemented by this rig)")
            return self._err(-32600, "batch not implemented by fault harness")
        if not isinstance(msg, dict):
            return self._err(-32600, "expected a JSON object")

        method = msg.get("method", "")
        rid = msg.get("id")
        is_notification = "id" not in msg
        sid = self.headers.get(SESSION_HEADER)
        auth = (self.headers.get("Authorization") or "")
        self._say(f"POST {method or '(none)'} id={rid!r} "
                  f"session={(sid or '-')[:8]} "
                  f"auth={'Bearer' if auth.lower().startswith('bearer ') else 'none'}")

        # GATE A — Accept must offer both media types (Streamable HTTP).
        accept = (self.headers.get("Accept") or "").lower()
        if not ("application/json" in accept and "text/event-stream" in accept):
            if CONFIG["strict_accept"]:
                self._say("GATE A FAILED — Accept lacks a required media type")
                return self._err(
                    -32600,
                    "Accept must offer application/json AND text/event-stream")
            self._note("Accept lacks application/json or text/event-stream")

        # Auth is checked only when a scenario asks for it, so the default
        # flight has exactly ONE variable removed and no others. When it IS
        # asked for, it fires here -- before body parsing -- which reproduces
        # the structural shape of the live mcp.botify.com 401.
        if CONFIG["require_token"] is not None:
            if auth != "Bearer " + CONFIG["require_token"]:
                self._say("401 absent or wrong bearer token")
                return self._send(
                    401, json.dumps({"error": "unauthorized"}).encode("utf-8"),
                    "application/json")

        if method == "initialize":
            return self._initialize(msg, rid)

        # GATE B — everything after the handshake must carry the session.
        if CONFIG["session"]:
            if not sid:
                self._say("GATE B FAILED — no session header")
                return self._err(
                    -32600, f"Missing {SESSION_HEADER}; initialize issued one")
            if sid not in SESSIONS:
                self._say("GATE B FAILED — unknown session id")
                return self._err(-32600, "Unknown session id", status=404, rid=rid)

        # PROTOCOL NOTE, deliberately not a gate. See the module docstring:
        # the reading is unsettled and an independent server can adjudicate it
        # for the cost of one flight. It CANNOT explain the live Botify 401 --
        # that one died at initialize, before any post-handshake request exists.
        if not self.headers.get("MCP-Protocol-Version"):
            self._note("post-handshake request omits MCP-Protocol-Version "
                       "(spec 2025-06-18 appears to require it; cannot explain "
                       "a 401 raised at initialize)")

        if is_notification:
            if CONFIG["reject_notify"]:
                self._say("400 notifications/initialized REFUSED (fault injection)")
                return self._err(-32600,
                                 "fault harness: refusing notifications/initialized")
            if method == "notifications/initialized" and sid in SESSIONS:
                SESSIONS[sid]["initialized"] = True
                self._say("handshake complete")
            return self._send(202)

        if method == "tools/list":
            if CONFIG["session"] and not SESSIONS.get(sid, {}).get("initialized"):
                self._note("tools/list arrived before notifications/initialized")
            if CONFIG["rpc_error_on_list"]:
                # HTTP 200 carrying a JSON-RPC error: legal, and the exact
                # shape that made mcp.py print GREEN with tools=0.
                self._say("200 tools/list -> JSON-RPC error (false-green probe)")
                return self._rpc({"jsonrpc": "2.0", "id": rid,
                                  "error": {"code": -32603,
                                            "message": "fault harness: deliberate "
                                                       "server-side failure"}})
            tools = [{"name": n, "description": s["description"],
                      "inputSchema": s["inputSchema"]} for n, s in TOOLS.items()]
            return self._rpc({"jsonrpc": "2.0", "id": rid,
                              "result": {"tools": tools}})

        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                self._say(f"tools/call unknown tool {name!r} (isError)")
                return self._rpc({
                    "jsonrpc": "2.0", "id": rid,
                    "result": {"isError": True,
                               "content": [{"type": "text",
                                            "text": f"unknown tool: {name}"}]}})
            text = TOOLS[name]["handler"](arguments)
            self._say(f"tools/call {name} -> {len(text)} char(s)")
            return self._rpc({
                "jsonrpc": "2.0", "id": rid,
                "result": {"isError": False,
                           "content": [{"type": "text", "text": text}]}})

        self._say(f"METHOD NOT FOUND — {method!r}")
        return self._err(-32601, f"Method not found: {method}", status=404, rid=rid)

    def _initialize(self, msg, rid):
        params = msg.get("params") or {}
        requested = params.get("protocolVersion")
        cinfo = params.get("clientInfo") or {}
        self._say(f"initialize from {cinfo.get('name', '?')} "
                  f"{cinfo.get('version', '?')} protocolVersion={requested!r}")

        # FAULT INJECTION: HTTP 200 + a JSON-RPC error, and NO session header.
        # The status guard in mcp.py's initialize() cannot see this, which is
        # exactly why the earlier version-mismatch red (an HTTP 400) masked it.
        if CONFIG["init_rpc_error"]:
            self._say("200 initialize -> JSON-RPC error, no session (false-green probe)")
            return self._rpc({"jsonrpc": "2.0", "id": rid,
                              "error": {"code": -32603,
                                        "message": "fault harness: initialize "
                                                   "refused at the RPC layer"}})

        if requested not in CONFIG["protocol_versions"]:
            self._say(f"400 initialize — {requested!r} unsupported "
                      f"(rig speaks {CONFIG['protocol_versions']})")
            return self._rpc(
                {"jsonrpc": "2.0", "id": rid,
                 "error": {"code": -32602,
                           "message": f"unsupported protocolVersion {requested!r}",
                           "data": {"supported": CONFIG["protocol_versions"]}}},
                status=400)

        extra = {}
        if CONFIG["session"]:
            sid = uuid.uuid4().hex
            SESSIONS[sid] = {"initialized": False}
            extra[SESSION_HEADER] = sid
            self._say(f"issued {SESSION_HEADER}={sid[:8]}")
        return self._rpc(
            {"jsonrpc": "2.0", "id": rid,
             "result": {"protocolVersion": requested,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": SERVER_INFO}}, extra=extra)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _start(host="127.0.0.1", port=0):
    httpd = _Server((host, port), MCPHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


# ---------------------------------------------------------------------------
# Client invocation — hermetic, so a rig run can never touch a real credential
# ---------------------------------------------------------------------------
def _hermetic_env():
    """Strip every MCP_* and BOTIFY_* name before injecting the stand-in.

    Without this, mcp.py's resolve_token fallback chain could reach a real
    token file and a harness run could authenticate somewhere real — or pass
    BECAUSE it did, which is the worse of the two.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MCP_", "BOTIFY_"))}
    env["MCP_BEARER_TOKEN"] = "faultharness"
    return env


def _run_client(url, argv):
    return subprocess.run([sys.executable, str(CLIENT), url] + argv,
                          capture_output=True, text=True, timeout=30,
                          env=_hermetic_env(), stdin=subprocess.DEVNULL)


def _payload(stdout):
    """Drop receipt lines (every one starts with '#') so a D0 byte comparison
    is not defeated by the receipt's own observed_at stamp."""
    return "\n".join(ln for ln in stdout.splitlines()
                     if not ln.startswith("#")).strip()


def _last(proc):
    lines = [ln for ln in ((proc.stdout or "") + (proc.stderr or "")
                           ).strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "(silent)"


# ---------------------------------------------------------------------------
# The flight card
# ---------------------------------------------------------------------------
def _green_battery(url):
    """Happy-path assertions, run once per framing. (ok, name, evidence, why)."""
    rows = []

    p = _run_client(url, ["--check"])
    rows.append((p.returncode == 0 and "GREEN" in p.stdout, "check",
                 _last(p), "full handshake reaches tools/list"))

    p = _run_client(url, [])
    listed = all(n in p.stdout for n in TOOLS)
    rows.append((p.returncode == 0 and listed, "list",
                 f"{len(TOOLS)} tools expected, all present" if listed
                 else "tool names missing from tools/list",
                 "tools/list round trips through the session"))

    a = _run_client(url, ["echo", '{"text":"harness"}', "--dclass", "D0"])
    b = _run_client(url, ["echo", '{"text":"harness"}', "--dclass", "D0"])
    rows.append((a.returncode == 0 and "D0 (declared)" in a.stdout, "call.D0",
                 _last(a), "four-tuple receipt with a declared class"))
    same = _payload(a.stdout) == _payload(b.stdout) and _payload(a.stdout) != ""
    rows.append((same, "D0-repeat",
                 "identical bytes across two calls" if same
                 else "D0 tool was NOT byte-stable — the class label is a lie",
                 "D0 must be reproducible or the receipt overclaims"))

    c = _run_client(url, ["counter", "{}", "--dclass", "D1"])
    d = _run_client(url, ["counter", "{}", "--dclass", "D1"])
    moved = (c.returncode == 0 and d.returncode == 0
             and _payload(c.stdout) != _payload(d.stdout))
    rows.append((moved, "D1-differ",
                 "counter advanced between calls" if moved
                 else "D1 tool did not advance — state is not exercised",
                 "D1 must be able to change or the class is untested"))

    e = _run_client(url, ["now", "{}"])
    clamped = "UNDECLARED" in e.stdout and "D2" in e.stdout
    rows.append((e.returncode == 0 and clamped, "D2-clamp",
                 "undeclared class clamped to D2" if clamped
                 else "undeclared --dclass did NOT clamp to D2",
                 "an unlabelled result must never inherit D0's authority"))

    f = _run_client(url, ["no_such_tool", "{}", "--dclass", "D0"])
    rows.append((f.returncode == 0 and "unknown tool" in f.stdout, "tool-error",
                 "isError surfaced in the client receipt",
                 "a tool-level failure must reach the operator"))

    return rows


# MANUFACTURED REDS. A rig that has never been SEEN reporting red is not an
# instrument. Each row names the GATE the client must blame -- misattribution
# is a defect, because a receipt naming the wrong gate sends the operator to
# the wrong place.
RED_SCENARIOS = [
    ("red.version", {"protocol_versions": ["1999-01-01"]}, ["--check"], 1,
     "gate2", "client must notice a protocolVersion the server refuses"),
    ("red.bearer", {"require_token": "not-the-token"}, ["--check"], 1,
     "gate2", "reproduces the structural shape of the live mcp.botify.com 401"),
    ("red.rpc-error", {"rpc_error_on_list": True}, ["--check"], 1,
     "gate3", "HTTP 200 carrying a JSON-RPC error is NOT health"),
    ("red.init-rpc-error", {"init_rpc_error": True}, ["--check"], 1,
     "gate2", "same disease one gate earlier -- and the client must blame "
              "gate2, not gate3, or the receipt misdirects the operator"),
    ("red.notify-rejected", {"reject_notify": True}, ["--check"], 1,
     "gate2", "httpx does not raise on 4xx, so a server refusing half the "
              "handshake produced a clean GREEN"),
]


def _control_session():
    """Prove GATE B is real, not decorative.

    mcp.py always echoes the session header, so its green cannot distinguish
    'the client round-trips correctly' from 'the server never checked'. Post
    tools/list with raw httpx, correct Accept, and NO session header; the
    refusal must NAME the session so a GATE A 400 cannot be mistaken for it.
    """
    import httpx
    CONFIG.update(BASE_CONFIG)
    SESSIONS.clear()
    httpd, port = _start()
    try:
        with httpx.Client(timeout=10.0, headers={
                "Accept": "application/json, text/event-stream"}) as client:
            resp = client.post(f"http://127.0.0.1:{port}/mcp",
                               json={"jsonrpc": "2.0", "id": 1,
                                     "method": "tools/list"})
        try:
            message = (resp.json().get("error") or {}).get("message", "")
        except ValueError:
            message = ""
        ok = resp.status_code == 400 and SESSION_HEADER in message
        return ok, f"HTTP {resp.status_code} — {message or '(no message)'}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def selftest():
    if not CLIENT.exists():
        sys.stderr.write(f"fault harness ABORT: client not found at {CLIENT}\n")
        return 1

    print("# MCP FAULT HARNESS — scripts/connectors/mcp.py, UNMODIFIED")
    print(f"# instrument: {CLIENT}")
    print(f"# harness:    {Path(__file__).resolve()}\n")

    rows = []
    for sse in (False, True):
        CONFIG.update(BASE_CONFIG)
        CONFIG["sse"] = sse
        SESSIONS.clear()
        with _LOCK:
            _COUNTER["n"] = 0
        httpd, port = _start()
        framing = "sse" if sse else "json"
        try:
            for ok, name, evidence, why in _green_battery(
                    f"http://127.0.0.1:{port}/mcp"):
                rows.append((ok, f"{framing}.{name}", evidence, why))
        finally:
            httpd.shutdown()
            httpd.server_close()

    for name, overrides, argv, want_code, want_text, why in RED_SCENARIOS:
        CONFIG.update(BASE_CONFIG)
        CONFIG.update(overrides)
        SESSIONS.clear()
        httpd, port = _start()
        try:
            p = _run_client(f"http://127.0.0.1:{port}/mcp", argv)
            combined = (p.stdout or "") + (p.stderr or "")
            ok = p.returncode == want_code and want_text in combined
            rows.append((ok, name,
                         f"want exit {want_code}/{want_text}, got "
                         f"{p.returncode} — {_last(p)}", why))
        except subprocess.TimeoutExpired:
            rows.append((False, name, "timed out after 30s", why))
        finally:
            httpd.shutdown()
            httpd.server_close()

    ok, evidence = _control_session()
    rows.append((ok, "control.session", evidence,
                 "proves GATE B enforcement is real, not decorative"))

    width = max(len(r[1]) for r in rows)
    for ok, name, evidence, why in rows:
        if len(evidence) > LINE_CAP:
            evidence = evidence[:LINE_CAP - 1] + "\u2026"
        print(f"  {'[ok]  ' if ok else '[FAIL]'} {name.ljust(width)}  {evidence}")
        if not ok:
            print(f"         \u21b3 {why}")

    if NOTES:
        print("\n# PROTOCOL NOTES — client behaviours a stricter server may reject:")
        for note in NOTES:
            print(f"  - {note}")

    passed = sum(1 for r in rows if r[0])
    total = len(rows)
    print(f"\n# {passed}/{total} checks passed")
    if passed != total:
        print("# failed: " + ", ".join(r[1] for r in rows if not r[0]))
        return 1
    print("# MECHANISM WITNESSED — handshake sequence, session round trip")
    print("#   (enforcement proved by control), both framings, all three")
    print("#   determinism classes, and correct GATE ATTRIBUTION on five")
    print("#   manufactured failures.")
    print("# STILL INFERRED — that \"2025-06-18\", \"Mcp-Session-Id\", and the")
    print("#   tools/* spellings are what a REAL server wants. This harness")
    print("#   shares mcp.py's spec reading; agreement is tautology. Only a")
    print("#   server of INDEPENDENT AUTHORSHIP promotes those three.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Zero-auth MCP fault harness for scripts/connectors/mcp.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the whole flight card and exit; the exit "
                             "code is the answer.")
    parser.add_argument("--serve", action="store_true",
                        help="hold a server open for hand-driving.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host (default 127.0.0.1 — do not widen).")
    parser.add_argument("--port", type=int, default=8765,
                        help="bind port (default 8765; 0 picks ephemeral).")
    parser.add_argument("--sse", action="store_true",
                        help="--serve only: frame responses as text/event-stream.")
    parser.add_argument("--no-session", action="store_true",
                        help="never issue Mcp-Session-Id.")
    parser.add_argument("--lax", action="store_true",
                        help="downgrade the Accept gate to a note.")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.serve:
        parser.error("choose --selftest (one command) or --serve (hand-driving)")

    CONFIG.update(BASE_CONFIG)
    CONFIG.update(sse=args.sse, session=not args.no_session,
                  strict_accept=not args.lax, log=True)
    httpd, port = _start(args.host, args.port)
    url = f"http://{args.host}:{port}/mcp"
    print(f"# MCP fault harness serving on {url}")
    print(f"# framing={'sse' if args.sse else 'json'}  "
          f"session={'on' if CONFIG['session'] else 'off'}  "
          f"accept={'strict' if CONFIG['strict_accept'] else 'lax'}  "
          f"auth=NONE (header ignored)")
    print(f"# tools: {', '.join(TOOLS)}")
    print(f"#   MCP_BEARER_TOKEN=faultharness python {CLIENT} {url} --check")
    print(f"#   MCP_BEARER_TOKEN=faultharness python {CLIENT} {url} "
          "echo '{\"text\":\"hi\"}' --dclass D0")
    print("# Ctrl-C to stop.\n")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n# harness down")
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
