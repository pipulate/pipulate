#!/usr/bin/env python3
"""
walk_compile.py -- compile a .walk.md authoring surface into a trail.

Stdlib only. Single file. Never imports walk.py, and deliberately RE-DERIVES
the field sets and regexes it needs. Same WET bargain bookmark_import.py and
walk_cartridge.py already strike, for the same stated reason: a tool that must
be fetchable alone cannot import its way to correctness. The cost is named
rather than hidden -- if walk.py's field sets, NAME_RE or ENV_RE ever change,
this file is wrong until it changes too, and nothing here will notice.

WHAT IT READS: <stem>.walk.md, the surface bookmark_import.py emits and a
human then fills in.

    ---                     the frontmatter fence, on line 1
    key: value              SCALAR SUBSET: one key and one value per line
    ---
                            preamble prose, DISCARDED
    ## stop_name            the heading IS the stop name
    key: value              the stop's scalar head
                            the FIRST BLANK LINE ends the head
    guidance paragraph      read ALOUD; runs to the next heading

THE SCALAR SUBSET IS NOT YAML AND DOES NOT PRETEND TO BE. A value is the raw
text after the FIRST colon, stripped. No anchors, no aliases, no block
scalars, no flow sequences -- each refused by leading character, by name, with
a line number. Flow MAPPINGS are deliberately NOT refused by sigil, because
the one placeholder the trail schema requires begins with an opening brace and
a grammar that refuses its own mandatory token is not a grammar. Nothing here
is ever handed to a YAML parser, so a brace-wrapped value is simply a literal
string, and it dies downstream at a named field check rather than being
silently coerced into a nested map.

WHAT IT WRITES: <stem>.yaml BESIDE the surface -- the JSON subset of YAML 1.2
that walk.py accepts UNMODIFIED. The output path is a pure function of the
input path, so a collision is unrepresentable and re-compiling is idempotent.
CONTENT-ADDRESSED artifacts live under data/ (data/walks/<sha256>/walk.zip,
where the path IS the identity). NAME-ADDRESSED artifacts live beside their
source. A trail is name-addressed; a sealed cartridge is not.

IT REFUSES RATHER THAN DEFAULTS. Every TODO left in the surface is a refusal
naming the stop it belongs to, so a half-filled surface cannot become a trail
-- and therefore cannot be spoken, because mother_cat._ride_async calls
walk.load_trail BEFORE it narrates anything, and a trail that was never
written is a trail that never loads.

TWO CHANNELS, TWO AUDIENCES. stdout carries exactly one outcome line: a token
plus counts, never a label, never a path, never a stop name. stderr carries
everything a human needs, including everything identifying. Redirecting stderr
away is compile-lane-safe BY CONSTRUCTION.

GRADE THE TOKEN, NOT THE EXIT CODE. Exit 2 already means at least four things
on this machine, so the outcome line exists to be read instead.

THE FIRST-ERROR FLOOR APPLIES TO THIS TOOL'S OWN REFUSALS. A structural
refusal reports the FIRST line the parser could not get past and says nothing
about the lines after it; the refusal says so out loud. CONTENT refusals
(TODO, empty guidance) are enumerated in full, because those can be collected
without guessing.

USAGE
  python scripts/walk_compile.py PATH/TO/name.walk.md

Exit codes: 0 wrote the trail | 2 refused, nothing written.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1
TODO = "TODO"
SCHEME_SEP = "://"
SUFFIX = ".walk.md"

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

HEAD_STRINGS = ("name", "description", "profile_name")
HEAD_BOOLS = ("headless", "persistent", "override_cache",
              "take_screenshot", "is_notebook_context", "verbose")
HEAD_FIELDS = frozenset(
    HEAD_STRINGS + HEAD_BOOLS + ("schema_version", "delay_range"))

STOP_HEAD_FIELDS = frozenset((
    "label", "url_env", "target_slot", "harvest_regex",
    "connector_script", "connector_argv",
))


class CompileError(Exception):
    """One structural refusal, carrying enough text to name where it was."""


def _die(lineno, message, line=None):
    text = "line " + str(lineno) + ": " + message
    if line is not None:
        text += "  |  " + line.rstrip()
    raise CompileError(text)


def _die_head(message):
    raise CompileError("frontmatter: " + message)


def _parse_head(lines, start, end):
    """Return (mapping, index_of_terminator). One scalar per line, nothing else.

    The head ends at the FIRST BLANK LINE and that rule is the entire grammar.
    A stop with no blank line before the next heading therefore runs its head
    straight into that heading, and the heading refuses here -- a heading has
    no colon, and if a stop name ever carried one its key would not match
    KEY_RE. Either way the refusal names the HEADING'S line number, which is
    exactly where the missing blank line belongs. Stopping at the heading
    instead would hand the stop an empty guidance body and point the refusal
    somewhere useless.
    """
    head = {}
    i = start
    while i < end and lines[i].strip():
        line = lines[i]
        n = i + 1
        if line[:1] in (" ", "\t"):
            _die(n, "indented; the scalar head has no nesting", line)
        if line.lstrip().startswith("- "):
            _die(n, "a list item; the scalar head has no lists", line)
        if ":" not in line:
            _die(n, "no colon; the head is one 'key: value' per line", line)
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not KEY_RE.match(key):
            _die(n, "key " + repr(key) + " is not lowercase_underscore", line)
        if not value:
            _die(n, "key " + repr(key) + " has an empty value", line)
        if value[0] in "&*|>[":
            _die(n, "value opens with " + repr(value[0]) + "; no anchors, aliases, block scalars or flow sequences", line)
        if key in head:
            _die(n, "duplicate key " + repr(key), line)
        head[key] = value
        i += 1
    return head, i


def _as_bool(key, raw):
    """Exactly 'true' or 'false'. One spelling, on purpose.

    YAML 1.1 also accepts yes, on, y and their capitalizations, and a value
    with two spellings is a value the sealed bytes and the consent surface can
    disagree about.
    """
    if raw == "true":
        return True
    if raw == "false":
        return False
    _die_head("key " + repr(key) + " must be exactly 'true' or 'false', got "
              + repr(raw))


def _as_delay_range(raw):
    """'none', or two numbers separated by whitespace."""
    if raw == "none":
        return None
    parts = raw.split()
    if len(parts) != 2:
        _die_head("delay_range must be 'none' or two numbers separated by a "
                  "space, got " + repr(raw))
    try:
        low = float(parts[0])
        high = float(parts[1])
    except ValueError:
        _die_head("delay_range has a non-numeric bound: " + repr(raw))
    if low > high:
        _die_head("delay_range has minimum above maximum: " + repr(raw))
    return [low, high]


def _split(lines):
    """Return (frontmatter_head, [(name, heading_lineno, head, guidance), ...])."""
    if not lines or lines[0].strip() != "---":
        _die(1, "the surface must open with a '---' frontmatter fence")
    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        _die(1, "the frontmatter fence is never closed")
    head, head_end = _parse_head(lines, 1, close)
    if head_end != close:
        _die(head_end + 1, "blank line inside frontmatter; the head must run "
                           "unbroken from the opening fence to the closing one")
    stops = []
    i = close + 1
    while i < len(lines):
        if not lines[i].startswith("## "):
            i += 1
            continue
        name = lines[i][3:].strip()
        heading_lineno = i + 1
        stop_head, after = _parse_head(lines, i + 1, len(lines))
        j = after
        while j < len(lines) and not lines[j].strip():
            j += 1
        body = []
        while j < len(lines) and not lines[j].startswith("## "):
            body.append(lines[j])
            j += 1
        guidance = " ".join(" ".join(body).split())
        stops.append((name, heading_lineno, stop_head, guidance))
        i = j
    return head, stops


def _build(head, stops):
    """Return (trail, refusals).

    Structural problems RAISE, because a parser cannot honestly continue past
    one. Content problems (TODO, empty guidance) COLLECT, because those can be
    enumerated in full without guessing.
    """
    refusals = []

    missing = sorted(HEAD_FIELDS - set(head))
    unknown = sorted(set(head) - HEAD_FIELDS)
    if missing:
        _die_head("missing key(s): " + ", ".join(missing))
    if unknown:
        _die_head("unknown key(s): " + ", ".join(unknown))
    if head["schema_version"] != str(SCHEMA_VERSION):
        _die_head("schema_version must be " + str(SCHEMA_VERSION) + ", got "
                  + repr(head["schema_version"]))
    if not NAME_RE.match(head["name"]):
        _die_head("name " + repr(head["name"]) + " is not lowercase_underscore")
    if TODO in head["description"]:
        refusals.append("frontmatter: description still says " + TODO)

    defaults = {
        "take_screenshot": _as_bool("take_screenshot", head["take_screenshot"]),
        "headless": _as_bool("headless", head["headless"]),
        "is_notebook_context": _as_bool("is_notebook_context",
                                        head["is_notebook_context"]),
        "persistent": _as_bool("persistent", head["persistent"]),
        "profile_name": head["profile_name"],
        "verbose": _as_bool("verbose", head["verbose"]),
        "override_cache": _as_bool("override_cache", head["override_cache"]),
        "delay_range": _as_delay_range(head["delay_range"]),
    }

    if not stops:
        _die(1, "the surface declares no stops; a walk needs at least one")

    built = []
    seen_name = set()
    seen_slot = set()
    for name, lineno, stop_head, guidance in stops:
        where = "stop " + repr(name)
        if not NAME_RE.match(name or ""):
            _die(lineno, "stop name " + repr(name) + " is not lowercase_underscore")
        if name in seen_name:
            _die(lineno, "duplicate stop name " + repr(name))
        seen_name.add(name)
        missing = sorted(STOP_HEAD_FIELDS - set(stop_head))
        unknown = sorted(set(stop_head) - STOP_HEAD_FIELDS)
        if missing:
            _die(lineno, where + " is missing: " + ", ".join(missing))
        if unknown:
            _die(lineno, where + " has unknown key(s): " + ", ".join(unknown))
        if not ENV_RE.match(stop_head["url_env"]):
            _die(lineno, where + " url_env " + repr(stop_head["url_env"])
                 + " is not an environment variable name")
        slot = stop_head["target_slot"]
        if not NAME_RE.match(slot):
            _die(lineno, where + " target_slot " + repr(slot)
                 + " is not lowercase_underscore")
        if slot in seen_slot:
            _die(lineno, where + " reuses target_slot " + repr(slot))
        seen_slot.add(slot)
        try:
            re.compile(stop_head["harvest_regex"])
        except re.error as exc:
            _die(lineno, where + " harvest_regex is invalid: " + str(exc))
        try:
            argv = shlex.split(stop_head["connector_argv"])
        except ValueError as exc:
            _die(lineno, where + " connector_argv will not split: " + str(exc))

        script = stop_head["connector_script"]
        if TODO in script:
            refusals.append(where + ": connector_script still says " + TODO)
        else:
            script_path = Path(script)
            if script_path.is_absolute():
                _die(lineno, where + " connector_script must be relative to "
                     "the repository root")
            if not (REPO_ROOT / script_path).is_file():
                _die(lineno, where + " connector_script does not exist: " + script)

        if TODO in stop_head["connector_argv"]:
            refusals.append(where + ": connector_argv still says " + TODO)
        else:
            if argv.count("{harvested}") != 1:
                _die(lineno, where + " connector_argv must contain the "
                     "harvested placeholder exactly once")
            for token in argv:
                if ("{" in token or "}" in token) and token != "{harvested}":
                    _die(lineno, where + " connector_argv has an unknown "
                         "placeholder: " + repr(token))

        if not guidance:
            refusals.append(where + ": has no guidance body")
        elif TODO in guidance:
            refusals.append(where + ": guidance still says " + TODO)

        built.append({
            "name": name,
            "label": stop_head["label"],
            "guidance": guidance,
            "url_env": stop_head["url_env"],
            "target_slot": slot,
            "harvest_regex": stop_head["harvest_regex"],
            "connector": {
                "script": script,
                "argv": argv,
                "read_only": True,
            },
        })

    trail = {
        "schema_version": SCHEMA_VERSION,
        "name": head["name"],
        "description": head["description"],
        "defaults": defaults,
        "stops": built,
    }
    return trail, refusals


def _emit(trail):
    return json.dumps(trail, indent=2, ensure_ascii=False) + "\n"


def _ignored_or_outside(path):
    """Return None when writing here is safe, else a refusal string.

    Duplicated from bookmark_import.py on purpose; see this module's docstring
    for the WET bargain and its stated cost. Two questions, because the
    architecture demands both: is this path ignored by THIS repo, and if git
    says it is outside this repo, is it ignored by whatever repo it does live
    in? A path in no repo at all is safe -- there is no index to leak into.
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compile a .walk.md authoring surface into a trail."
    )
    parser.add_argument("surface", help="path to a <name>.walk.md file")
    args = parser.parse_args(argv)

    surface = Path(args.surface).expanduser()
    if not surface.is_file():
        print("COMPILE REFUSED reason=no_such_file")
        print("no such file: " + str(surface), file=sys.stderr)
        return 2
    if not surface.name.endswith(SUFFIX):
        print("COMPILE REFUSED reason=bad_suffix")
        print("expected a file named <name>" + SUFFIX + ", got " + surface.name,
              file=sys.stderr)
        return 2

    stem = surface.name[:-len(SUFFIX)]
    try:
        text = surface.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print("COMPILE REFUSED reason=unreadable")
        print("could not read " + str(surface) + ": " + str(exc), file=sys.stderr)
        return 2

    try:
        head, stops = _split(text.split("\n"))
        trail, refusals = _build(head, stops)
    except CompileError as exc:
        print("COMPILE REFUSED reason=structure")
        print(str(exc), file=sys.stderr)
        print("", file=sys.stderr)
        print("THE FIRST-ERROR FLOOR: that is the FIRST line the parser could",
              file=sys.stderr)
        print("not get past, never the last defect in the file. Fix it and",
              file=sys.stderr)
        print("re-run rather than assuming it was the only one.", file=sys.stderr)
        return 2

    if trail["name"] != stem:
        print("COMPILE REFUSED reason=name_mismatch")
        print("frontmatter name " + repr(trail["name"]) + " does not match the "
              "file stem " + repr(stem) + ".", file=sys.stderr)
        print("One identity all the way through: <stem>" + SUFFIX
              + " compiles to <stem>.yaml and the trail inside is named "
              "<stem>.", file=sys.stderr)
        return 2

    if refusals:
        print("COMPILE REFUSED reason=todo count=" + str(len(refusals)))
        for line in refusals:
            print("  " + line, file=sys.stderr)
        print("", file=sys.stderr)
        print("Every one of these is a REFUSAL, not a default. Fill them in and",
              file=sys.stderr)
        print("re-run. Nothing was written.", file=sys.stderr)
        return 2

    serialized = _emit(trail)
    leaks = [n for n, line in enumerate(serialized.split("\n"), start=1)
             if SCHEME_SEP in line]
    if leaks:
        print("COMPILE REFUSED reason=scheme_separator count=" + str(len(leaks)))
        print("the compiled trail carries an address on line(s) "
              + ", ".join(str(n) for n in leaks) + ".", file=sys.stderr)
        print("A trail NAMES the variables it demands and never HOLDS their",
              file=sys.stderr)
        print("values; that is what makes it safe to seal and hand to somebody.",
              file=sys.stderr)
        print("Move the address into the exports file. Nothing was written.",
              file=sys.stderr)
        return 2

    out_path = surface.parent / (stem + ".yaml")
    problem = _ignored_or_outside(out_path)
    if problem:
        print("COMPILE REFUSED reason=not_ignored")
        print(problem, file=sys.stderr)
        print("", file=sys.stderr)
        print("A trail carries client labels and client guidance. Move the",
              file=sys.stderr)
        print("surface to an ignored path and compile it there.", file=sys.stderr)
        return 2

    out_path.write_text(serialized, encoding="utf-8")
    out_path.chmod(0o600)
    print("COMPILE OK stops=" + str(len(trail["stops"])))
    print("trail  " + str(out_path) + "  (mode 0600)", file=sys.stderr)
    print("", file=sys.stderr)
    print("Next: dry-run it, then seal it.", file=sys.stderr)
    print("  .venv/bin/python scripts/walk.py --trail " + str(out_path),
          file=sys.stderr)
    print("  .venv/bin/python scripts/walk_cartridge.py seal " + str(out_path),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
