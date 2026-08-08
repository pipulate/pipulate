#!/usr/bin/env python3
"""
bookmark_import.py -- one folder of bookmarks becomes a walk AUTHORING SURFACE.

Stdlib only. Single file. Never imports walk.py, and deliberately RE-DERIVES
the two regexes it needs. The cost is named rather than hidden: if walk.py's
NAME_RE or ENV_RE ever change, this file is wrong until it changes too, and
nothing here will notice. That is the same WET bargain walk_cartridge.py
strikes with foo_cartridge.py, for the same reason -- a tool that must be
fetchable alone cannot import its way to correctness.

EMITS TWO ARTIFACTS, AND NEITHER IS A TRAIL:

  <name>.walk.md      the AUTHORING SURFACE. A fenced frontmatter head for the
                      trail-wide scalars, then one level-two heading per stop:
                      the heading IS the stop name, the lines directly under
                      it up to the first blank line are the SCALAR SUBSET
                      head, and everything after that blank line is the
                      guidance -- the paragraph Piper reads ALOUD. ZERO
                      literal URLs.

  <name>.exports.sh   one export line per stop. Every URL in the import lives
                      HERE and nowhere else. Source it before riding.

WHY TWO FILES: the surface is meant to be read, edited, sealed, and handed to
somebody. The exports carry client URLs and must never leave the machine. One
artifact cannot hold both properties, so there are two.

TWO CHANNELS, AND THE SPLIT IS A SAFETY PROPERTY. stdout carries exactly one
outcome line per run -- a token plus counts, never a label, never a folder
name, never a path. stderr carries everything a human needs, including
everything identifying. So redirecting stderr away is compile-lane-safe BY
CONSTRUCTION, and a probe never has to choose between reading the outcome and
leaking a client.

GRADE THE TOKEN, NOT THE EXIT CODE. Exit 2 already means at least four things
on this machine: argparse rejecting an argument, walk.py reporting a plan that
is not ready, CPython failing to open a script at all, and any refusal a
script spells 2. The outcome line exists so nothing must disambiguate a number
four worlds share.

THE WRITE TARGET IS ASKED, NOT ASSUMED. Before a single byte is written this
asks git check-ignore whether the target sits in git's negative space, and
REFUSES when it does not. A hardcoded safe-directory list is a convention; a
question put to git is a mechanism, and it survives a rename, a move, a
whitelabel, and the case where the URLs live in somebody else's repo entirely.

INPUT: a Netscape bookmark export (every browser makes one) or a Chromium
Bookmarks JSON file. Detected by first byte, never by extension. The HTML form
is RICHER: it carries a description slot that Chrome's JSON does not have at
all. Receipt, 2026-08-08: a census of a live 95,398-byte Bookmarks file
holding 250 url nodes returned 18 lowercase key names, none description-shaped.

USAGE
  python scripts/bookmark_import.py FILE                      # list folders
  python scripts/bookmark_import.py FILE --folder NAME
  python scripts/bookmark_import.py FILE --folder NAME --name my_walk --out DIR

NEVER echo the bare folder-listing invocation as a compile-lane probe. The
listing is folder names, and folder names are client data. It goes to stderr
for exactly that reason, but a probe that merges the streams defeats the split.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Re-derived from walk.py. See the module docstring for why this is a copy.
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Default landing zone. Receipt 2026-08-08: .gitignore carries
# Notebooks/Client_Work/ and data/ wholesale, so both are negative space. This
# one is chosen because a human has to OPEN the surface and edit it, and a
# human-authored document belongs beside the other human-authored ones rather
# than in the machine-state directory next to databases and browser profiles.
DEFAULT_OUT = REPO_ROOT / "Notebooks" / "Client_Work"

TODO = "TODO"
TODO_GUIDANCE = (
    "TODO: write what the rider must DO at this stop, in the voice the "
    "narrator will read aloud. The compiler refuses this line, so the walk "
    "cannot be sealed until it is replaced."
)


class _NetscapeParser(HTMLParser):
    """Netscape Bookmark File Format, 1996.

    It is not valid HTML and never was: DT and DD are never closed. So a
    pending description is flushed on the next structural tag rather than on
    an end tag that never arrives.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.folders = []
        self.nodes = []
        self._pending_folder = None
        self._mode = None
        self._buf = []
        self._href = ""

    def flush_pending_description(self):
        if self._mode != "dd":
            return
        if self.nodes:
            text = " ".join("".join(self._buf).split())
            if text:
                self.nodes[-1]["description"] = text
        self._mode = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        name = tag.lower()
        if name in ("dt", "dl", "h3", "a", "dd"):
            self.flush_pending_description()
        if name == "dl":
            self.folders.append(self._pending_folder or "")
            self._pending_folder = None
        elif name == "h3":
            self._mode = "h3"
            self._buf = []
        elif name == "a":
            self._mode = "a"
            self._buf = []
            self._href = dict(attrs).get("href") or ""
        elif name == "dd":
            self._mode = "dd"
            self._buf = []

    def handle_endtag(self, tag):
        name = tag.lower()
        if name == "h3" and self._mode == "h3":
            self._pending_folder = "".join(self._buf).strip()
            self._mode = None
            self._buf = []
        elif name == "a" and self._mode == "a":
            self.nodes.append({
                "folder": tuple(f for f in self.folders if f),
                "label": " ".join("".join(self._buf).split()),
                "url": self._href,
                "description": "",
            })
            self._mode = None
            self._buf = []
        elif name == "dl":
            self.flush_pending_description()
            if self.folders:
                self.folders.pop()

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data)


def _from_chrome_json(data):
    nodes = []

    def descend(container, path):
        for child in container.get("children") or []:
            if not isinstance(child, dict):
                continue
            if child.get("type") == "url":
                nodes.append({
                    "folder": tuple(path),
                    "label": " ".join((child.get("name") or "").split()),
                    "url": child.get("url") or "",
                    "description": "",
                })
            elif child.get("type") == "folder":
                descend(child, path + [child.get("name") or ""])

    for key, root in sorted((data.get("roots") or {}).items()):
        if isinstance(root, dict) and "children" in root:
            descend(root, [root.get("name") or key])
    return nodes


def _parse(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    if raw.lstrip()[:1] == "{":
        return _from_chrome_json(json.loads(raw))
    parser = _NetscapeParser()
    parser.feed(raw)
    parser.close()
    parser.flush_pending_description()
    return parser.nodes


def _slug(text):
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if value and not value[0].isalpha():
        value = "s_" + value
    return value


def _stamp():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return now.replace("+00:00", "Z")


def _ignored_or_outside(path):
    """Return None when writing here is safe, else a refusal string.

    Two questions, because the architecture demands both: is this path ignored
    by THIS repo, and if git says it is outside this repo, is it ignored by
    whatever repo it does live in? A path in no repo at all is safe -- there
    is no index for it to leak into.
    """
    for cwd in (REPO_ROOT, path.parent):
        try:
            proc = subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return str(path) + ": could not ask git about it (" + str(exc) + ")"
        if proc.returncode == 0:
            return None
        if proc.returncode == 1:
            return str(path) + ": inside a git worktree and NOT ignored"
    return None


def _render_surface(name, stops, skipped, source_name, folder):
    out = []
    out.append("---")
    out.append("name: " + name)
    out.append("description: " + TODO)
    out.append("schema_version: 1")
    out.append("headless: false")
    out.append("persistent: true")
    out.append("override_cache: true")
    out.append("profile_name: default")
    out.append("take_screenshot: false")
    out.append("is_notebook_context: false")
    out.append("verbose: true")
    out.append("delay_range: none")
    out.append("---")
    out.append("")
    out.append("# " + name)
    out.append("")
    out.append("Imported " + _stamp() + " from " + source_name + ", folder "
               + repr(folder) + ".")
    out.append("")
    out.append("HOW TO READ THIS FILE. Each level-two heading IS a stop name.")
    out.append("The lines directly under it, up to the first blank line, are")
    out.append("the scalar head: one key and value per line, split on the")
    out.append("FIRST colon, no nesting, no lists. Everything after that blank")
    out.append("line is the guidance -- the paragraph read ALOUD at that stop.")
    out.append("")
    out.append("EVERY " + TODO + " IS A REFUSAL, not a default. The compiler")
    out.append("stops on each one and names it, so a half-filled surface")
    out.append("cannot become a walk and cannot be read aloud.")
    out.append("")
    out.append("The default harvest_regex accepts anything non-empty.")
    out.append("Tightening it is how a stop refuses a wrong paste, so tighten")
    out.append("it wherever you already know the shape.")
    out.append("")
    out.append("connector_argv is the one place the trail needs a list. Write")
    out.append("it as a shell-quoted line and the compiler splits it the way a")
    out.append("shell would, so a token containing a space needs quotes and")
    out.append("nothing else does.")
    out.append("")
    if skipped:
        out.append("THE IMPORTER SKIPPED " + str(len(skipped)) + " BOOKMARK(S):")
        out.append("")
        for label, reason in skipped:
            if "://" in label:
                shown = "(label omitted: it was a URL)"
            else:
                shown = repr(label)
            out.append("  - SKIPPED " + shown + " -- " + reason)
        out.append("")
    for stop in stops:
        out.append("## " + stop["name"])
        out.append("label: " + stop["label"])
        out.append("url_env: " + stop["url_env"])
        out.append("target_slot: " + stop["target_slot"])
        out.append("harvest_regex: " + stop["harvest_regex"])
        out.append("connector_script: " + TODO)
        out.append("connector_argv: " + TODO)
        out.append("")
        out.append(stop["guidance"])
        out.append("")
    return "\n".join(out) + "\n"


def _render_exports(name, stops, source_name):
    out = []
    out.append("#!/bin/sh")
    out.append("# " + name + " -- the URLs for the walk of the same name.")
    out.append("# Imported " + _stamp() + " from " + source_name + ".")
    out.append("#")
    out.append("# THIS FILE IS THE ONLY PLACE THESE URLS LIVE. The surface")
    out.append("# beside it NAMES them and does not HOLD them, which is")
    out.append("# exactly what makes the surface safe to seal and hand to")
    out.append("# somebody. Keep this one here.")
    out.append("#")
    out.append("#   source " + name + ".exports.sh")
    out.append("")
    for stop in stops:
        out.append("# " + stop["label"])
        quoted = stop["url"].replace("'", "'\\''")
        out.append("export " + stop["url_env"] + "='" + quoted + "'")
    out.append("")
    return "\n".join(out)


def _derive(selected):
    """Return (stops, skipped, refusals). Never writes, never prints."""
    stops = []
    skipped = []
    refusals = []
    seen_slug = {}
    seen_env = {}
    for node in selected:
        label = node["label"]
        url = node["url"].strip()
        scheme = url.split(":", 1)[0].lower() if ":" in url else ""
        if scheme not in ("http", "https"):
            skipped.append((label or "(unnamed)",
                            "scheme " + repr(scheme) + " is not a web scheme"))
            continue
        if "://" in label or label == url:
            skipped.append((label,
                            "the label IS the address, which would leak it "
                            "into the sealed trail; title this bookmark and "
                            "re-import"))
            continue
        slug = _slug(label)
        if not NAME_RE.match(slug or ""):
            skipped.append((label, "label yields no usable stop name"))
            continue
        env = "PIPULATE_TRAIL_" + slug.upper() + "_URL"
        if not ENV_RE.match(env):
            skipped.append((label,
                            "derived variable " + env + " is not a legal name"))
            continue
        if slug in seen_slug:
            refusals.append(repr(label) + " and " + repr(seen_slug[slug])
                            + " both derive the stop name " + repr(slug))
            continue
        if env in seen_env:
            refusals.append(repr(label) + " and " + repr(seen_env[env])
                            + " both derive " + env)
            continue
        seen_slug[slug] = label
        seen_env[env] = label
        stops.append({
            "name": slug,
            "label": label,
            "url": url,
            "url_env": env,
            "target_slot": slug,
            "harvest_regex": ".+",
            "guidance": node["description"] or TODO_GUIDANCE,
        })
    return stops, skipped, refusals


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turn one folder of bookmarks into a walk authoring surface."
    )
    parser.add_argument("source", help="a bookmark export, or a Chrome Bookmarks JSON file")
    parser.add_argument("--folder", default=None, help="folder to import; omit to list folders")
    parser.add_argument("--name", default=None, help="walk name (default: slug of the folder)")
    parser.add_argument("--out", default=None, help="output directory")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser()
    if not source.is_file():
        print("IMPORT REFUSED reason=no_such_file")
        print("no such file: " + str(source), file=sys.stderr)
        return 2

    try:
        nodes = _parse(source)
    except (ValueError, UnicodeDecodeError) as exc:
        print("IMPORT REFUSED reason=unparseable")
        print("could not parse " + str(source) + ": " + str(exc), file=sys.stderr)
        return 2

    if args.folder is None:
        counts = {}
        for node in nodes:
            key = " / ".join(node["folder"]) or "(root)"
            counts[key] = counts.get(key, 0) + 1
        print("IMPORT FOLDERS count=" + str(len(counts)))
        print("", file=sys.stderr)
        print("Pick one with --folder. A walk is three to seven stops, and you",
              file=sys.stderr)
        print("supply the guidance for each by hand, so import a folder you can",
              file=sys.stderr)
        print("actually narrate.", file=sys.stderr)
        print("", file=sys.stderr)
        for key in sorted(counts):
            print("  " + str(counts[key]).rjust(4) + "  " + key, file=sys.stderr)
        return 2

    want = args.folder.strip().lower()
    selected = []
    for node in nodes:
        if node["folder"] and node["folder"][-1].strip().lower() == want:
            selected.append(node)
    if not selected:
        print("IMPORT REFUSED reason=no_such_folder")
        print("no folder named " + repr(args.folder) + " in " + source.name,
              file=sys.stderr)
        return 2

    name = args.name or _slug(args.folder)
    if not NAME_RE.match(name or ""):
        print("IMPORT REFUSED reason=bad_name")
        print("walk name " + repr(name) + " does not match " + NAME_RE.pattern,
              file=sys.stderr)
        return 2

    stops, skipped, refusals = _derive(selected)

    if refusals:
        print("IMPORT REFUSED reason=collision count=" + str(len(refusals)))
        print("collisions, nothing written:", file=sys.stderr)
        for line in refusals:
            print("  " + line, file=sys.stderr)
        print("", file=sys.stderr)
        print("  Rename the bookmark in your browser and re-import. The",
              file=sys.stderr)
        print("  ambiguity lives there, and fixing it there fixes your",
              file=sys.stderr)
        print("  bookmarks too.", file=sys.stderr)
        return 2

    if not stops:
        print("IMPORT REFUSED reason=all_skipped count=" + str(len(skipped)))
        print("every bookmark in that folder was skipped:", file=sys.stderr)
        for label, reason in skipped:
            if "://" in label:
                shown = "(label omitted: it was a URL)"
            else:
                shown = repr(label)
            print("  " + shown + " -- " + reason, file=sys.stderr)
        return 2

    if args.out:
        out_dir = Path(args.out).expanduser()
    else:
        out_dir = DEFAULT_OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    surface_path = out_dir / (name + ".walk.md")
    exports_path = out_dir / (name + ".exports.sh")

    bad = []
    for candidate in (surface_path, exports_path):
        problem = _ignored_or_outside(candidate)
        if problem:
            bad.append(problem)
    if bad:
        print("IMPORT REFUSED reason=not_ignored")
        print("the write target is not in git's negative space:", file=sys.stderr)
        for line in bad:
            print("  " + line, file=sys.stderr)
        print("", file=sys.stderr)
        print("  These files carry client material. Point --out at an ignored",
              file=sys.stderr)
        print("  path.", file=sys.stderr)
        return 2

    surface_path.write_text(
        _render_surface(name, stops, skipped, source.name, args.folder),
        encoding="utf-8",
    )
    exports_path.write_text(
        _render_exports(name, stops, source.name),
        encoding="utf-8",
    )
    surface_path.chmod(0o600)
    exports_path.chmod(0o600)

    print("IMPORT OK stops=" + str(len(stops)) + " skipped=" + str(len(skipped)))
    print("surface  " + str(surface_path), file=sys.stderr)
    print("exports  " + str(exports_path), file=sys.stderr)
    print("both written mode 0600.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Next: open the surface and replace every " + TODO + ". Nothing",
          file=sys.stderr)
    print("seals until you do.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
