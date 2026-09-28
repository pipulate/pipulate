#!/usr/bin/env python3
# connectors/mcp_render.py
"""
mcp_render.py — Decode, diff or mint a PocketRender share link.

THE CONF IS IN THE LINK (READ 2026-09-27, deed 1629, off the two PocketRender
links on one SVB ticket): a share link's #conf= fragment is standard base64 of
a zlib-compressed JSON object with nine keys -- urls, devices, userAgent,
extraHeaders, renderingRules (a list, one rule per item), js (a dict of the
eight injectJs* hooks, INFERRED from the key count), presetFilters,
detectAPIs, execEnvUri -- so the existing and the suggested configs on a
ticket decode offline with the standard library, and the three rule-text
diffs a ticket needs (original|vendor, original|ours, vendor|ours) need no
render at all. The render farm is for the metrics only.

The typed word is `render` (a flake.nix connectorCommand line since 2026-09-27);
the interpreter's spelling works anywhere the word is not on PATH:

  .venv/bin/python connectors/mcp_render.py decode LINK                # the other keys as a header, then the rules, one per line
  .venv/bin/python connectors/mcp_render.py decode - --nth 2           # the second #conf= on stdin (jira KEY | ... decode -)
  .venv/bin/python connectors/mcp_render.py decode LINK --rules-only   # the rules alone, ready for a file
  .venv/bin/python connectors/mcp_render.py decode LINK --json         # the whole conf as JSON
  .venv/bin/python connectors/mcp_render.py diff LINK_A LINK_B         # header keys that differ, then diff -u of the rules
  .venv/bin/python connectors/mcp_render.py diff - --labels existing suggested   # the first two links on stdin, in text order
  .venv/bin/python connectors/mcp_render.py encode RULES_FILE --from LINK        # mint a link: LINK's conf with RULES_FILE as its rules

Designed for context.txt as a `!` line, e.g.:

  ! jira SVB-123 2>&1 | .venv/bin/python connectors/mcp_render.py diff - --labels existing suggested

THE RELAY LANES (landed 2026-09-28, the relay's --help read by hand first):

  .venv/bin/python connectors/mcp_render.py tools                  # spawn the relay, initialize, tools/list: one line per tool
  .venv/bin/python connectors/mcp_render.py schema pr_x            # one tool's inputSchema as JSON
  .venv/bin/python connectors/mcp_render.py call pr_x '{"k":"v"}'  # tools/call; exit 1 on a JSON-RPC error or isError

Each lane spawns the relay (RELAY_CMD; --relay overrides it, --widget-origin
names the page origin it admits) with LD_LIBRARY_PATH cleared, the loader
lesson of 2026-09-27, and speaks newline-delimited JSON-RPC on the relay's
stdin and stdout: initialize, notifications/initialized, then one request and
its reply by id. The WebSocket on 127.0.0.1:9333 the help names is the relay's
face toward the PocketRender tab (opened once with ?webmcp=1, the two
chrome://flags set, logged in), never ours. Every request prints one MCP
RECEIPT line (method, id, the bytes sent) per THE MCP RECEIPT RULE, and a
verdict token closes each lane: RELAY_INIT_OK, RELAY_TOOLS n=, RELAY_CALL_OK on
the way through; RELAY_INIT_NO_REPLY, RELAY_TOOLS_NO_REPLY, RELAY_CALL_ERROR
with the relay's stderr tail under them. With no tab open the list reads n=0 or
times out, and the initialize reply alone witnesses that stdio is the
transport; until it has, stdio is INFERRED from the client configs that launch
the relay as a command.

THE ROUND TRIP IS THE RECEIPT: encode decodes what it just minted and refuses
with exit 1 when the two confs differ, so a minted link that prints is a link
that decodes to the rules it was given. Whether PocketRender itself reads it
is witnessed by a human opening it in a logged-in tab, and nothing here can
claim that.

No auth, no wallet slot, no --check, on noop.py's reasoning: a share link is
readable by whoever holds it, and a green row for a decoder is a green row
for nothing.

COMPILE-LANE CAUTION: a conf carries the client's URL and its rule text, and
a ticket's links name the client's project. Trusted payloads only.
"""

import sys
import re
import json
import zlib
import base64
import difflib
import argparse
import os
import time
import queue
import shlex
import threading
import subprocess
import collections

PR_URL = "https://app.botify.com/tools/cpap/pocketrender/index.html"
CONF_RE = re.compile(r'#conf=([A-Za-z0-9+/=_-]+)')
RULES_KEY = "renderingRules"
# THE RELAY (its --help read by hand, 2026-09-28): a local WebSocket on 127.0.0.1:9333
# faces the PocketRender tab; the face toward this client is stdio, INFERRED from the
# client configs until a reply on stdout witnesses it. npx re-resolves @latest on every
# run and needs node on PATH; a pinned version, then a Nix derivation, is the graft.
RELAY_CMD = "npx -y @mcp-b/webmcp-local-relay@latest"
WIDGET_ORIGIN = "https://app.botify.com"
PROTOCOL_VERSION = "2025-06-18"


def read_source(arg):
    """The text an argument names: '-' is stdin, a link is itself, a readable path is its file, anything else is itself."""
    if arg == "-":
        return sys.stdin.read()
    if arg.startswith(("http://", "https://")):
        return arg
    try:
        with open(arg, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return arg


def fragments_in(text):
    """Every #conf= fragment in text, in order of appearance."""
    return CONF_RE.findall(text)


def decode_fragment(b64):
    """The conf object behind one #conf= fragment: base64 (standard, then urlsafe), zlib, JSON."""
    padded = b64 + "=" * (-len(b64) % 4)
    raw = None
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            raw = zlib.decompress(decoder(padded))
            break
        except (ValueError, zlib.error):
            continue
    if raw is None:
        raise ValueError("the fragment is not base64 of a zlib stream")
    conf = json.loads(raw)
    if not isinstance(conf, dict):
        raise ValueError(f"the conf is a JSON {type(conf).__name__}, not an object")
    return conf


def encode_conf(conf):
    """The #conf= fragment for a conf: compact JSON, zlib at level 6 (PocketRender's own,
    read by sweep at deed 1632, so a mint is byte-identical to the vendor's), standard base64."""
    raw = json.dumps(conf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 6)).decode("ascii")


def rule_lines(conf):
    """The rules as lines: a list one per item, a string split on newlines, anything else as JSON."""
    rules = conf.get(RULES_KEY)
    if isinstance(rules, list):
        return [str(item) for item in rules]
    if isinstance(rules, str):
        return rules.split("\n")
    return [] if rules is None else [json.dumps(rules, default=str)]


def header_lines(conf, cap=200):
    """One '# key: value' line per key other than the rules: scalars raw, lists joined, dicts as key=size."""
    lines = []
    for key, value in conf.items():
        if key == RULES_KEY:
            continue
        if isinstance(value, dict):
            shown = "{" + ", ".join(
                f"{k}={len(v) if isinstance(v, (str, list, dict)) else v}"
                for k, v in value.items()) + "}"
        elif isinstance(value, list):
            shown = ", ".join(str(v) for v in value) if value else "(none)"
        elif isinstance(value, str):
            shown = value or "(empty)"
        else:
            shown = json.dumps(value)
        cut = f" ...(+{len(shown) - cap})" if len(shown) > cap else ""
        lines.append(f"# {key}: {shown[:cap]}{cut}")
    return lines


def pick_fragment(text, nth, where):
    """The nth (1-based) #conf= fragment in text, refusing with the count when it is out of range."""
    found = fragments_in(text)
    if not found:
        raise ValueError(f"no #conf= fragment in {where}")
    if nth < 1 or nth > len(found):
        raise ValueError(f"{where} holds {len(found)} #conf= fragment(s); --nth {nth} is out of range")
    return found[nth - 1]


def cmd_decode(args):
    where = "stdin" if args.link == "-" else args.link[:60]
    b64 = pick_fragment(read_source(args.link), args.nth, where)
    conf = decode_fragment(b64)
    if args.json:
        print(json.dumps(conf, indent=2, ensure_ascii=False))
        return 0
    rules = rule_lines(conf)
    if not args.rules_only:
        print(f"# PocketRender conf: {len(b64)} base64 chars, {len(rules)} rule line(s)")
        for line in header_lines(conf):
            print(line)
        print()
    shown = rules[:args.max]
    for line in shown:
        print(line)
    if len(rules) > len(shown):
        print(f"# ... +{len(rules) - len(shown)} more rule line(s) (raise -n/--max)")
    if not args.rules_only:
        print("\n# Next: python connectors/mcp_render.py diff LINK_A LINK_B   (header keys that differ, then diff -u of the rules)")
        print("#       python connectors/mcp_render.py encode RULES_FILE --from LINK   (mint a link from a rules file)")
    return 0


def cmd_diff(args):
    if len(args.sources) == 1:
        source = args.sources[0]
        where = "stdin" if source == "-" else source[:60]
        found = fragments_in(read_source(source))
        if len(found) < 2:
            raise ValueError(f"one source needs two #conf= fragments; {where} holds {len(found)}")
        chosen = found[:2]
    elif len(args.sources) == 2:
        chosen = [pick_fragment(read_source(source), 1, "stdin" if source == "-" else source[:60])
                  for source in args.sources]
    else:
        raise ValueError("diff takes one source holding two links, or two sources holding one each")
    left_conf, right_conf = [decode_fragment(b64) for b64 in chosen]
    a_label, b_label = args.labels or ("left", "right")
    keys = sorted(set(left_conf) | set(right_conf))
    differing = [k for k in keys if k != RULES_KEY and left_conf.get(k) != right_conf.get(k)]
    print(f"# header keys that differ: {', '.join(differing) or 'none'}")
    for key in differing:
        left = json.dumps(left_conf.get(key), ensure_ascii=False)[:120]
        right = json.dumps(right_conf.get(key), ensure_ascii=False)[:120]
        print(f"#   {key}: {a_label} {left}  |  {b_label} {right}")
    left, right = rule_lines(left_conf), rule_lines(right_conf)
    diff = list(difflib.unified_diff(left, right, a_label, b_label, lineterm="", n=args.context))
    changed = sum(1 for line in diff
                  if line[:1] in ("+", "-") and not line.startswith(("+++", "---")))
    print(f"# rules: {len(left)} line(s) {a_label}, {len(right)} line(s) {b_label}, {changed} changed line(s)")
    for line in diff:
        print(line)
    return 0


def cmd_encode(args):
    text = read_source(args.template)
    where = "stdin" if args.template == "-" else args.template[:60]
    b64 = pick_fragment(text, args.nth, where)
    template = decode_fragment(b64)
    with open(args.rules_file, encoding="utf-8") as handle:
        lines = handle.read().rstrip("\n").split("\n")
    conf = dict(template)
    conf[RULES_KEY] = "\n".join(lines) if isinstance(template.get(RULES_KEY), str) else lines
    if args.url:
        conf["urls"] = [args.url]
    if args.user_agent is not None:
        conf["userAgent"] = args.user_agent
    fragment = encode_conf(conf)
    if decode_fragment(fragment) != conf:
        sys.stderr.write("round trip FAILED: the minted fragment does not decode to the conf it was made from\n")
        return 1
    found = re.search(r'(https?://[^\s#()\[\]]+)#conf=' + re.escape(b64), text)
    base = found.group(1) if found else PR_URL
    sys.stderr.write(f"minted: {len(lines)} rule line(s), {len(fragment)} base64 chars, round trip ok\n")
    print(f"{base}#conf={fragment}")
    return 0


def _relay_argv(relay, widget_origin):
    """The relay's argv: the --relay string split the way a shell would, plus the origin it admits."""
    return shlex.split(relay) + ["--widget-origin", widget_origin]


def _spawn_relay(argv):
    """Spawn the relay on stdio pipes; one thread per output stream feeds a queue of (tag, line)."""
    env = {**os.environ, "LD_LIBRARY_PATH": ""}
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    lines = queue.Queue()

    def pump(stream, tag):
        for line in iter(stream.readline, ""):
            lines.put((tag, line.rstrip("\n")))
        lines.put((tag, None))

    for stream, tag in ((proc.stdout, "out"), (proc.stderr, "err")):
        threading.Thread(target=pump, args=(stream, tag), daemon=True).start()
    return proc, lines


class RelaySession:
    """One relay process: initialize once, then one request and its reply by id, on stdio."""

    def __init__(self, relay, widget_origin, timeout):
        self.argv = _relay_argv(relay, widget_origin)
        self.timeout = timeout
        self.noise = []
        self.stderr_tail = collections.deque(maxlen=20)
        self.next_id = 1
        self.proc, self.lines = _spawn_relay(self.argv)

    def send(self, obj):
        line = json.dumps(obj, separators=(",", ":"))
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        return line

    def await_reply(self, want_id):
        """The JSON-RPC message carrying want_id, or None when the timeout passes or stdout closes."""
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                tag, line = self.lines.get(timeout=remaining)
            except queue.Empty:
                return None
            if line is None:
                if tag == "out":
                    return None
                continue
            if tag == "err":
                self.stderr_tail.append(line)
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self.noise.append(line)
                continue
            if isinstance(msg, dict) and msg.get("id") == want_id:
                return msg
            self.noise.append(line)

    def request(self, method, params):
        """Send one request, print its receipt, wait for its reply; None when none came."""
        rid = self.next_id
        self.next_id += 1
        sent = self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        print(f"# MCP RECEIPT [OBSERVED, D1]: transport=stdio server={' '.join(self.argv)} "
              f"method={method} id={rid} sent={sent}")
        return self.await_reply(rid)

    def initialize(self):
        reply = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "pipulate-render", "version": "0.1"}})
        if reply is not None and "error" not in reply:
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return reply

    def diagnostics(self):
        """What the relay said outside the protocol: stdout that was not JSON-RPC, the stderr tail."""
        for line in self.noise[-20:]:
            print(f"# relay stdout, not JSON-RPC: {line}")
        for line in self.stderr_tail:
            print(f"# relay stderr: {line}")

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def _open_relay(args):
    """Spawn and initialize: the session on RELAY_INIT_OK, None after a printed verdict otherwise."""
    session = RelaySession(args.relay, args.widget_origin, args.timeout)
    reply = session.initialize()
    if reply is None:
        print(f"RELAY_INIT_NO_REPLY: no JSON-RPC reply to id 1 on stdout within {args.timeout:.0f}s"
              " (stdio is not the transport, or the relay wants something before it answers)")
        session.diagnostics()
        session.close()
        return None
    if "error" in reply:
        print(f"RELAY_INIT_ERROR {json.dumps(reply['error'], ensure_ascii=False)[:300]}")
        session.diagnostics()
        session.close()
        return None
    result = reply.get("result", {})
    info = result.get("serverInfo", {})
    print(f"RELAY_INIT_OK protocol={result.get('protocolVersion')} "
          f"server={info.get('name')} {info.get('version')}")
    return session


def _list_tools(session, timeout):
    """The tools/list result, or None after a printed verdict."""
    reply = session.request("tools/list", {})
    if reply is None:
        print(f"RELAY_TOOLS_NO_REPLY: initialize answered, tools/list did not within {timeout:.0f}s"
              " (the relay may hold the list until a PocketRender tab connects)")
        session.diagnostics()
        return None
    if "error" in reply:
        print(f"RELAY_TOOLS_ERROR {json.dumps(reply['error'], ensure_ascii=False)[:300]}")
        session.diagnostics()
        return None
    return reply.get("result", {}).get("tools", [])


def cmd_tools(args):
    session = _open_relay(args)
    if session is None:
        return 1
    try:
        tools = _list_tools(session, args.timeout)
    finally:
        session.close()
    if tools is None:
        return 1
    print(f"RELAY_TOOLS n={len(tools)}")
    if args.json:
        print(json.dumps(tools, indent=2, ensure_ascii=False))
        return 0
    for tool in tools:
        desc = " ".join(str(tool.get("description", "")).split())
        print(f"{tool.get('name')}\t{desc[:100]}")
    if not tools:
        print("# 0 tools: is a PocketRender tab open with ?webmcp=1, the two chrome://flags set,"
              " and its origin the --widget-origin?")
    print("\n# Next: render schema <tool>      (one tool's inputSchema)")
    print("#       render call <tool> '{}'   (tools/call; a JSON-RPC error names the schema)")
    return 0


def cmd_schema(args):
    session = _open_relay(args)
    if session is None:
        return 1
    try:
        tools = _list_tools(session, args.timeout)
    finally:
        session.close()
    if tools is None:
        return 1
    for tool in tools:
        if tool.get("name") == args.tool:
            print(json.dumps(tool.get("inputSchema", {}), indent=2, ensure_ascii=False))
            return 0
    names = ", ".join(str(tool.get("name")) for tool in tools) or "(none listed)"
    print(f"RELAY_SCHEMA_UNLISTED {args.tool}: the relay lists {names}")
    return 1


def cmd_call(args):
    arguments = json.loads(args.arguments)
    if not isinstance(arguments, dict):
        raise ValueError("the arguments must be one JSON object")
    session = _open_relay(args)
    if session is None:
        return 1
    try:
        reply = session.request("tools/call", {"name": args.tool, "arguments": arguments})
        if reply is None:
            print(f"RELAY_CALL_NO_REPLY within {args.timeout:.0f}s")
            session.diagnostics()
            return 1
    finally:
        session.close()
    if "error" in reply:
        print(f"RELAY_CALL_ERROR {json.dumps(reply['error'], ensure_ascii=False)[:2000]}")
        return 1
    result = reply.get("result", {})
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for item in result.get("content", []):
            if item.get("type") == "text":
                print(item.get("text", ""))
            else:
                print(json.dumps(item, ensure_ascii=False)[:2000])
    if result.get("isError"):
        print("RELAY_CALL_ERROR isError=true: the tool ran and refused; its reason is the text above")
        return 1
    print("RELAY_CALL_OK")
    return 0


def main():
    parser = argparse.ArgumentParser(
        # ONE SOURCE FOR THREE SURFACES: the sources roster reads this
        # docstring by AST, the registry face installs it as __doc__, and
        # --help prints it here.
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-n", "--max", type=int, default=200,
                        help="Rule lines decode prints (default: 200, more than any conf seen so far; a cut is announced).")
    modes = parser.add_subparsers(dest="mode", required=True)

    decode = modes.add_parser("decode", help="print one conf: the other keys as a header, then the rules")
    decode.add_argument("link", help="a PocketRender link, a file holding one, or - for stdin")
    decode.add_argument("--nth", type=int, default=1, help="which #conf= in the source, 1-based (default: the first)")
    decode.add_argument("--rules-only", action="store_true", help="the rules alone, one per line, no header and no breadcrumb")
    decode.add_argument("--json", action="store_true", help="the whole conf as indented JSON")
    decode.set_defaults(func=cmd_decode)

    diff = modes.add_parser("diff", help="two confs: header keys that differ, then diff -u of the rules")
    diff.add_argument("sources", nargs="+", help="two links (or files, or -), or one source holding two links")
    diff.add_argument("--labels", nargs=2, metavar=("A", "B"), help="names for the two sides (default: left right)")
    diff.add_argument("--context", type=int, default=3, help="context lines around each change (default: 3)")
    diff.set_defaults(func=cmd_diff)

    encode = modes.add_parser("encode", help="mint a link: a template conf with a rules file as its rules")
    encode.add_argument("rules_file", help="the rules, one per line, as decode --rules-only prints them")
    encode.add_argument("--from", dest="template", required=True,
                        help="the link (or file, or -) whose conf supplies every other key")
    encode.add_argument("--nth", type=int, default=1, help="which #conf= in the template source (default: the first)")
    encode.add_argument("--url", help="replace the conf's single url")
    encode.add_argument("--user-agent", help="replace the conf's userAgent")
    encode.set_defaults(func=cmd_encode)

    def relay_options(sub, timeout):
        sub.add_argument("--relay", default=RELAY_CMD,
                         help="the relay command, split like a shell would (default: %(default)s)")
        sub.add_argument("--widget-origin", default=WIDGET_ORIGIN,
                         help="the PocketRender origin the relay admits (default: %(default)s)")
        sub.add_argument("--timeout", type=float, default=timeout,
                         help="seconds to wait for each reply (default: %(default)s)")

    tools = modes.add_parser("tools", help="spawn the relay, initialize, tools/list: one line per tool")
    relay_options(tools, 20)
    tools.add_argument("--json", action="store_true", help="the whole tools list as JSON")
    tools.set_defaults(func=cmd_tools)

    schema = modes.add_parser("schema", help="one tool's inputSchema as JSON, read off tools/list")
    schema.add_argument("tool", help="the tool's name as tools/list prints it")
    relay_options(schema, 20)
    schema.set_defaults(func=cmd_schema)

    call = modes.add_parser("call", help="tools/call one tool with a JSON object of arguments")
    call.add_argument("tool", help="the tool's name as tools/list prints it")
    call.add_argument("arguments", nargs="?", default="{}", help="one JSON object (default: an empty one)")
    relay_options(call, 90)
    call.add_argument("--json", action="store_true", help="the whole result as JSON")
    call.set_defaults(func=cmd_call)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"render {args.mode}: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
