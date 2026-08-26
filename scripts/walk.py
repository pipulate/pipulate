#!/usr/bin/env python3
"""Mother Cat trail planner, Car A: strict dry-run and no actuation.

Trail files use the JSON subset of YAML 1.2. That keeps this car stdlib-only,
duplicate-key-checkable, and still valid YAML. There is deliberately no
browser, voice, shell, or adhoc.txt mutation path in this file.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
# THE DEFAULT IS THE SOFTBALL, ON PURPOSE (2026-08-01). Before this line moved,
# the SHORTEST invocation (`mothercat`, bare) was EXPERT MODE: three
# authenticated stops, and a newcomer's first contact was a KeyError on an
# environment variable they had never heard of. Default to the walk that needs
# no credential; make expert mode cost keystrokes.
DEFAULT_TRAIL = REPO_ROOT / "assets" / "trails" / "public_walk.yaml"
# THE EXPERT TRAIL, named here rather than implied by being the default --
# discoverability used to rest entirely on this line pointing at it:
#   mothercat assets/trails/first_context.yaml   (Jira + Botify + Gmail, auth)
SCHEMA_VERSION = 1

SELENIUM_DEFAULTS = {
    "take_screenshot": False,
    "headless": True,
    "is_notebook_context": False,
    "persistent": False,
    "profile_name": "default",
    "verbose": True,
    "override_cache": False,
    "delay_range": None,
}
ROOT_FIELDS = {"schema_version", "name", "description", "defaults", "stops"}
DEFAULT_FIELDS = set(SELENIUM_DEFAULTS)
# Every stop carries all of these.
STOP_FIELDS = {
    "name", "label", "guidance", "target_slot",
    "harvest_regex", "connector",
}
# Exactly one of these, never both and never neither. They are kept OUT of
# STOP_FIELDS because _exact enforces set-difference in both directions and
# cannot express "one of two". load_trail unions the one that is present into
# STOP_FIELDS per stop, so unknown-key rejection is unchanged: a stop is still
# checked against a complete, exact field set, just one assembled per stop.
STOP_URL_FIELDS = {"url", "url_env"}
CONNECTOR_FIELDS = {"script", "argv", "read_only"}
BOOL_DEFAULTS = {
    "take_screenshot", "headless", "is_notebook_context", "persistent",
    "verbose", "override_cache",
}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class TrailError(ValueError):
    pass


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TrailError(f"duplicate trail key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise TrailError(f"non-finite JSON number is not allowed: {value}")


def _mapping(value, where):
    if not isinstance(value, dict):
        raise TrailError(f"{where} must be a mapping")
    return value


def _exact(value, fields, where):
    missing = sorted(fields - set(value))
    unknown = sorted(set(value) - fields)
    if missing:
        raise TrailError(f"{where} missing field(s): {', '.join(missing)}")
    if unknown:
        raise TrailError(f"{where} unknown field(s): {', '.join(unknown)}")


def _text(value, where):
    if not isinstance(value, str) or not value.strip():
        raise TrailError(f"{where} must be a non-empty string")
    return value.strip()


def _repo_file(raw, where):
    relative = Path(raw)
    if relative.is_absolute():
        raise TrailError(f"{where} must be relative to the repository root")
    resolved = (REPO_ROOT / relative).resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise TrailError(f"{where} escapes the repository root") from exc
    if not resolved.is_file():
        raise TrailError(f"{where} does not exist: {raw}")
    return resolved


def _validate_defaults(raw):
    defaults = _mapping(raw, "defaults")
    _exact(defaults, DEFAULT_FIELDS, "defaults")
    for key in BOOL_DEFAULTS:
        if not isinstance(defaults[key], bool):
            raise TrailError(f"defaults.{key} must be true or false")
    defaults["profile_name"] = _text(
        defaults["profile_name"],
        "defaults.profile_name",
    )
    delay = defaults["delay_range"]
    if delay is not None:
        numbers = (
            isinstance(delay, list)
            and len(delay) == 2
            and all(
                isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in delay
            )
        )
        if not numbers or delay[0] > delay[1]:
            raise TrailError(
                "defaults.delay_range must be null or [minimum, maximum] "
                "with minimum <= maximum"
            )
    return defaults


def _validate_connector(raw, where):
    connector = _mapping(raw, where)
    _exact(connector, CONNECTOR_FIELDS, where)
    script = _text(connector["script"], f"{where}.script")
    argv = connector["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(token, str) or not token for token in argv)
    ):
        raise TrailError(
            f"{where}.argv must be a non-empty list of non-empty strings"
        )
    if argv.count("{harvested}") != 1:
        raise TrailError(
            f"{where}.argv must contain {{harvested}} exactly once"
        )
    if any(
        ("{" in token or "}" in token) and token != "{harvested}"
        for token in argv
    ):
        raise TrailError(f"{where}.argv contains an unknown placeholder")
    if connector["read_only"] is not True:
        raise TrailError(f"{where}.read_only must be true in Car A")
    return {
        "script": script,
        "script_path": str(_repo_file(script, f"{where}.script")),
        "argv": list(argv),
        "read_only": True,
    }


def load_trail(path):
    try:
        trail = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except OSError as exc:
        raise TrailError(f"cannot read trail {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TrailError(
            f"invalid trail syntax in {path}: Car A accepts the JSON subset "
            f"of YAML 1.2 only ({exc})"
        ) from exc

    trail = _mapping(trail, "trail")
    _exact(trail, ROOT_FIELDS, "trail")
    version = trail["schema_version"]
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != SCHEMA_VERSION
    ):
        raise TrailError(
            f"trail.schema_version must be integer {SCHEMA_VERSION}, "
            f"got {version!r}"
        )
    name = _text(trail["name"], "trail.name")
    if not NAME_RE.fullmatch(name):
        raise TrailError("trail.name must match ^[a-z][a-z0-9_]*$")

    stops = trail["stops"]
    if not isinstance(stops, list) or not stops:
        raise TrailError("trail.stops must be a non-empty list")

    clean_stops = []
    seen_names = set()
    seen_slots = set()
    for index, raw_stop in enumerate(stops):
        where = f"stops[{index}]"
        stop = _mapping(raw_stop, where)
        present = STOP_URL_FIELDS & set(stop)
        if len(present) != 1:
            raise TrailError(
                f"{where} must carry exactly one of "
                f"{sorted(STOP_URL_FIELDS)}; found {sorted(present)}"
            )
        _exact(stop, STOP_FIELDS | present, where)
        stop_name = _text(stop["name"], f"{where}.name")
        target_slot = _text(
            stop["target_slot"],
            f"{where}.target_slot",
        )
        url_env = _text(stop["url_env"], f"{where}.url_env")
        harvest_regex = _text(
            stop["harvest_regex"],
            f"{where}.harvest_regex",
        )
        if (
            not NAME_RE.fullmatch(stop_name)
            or stop_name in seen_names
        ):
            raise TrailError(
                f"{where}.name must be unique and match "
                "^[a-z][a-z0-9_]*$"
            )
        if (
            not NAME_RE.fullmatch(target_slot)
            or target_slot in seen_slots
        ):
            raise TrailError(
                f"{where}.target_slot must be unique and match "
                "^[a-z][a-z0-9_]*$"
            )
        if not ENV_RE.fullmatch(url_env):
            raise TrailError(
                f"{where}.url_env must name an environment variable"
            )
        try:
            re.compile(harvest_regex)
        except re.error as exc:
            raise TrailError(
                f"{where}.harvest_regex is invalid: {exc}"
            ) from exc
        seen_names.add(stop_name)
        seen_slots.add(target_slot)
        clean_stops.append({
            "name": stop_name,
            "label": _text(stop["label"], f"{where}.label"),
            "guidance": _text(
                stop["guidance"],
                f"{where}.guidance",
            ),
            "url_env": url_env,
            "target_slot": target_slot,
            "harvest_regex": harvest_regex,
            "connector": _validate_connector(
                stop["connector"],
                f"{where}.connector",
            ),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "description": _text(
            trail["description"],
            "trail.description",
        ),
        "defaults": _validate_defaults(trail["defaults"]),
        "stops": clean_stops,
    }


def parse_values(raw_values):
    values = {}
    for raw in raw_values:
        slot, separator, value = raw.partition("=")
        slot = slot.strip()
        if not separator or not slot or not value:
            raise TrailError("--value must be TARGET_SLOT=VALUE")
        if slot in values:
            raise TrailError(
                f"duplicate --value for target_slot {slot!r}"
            )
        values[slot] = value
    return values


def _browser_params(url, defaults):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TrailError(f"URL must be absolute http(s): {url!r}")
    path = parsed.path
    slug = (
        "%2F"
        if not path or path == "/"
        else quote(path, safe="")[:100]
    )
    return {
        "url": url,
        "domain": parsed.netloc,
        "url_path_slug": slug,
        **defaults,
    }


def build_plan(trail, supplied_values):
    slots = {stop["target_slot"] for stop in trail["stops"]}
    unknown = sorted(set(supplied_values) - slots)
    if unknown:
        raise TrailError(
            f"--value named unknown target_slot(s): {', '.join(unknown)}"
        )
    interpreter = REPO_ROOT / ".venv" / "bin" / "python"
    if not interpreter.is_file():
        raise TrailError(
            f"canonical interpreter missing: {interpreter}"
        )

    all_errors = []
    resolved_stops = []
    for stop in trail["stops"]:
        url = os.environ.get(stop["url_env"], "").strip()
        value = supplied_values.get(stop["target_slot"])
        errors = []
        browser = None

        if not url:
            errors.append(
                f"unset environment variable {stop['url_env']}"
            )
        else:
            try:
                browser = _browser_params(
                    url,
                    trail["defaults"],
                )
            except TrailError as exc:
                errors.append(str(exc))

        valid_value = (
            value is not None
            and re.fullmatch(
                stop["harvest_regex"],
                value,
            ) is not None
        )
        if value is None:
            errors.append(
                f"missing --value {stop['target_slot']}=VALUE"
            )
        elif not valid_value:
            errors.append(
                f"value for {stop['target_slot']} failed "
                f"fullmatch({stop['harvest_regex']!r})"
            )

        argv = None
        if valid_value:
            argv = [
                str(interpreter),
                stop["connector"]["script_path"],
            ]
            argv.extend(
                value if token == "{harvested}" else token
                for token in stop["connector"]["argv"]
            )

        resolved_stops.append({
            "name": stop["name"],
            "label": stop["label"],
            "guidance": stop["guidance"],
            "url_env": stop["url_env"],
            "url": url or None,
            "target_slot": stop["target_slot"],
            "harvest_regex": stop["harvest_regex"],
            "match_mode": "fullmatch",
            "harvested_value": value,
            "browser_params": browser,
            "connector": {
                "script": stop["connector"]["script"],
                "read_only": True,
                "argv": argv,
            },
            "errors": errors,
        })
        all_errors.extend(
            f"{stop['name']}: {message}"
            for message in errors
        )

    return {
        "mode": "dry-run",
        "ready": not all_errors,
        "selenium_automation_defaults": SELENIUM_DEFAULTS,
        "trail": {
            **trail,
            "stops": resolved_stops,
        },
        "errors": all_errors,
        "actuation": {
            "browser": False,
            "voice": False,
            "adhoc_mutation": False,
            "shell_execution": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Validate and print a Mother Cat trail plan. "
            "Car A is dry-run only."
        )
    )
    parser.add_argument(
        "--trail",
        type=Path,
        default=DEFAULT_TRAIL,
    )
    parser.add_argument(
        "--value",
        action="append",
        default=[],
        metavar="TARGET_SLOT=VALUE",
        help=(
            "Supply one harvested value for fullmatch validation; "
            "repeat per stop."
        ),
    )
    args = parser.parse_args()

    try:
        path = (
            args.trail
            if args.trail.is_absolute()
            else REPO_ROOT / args.trail
        )
        plan = build_plan(
            load_trail(path),
            parse_values(args.value),
        )
    except TrailError as exc:
        print(json.dumps({
            "mode": "dry-run",
            "ready": False,
            "errors": [str(exc)],
        }, indent=2))
        return 2

    print(json.dumps(plan, indent=2))
    return 0 if plan["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
