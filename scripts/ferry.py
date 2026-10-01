#!/usr/bin/env python3
"""
ferry.py -- carry the Mac's shadow posts to Pipulate Prime, overwriting nothing.

The Mac writes articles only into its shadow corpora (blogs.shadow.json);
Prime owns the real repos. This reads both sides, refuses any file whose slug,
permalink is already taken on Prime, renumbers a taken date+sort_order upward on the copy, and copies the rest
over one SSH login. Dry run by default; --yes copies. It never commits on
Prime: copied files show up untracked in `git status` there.

    ferry                 dry run for article, grim, bot
    ferry grim --yes      copy only the grim posts
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

HOST = os.environ.get("PIPULATE_FERRY_TO", "mike@nixos.local")
SHADOW_CFG = Path(os.environ.get("PIPULATE_FERRY_SHADOW", "~/.config/pipulate/blogs.shadow.json")).expanduser()
DEFAULT_ALIASES = ("article", "grim", "bot")
SSH = ["ssh", "-o", "ControlMaster=auto", "-o", "ControlPath=/tmp/pipulate-ferry-%C",
       "-o", "ControlPersist=60", "-o", "ConnectTimeout=10", HOST]
ENV = {**os.environ, "LD_LIBRARY_PATH": ""}
FIELD_RE = re.compile(r"(permalink|sort_order)\s*:\s*(.*)$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
AWK = r"""FNR==1{fm=0; print FILENAME "\tfile"} /^---[[:space:]]*$/{fm++; next} fm==1 && /^(permalink|sort_order):/{print FILENAME "\t" $0}"""


def run_remote(script, data=None):
    return subprocess.run(SSH + ["sh -c " + shlex.quote(script)], input=data,
                          capture_output=True, env=ENV)


def norm(permalink):
    return permalink.strip().strip("/").lower()


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def split_name(name):
    m = DATE_RE.match(name)
    if m:
        return m.group(1), m.group(2).lower()
    stem = name[:-3] if name.endswith(".md") else name
    return "", stem.lower()


def local_fields(text):
    lines = text.split("\n")
    out = {}
    if not lines or lines[0].strip() != "---":
        return out
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = FIELD_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


class Inventory:
    def __init__(self):
        self.names = set()
        self.slugs = {}
        self.permas = {}
        self.sorts = {}

    def add(self, name, permalink, sort_order):
        date, slug = split_name(name)
        self.names.add(name)
        self.slugs.setdefault(slug, name)
        p = norm(permalink or "")
        if p:
            self.permas.setdefault(p, name)
        n = to_int(sort_order)
        if date and n is not None:
            self.sorts.setdefault((date, n), name)

    def next_sort(self, date):
        used = [n for (d, n) in self.sorts if d == date]
        return max(used) + 1 if used else 1


def prime_inventory(path):
    script = ("cd " + shlex.quote(path) + " || exit 3; set -- *.md; "
              "[ -e \"$1\" ] || exit 0; awk " + shlex.quote(AWK) + " \"$@\"")
    r = run_remote(script)
    if r.returncode != 0:
        return None, r.stderr.decode(errors="replace").strip() or "rc=" + str(r.returncode)
    names, fields = [], {}
    for line in r.stdout.decode(errors="replace").splitlines():
        name, _, rest = line.partition("\t")
        if rest == "file":
            names.append(name)
            continue
        m = FIELD_RE.match(rest)
        if m:
            fields.setdefault(name, {})[m.group(1)] = m.group(2).strip().strip("'\"")
    inv = Inventory()
    for name in names:
        f = fields.get(name, {})
        inv.add(name, f.get("permalink"), f.get("sort_order"))
    return inv, ""


def order_key(path):
    date, _ = split_name(path.name)
    n = to_int(local_fields(path.read_text(encoding="utf-8", errors="replace")).get("sort_order"))
    return (date, n if n is not None else 0, path.name)


def set_sort_order(data, n):
    lines = data.decode("utf-8", errors="surrogateescape").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                break
            if re.match(r"sort_order\s*:", lines[i]):
                lines[i] = "sort_order: " + str(n)
                break
    return "\n".join(lines).encode("utf-8", errors="surrogateescape")


def copy_remote(dest_dir, name, data):
    final = dest_dir + "/" + name
    script = ("d=" + shlex.quote(dest_dir) + "; t=$(mktemp -p \"$d\" .ferry.XXXXXX) || exit 1; "
              "cat > \"$t\" && chmod 644 \"$t\" && ln \"$t\" " + shlex.quote(final) +
              "; rc=$?; rm -f \"$t\"; exit $rc")
    r = run_remote(script, data)
    return r.returncode == 0, r.stderr.decode(errors="replace").strip()


def main():
    ap = argparse.ArgumentParser(description="Carry the Mac's shadow posts to Prime, overwriting nothing.")
    ap.add_argument("aliases", nargs="*", help="blog aliases (default: article grim bot)")
    ap.add_argument("--yes", action="store_true", help="copy; without it only print the plan")
    args = ap.parse_args()
    aliases = args.aliases or list(DEFAULT_ALIASES)

    if not SHADOW_CFG.is_file():
        sys.exit("ferry: STOP -- no shadow config at " + str(SHADOW_CFG) + "; this word is for the Mac.")
    shadow = {}
    for v in json.loads(SHADOW_CFG.read_text(encoding="utf-8")).values():
        if isinstance(v, dict) and v.get("alias") and v.get("path"):
            shadow[v["alias"]] = Path(v["path"]).expanduser()

    r = run_remote("uname -n; cat ~/.config/pipulate/blogs.json")
    if r.returncode != 0:
        sys.exit("ferry: STOP -- could not read blogs.json on " + HOST + ": " +
                 r.stderr.decode(errors="replace").strip())
    there, _, cfg = r.stdout.decode(errors="replace").partition("\n")
    if there.strip() == os.uname().nodename:
        sys.exit("ferry: STOP -- " + HOST + " is this machine; run ferry on the Mac.")
    try:
        prime = {v["alias"]: v["path"] for v in json.loads(cfg).values()
                 if isinstance(v, dict) and v.get("alias") and v.get("path")}
    except ValueError:
        sys.exit("ferry: STOP -- the blogs.json from " + HOST + " did not parse.")

    counts = {"copy": 0, "skipped": 0, "refused": 0, "failed": 0, "absent": 0}
    landed = []
    print("ferry: " + SHADOW_CFG.name + " -> " + HOST + (" (armed)" if args.yes else " (dry run; --yes copies)"))

    def say(verdict, name, why=""):
        print("    " + verdict.ljust(11) + name + ((" -- " + why) if why else ""))

    for alias in aliases:
        src, dest = shadow.get(alias), prime.get(alias)
        if src is None or dest is None:
            counts["absent"] += 1
            where = "the shadow config" if src is None else "blogs.json on " + HOST
            print("  " + alias + ": ABSENT, not in " + where)
            continue
        inv, err = prime_inventory(dest)
        if inv is None:
            counts["failed"] += 1
            print("  " + alias + ": FAILED, could not list " + dest + " on " + HOST + ": " + err)
            continue
        files = sorted(src.glob("*.md"), key=order_key) if src.is_dir() else []
        print("  " + alias + ": " + str(len(files)) + " shadow post(s), " + str(len(inv.names)) +
              " on Prime (" + dest + ")")
        for f in files:
            name = f.name
            if name in inv.names:
                counts["skipped"] += 1
                say("SKIPPED", name, "same filename already on Prime")
                continue
            data = f.read_bytes()
            fl = local_fields(data.decode("utf-8", errors="replace"))
            date, slug = split_name(name)
            why = []
            if slug in inv.slugs:
                why.append("slug already on Prime as " + inv.slugs[slug])
            p = norm(fl.get("permalink", ""))
            if p and p in inv.permas:
                why.append("permalink " + fl["permalink"] + " already on Prime as " + inv.permas[p])
            n = to_int(fl.get("sort_order"))
            note = ""
            if date and n is not None and (date, n) in inv.sorts:
                new_n = inv.next_sort(date)
                note = "sort_order " + str(n) + " -> " + str(new_n) + " (" + str(n) + " taken by " + inv.sorts[(date, n)] + ")"
                data = set_sort_order(data, new_n)
                fl["sort_order"] = str(new_n)
            if why:
                counts["refused"] += 1
                say("REFUSED", name, "; ".join(why))
                continue
            if args.yes:
                ok, msg = copy_remote(dest, name, data)
                if not ok:
                    counts["failed"] += 1
                    say("FAILED", name, msg or "copy returned nonzero")
                    continue
                say("COPIED", name, note)
                if dest not in landed:
                    landed.append(dest)
            else:
                say("WOULD COPY", name, note)
            counts["copy"] += 1
            inv.add(name, fl.get("permalink"), fl.get("sort_order"))

    label = "DONE" if args.yes else "DRY RUN"
    print("ferry: " + label + " -- " + ", ".join(str(v) + " " + k for k, v in counts.items() if v))
    for dest in landed:
        print("ferry: on Prime, the new posts are untracked: git -C " + os.path.dirname(dest) + " status --short")
    if counts["refused"] or counts["failed"] or counts["absent"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
