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

The typed word is `render`; the flake.nix connectorCommand line that mints it
is owed, so until it lands the spelling is the interpreter's:

  .venv/bin/python connectors/mcp_render.py decode LINK                # the other keys as a header, then the rules, one per line
  .venv/bin/python connectors/mcp_render.py decode - --nth 2           # the second #conf= on stdin (jira KEY | ... decode -)
  .venv/bin/python connectors/mcp_render.py decode LINK --rules-only   # the rules alone, ready for a file
  .venv/bin/python connectors/mcp_render.py decode LINK --json         # the whole conf as JSON
  .venv/bin/python connectors/mcp_render.py diff LINK_A LINK_B         # header keys that differ, then diff -u of the rules
  .venv/bin/python connectors/mcp_render.py diff - --labels existing suggested   # the first two links on stdin, in text order
  .venv/bin/python connectors/mcp_render.py encode RULES_FILE --from LINK        # mint a link: LINK's conf with RULES_FILE as its rules

Designed for context.txt as a `!` line, e.g.:

  ! jira SVB-123 2>&1 | .venv/bin/python connectors/mcp_render.py diff - --labels existing suggested

LATER, over the stdio relay (npx -y @mcp-b/webmcp-local-relay@latest
--widget-origin https://app.botify.com, a logged-in PocketRender tab opened
once with ?webmcp=1): tools, schema pr_x, call pr_x '{}', one subprocess
speaking JSON-RPC on its stdin and stdout, every call a receipt per THE MCP
RECEIPT RULE. Not built; the relay's --help is a hand step first.

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

PR_URL = "https://app.botify.com/tools/cpap/pocketrender/index.html"
CONF_RE = re.compile(r'#conf=([A-Za-z0-9+/=_-]+)')
RULES_KEY = "renderingRules"


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
    """The #conf= fragment for a conf: compact JSON, zlib, standard base64."""
    raw = json.dumps(conf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


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

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"render {args.mode}: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
