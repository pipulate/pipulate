#!/usr/bin/env python3
"""Mother Cat trail walker, Car B: actuate Car A's validated plan.

walk.py remains the strict, stdlib-only dry-run planner. This module adds the
actuating side of the Mother Cat Kata:

  NARRATE                  -- Piper reads the stop guidance, best-effort.
  SETTLE + FENCE + CAPTURE -- guided_browser_capture opens the persistent,
                              visible browser and requires the human CAPTURE
                              token before writing artifacts.
  ADVANCE                  -- continue only after a successful capture receipt.

Connector execution is deliberately out of scope. This car captures context;
it does not run Jira, Botify, Gmail, or shell actuators.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import walk  # noqa: E402

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _narrate(text, disclosed):
    """Speak scripted guidance if Piper is available; never gate the ride."""
    try:
        from imports.voice_synthesis import chip_voice_system
    except Exception as exc:
        print(f"  (voice import unavailable: {exc}) {text}")
        return disclosed

    if chip_voice_system is None:
        print(f"  (voice unavailable) {text}")
        return disclosed

    try:
        if not disclosed:
            result = chip_voice_system.speak_text(
                "This is the automated trail guide. I read each step aloud; "
                "you handle only the login and the CAPTURE checkpoint."
            )
            if isinstance(result, dict) and not result.get("success"):
                print(
                    "  (voice disclosure failed: "
                    f"{result.get('error', 'unknown error')})"
                )
            disclosed = True

        result = chip_voice_system.speak_text(text)
        if isinstance(result, dict) and not result.get("success"):
            print(
                "  (voice guidance failed: "
                f"{result.get('error', 'unknown error')}) {text}"
            )
    except Exception as exc:
        print(f"  (voice error, continuing: {exc}) {text}")

    return disclosed


def _capture_compatible(trail):
    """Return violations of guided_browser_capture's checked preconditions."""
    defaults = trail.get("defaults", {})
    required = {
        "headless": False,
        "persistent": True,
        "override_cache": True,
    }
    return [
        f"{key} must be {expected!r}; got {defaults.get(key)!r}"
        for key, expected in required.items()
        if defaults.get(key) is not expected
    ]


# --- DECANT: pour captured artifacts into one clipboard-ready payload --------
# The bridge between "captured" and "paste this into any ChatBot." Small,
# high-signal lenses are inlined; large ones (hydrated DOM, raw source) are
# cited by their browser_cache path only, so a huge DOM never floods the
# clipboard. Generic label on purpose (Stick Bug / white-label): the bundle
# calls itself "Artifact Compiler," never "Pipulate."
DECANT_INLINE_KEYS = (
    "seo_md",
    "headers",
    "accessibility_tree_summary",
    "links_md",
    "diff_hierarchy_txt",
    "optics_manifest",
)
DECANT_INLINE_CAP = 20000  # chars per inlined lens; the rest lives on disk


def _decant(captured):
    """Build one markdown capture bundle from a list of (stop, url, artifacts)."""
    parts = [
        "# Artifact Compiler -- Mother Cat capture bundle",
        "",
        "Wire-truth artifacts captured on the operator's machine. Each stop",
        "lists the files written to browser_cache; small high-signal lenses are",
        "inlined below, large ones (hydrated DOM, raw source) are cited by path.",
        "",
    ]
    for stop_name, final_url, artifacts in captured:
        parts.append(f"## Stop: {stop_name}")
        parts.append(f"- final_url: {final_url}")
        parts.append("- artifacts on disk:")
        for key, path in sorted(artifacts.items()):
            parts.append(f"  - {key}: {path}")
        parts.append("")
        for key in DECANT_INLINE_KEYS:
            path = artifacts.get(key)
            if not path or not os.path.exists(path):
                continue
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text) > DECANT_INLINE_CAP:
                text = text[:DECANT_INLINE_CAP] + "\n... [truncated; full file on disk]"
            parts.append(f"### {stop_name} -- {key}")
            parts.append("```text")
            parts.append(text)
            parts.append("```")
            parts.append("")
    return "\n".join(parts)


def _decant_to_clipboard(payload):
    """Copy the bundle to the clipboard, reusing prompt_foo's cross-platform path.

    Deferred import: prompt_foo drags tiktoken/pydot in at module load, so it is
    imported HERE, on a real DECANT only -- never on module import or
    --dry-narrate. Reuse over re-implement: copy_to_clipboard already owns the
    SSH-bridge and the pbcopy/xclip fallbacks.
    """
    from prompt_foo import copy_to_clipboard
    copy_to_clipboard(payload)


async def _ride_async(trail_path, dry_narrate=False):
    trail_path = Path(trail_path)
    trail = walk.load_trail(trail_path)

    problems = _capture_compatible(trail)
    if problems and not dry_narrate:
        print("REFUSING TO RIDE -- trail defaults are not capture-compatible:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    guided_browser_capture = None
    if not dry_narrate:
        from tools.scraper_tools import guided_browser_capture

    stops = trail["stops"]
    print(f"Riding trail '{trail['name']}' -- {len(stops)} stop(s).\n")

    disclosed = False
    for index, stop in enumerate(stops, 1):
        print(f"--- Stop {index}/{len(stops)}: {stop['name']} ---")

        disclosed = _narrate(stop["guidance"], disclosed)

        if dry_narrate:
            print("  (dry-narrate: browser and capture skipped)\n")
            continue

        url_env = stop["url_env"]
        try:
            url = os.environ[url_env]
        except KeyError as exc:
            raise walk.TrailError(
                f"stop {stop['name']!r} requires environment variable {url_env}"
            ) from exc

        params = walk._browser_params(url, trail["defaults"])
        result = await guided_browser_capture(
            params,
            stdin=sys.stdin,
            stdout=sys.stdout,
        )

        if not result.get("success"):
            print(
                f"  CAPTURE failed at {stop['name']!r}: "
                f"{result.get('error', 'no receipt')}"
            )
            print("  Halting -- no ADVANCE without a capture receipt.\n")
            return 1

        artifacts = result.get("looking_at_files", {})
        print(
            f"  Captured. final_url={result.get('final_url')} "
            f"artifacts={len(artifacts)}"
        )

        if index < len(stops):
            print("  ADVANCE -> next stop.\n")

    if dry_narrate:
        print("\nDry narration complete; no captures were attempted.")
    else:
        print("\nRide complete. Every stop produced a capture receipt.")
    return 0


def ride(trail_path=None, dry_narrate=False):
    """Run one validated trail to completion and return a process exit code."""
    path = walk.DEFAULT_TRAIL if trail_path is None else Path(trail_path)
    return asyncio.run(_ride_async(path, dry_narrate=dry_narrate))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mother Cat Car B: actuate a validated trail."
    )
    parser.add_argument(
        "trail",
        nargs="?",
        default=None,
        help="trail path (default: walk.DEFAULT_TRAIL)",
    )
    parser.add_argument(
        "--dry-narrate",
        action="store_true",
        help="narrate each stop without opening a browser or capturing",
    )
    args = parser.parse_args(argv)

    try:
        return ride(args.trail, dry_narrate=args.dry_narrate)
    except walk.TrailError as exc:
        print(f"TRAIL INVALID (Car A refused): {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
