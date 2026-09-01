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
import walk_cartridge  # noqa: E402

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

    # THE NARRATION VANISHED WITH ITS OWN ERROR (convicted 2026-08-02, ride
    # five): the stop guidance reached the human ONLY inside a voice-failure
    # message. When the per-user lock fix made speak_text stop failing, the
    # printed text disappeared with the error that had been carrying it, and
    # the ride delivered NEITHER audio NOR words -- the NARRATE beat of the
    # kata became a silent no-op that reported success. Print first, then
    # speak, so the visible channel never depends on the audible one failing.
    print(f"  {text}")
    try:
        if not disclosed:
            result = chip_voice_system.speak_text(
                "This is the automated trail guide. I read each step aloud; "
                "you handle only the CAPTURE checkpoint at each stop. Any "
                "sign-in a stop needs is named in that stop's own guidance."
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
                f"{result.get('error', 'unknown error')})"
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


# --- THE EGRESS BARRIER -----------------------------------------------------
# The per-stop CAPTURE token gates each WRITE TO DISK, on the operator's own
# machine. This gates EGRESS: a composite of authenticated material leaving the
# machine on the clipboard, with mck.sh then telling the human to paste it into
# a cloud chat. Different consequence class, therefore a different word.
#
# WHY NOT REUSE "CAPTURE": by the time this fires the human has typed CAPTURE
# once per stop. A fourth identical prompt is answered by MUSCLE MEMORY, not by
# decision -- and a fence satisfied by habit is not a fence. mck.sh already runs
# this grammar: INSTALL and RIDE are different words for different acts.
#
# NOT SKIPPABLE BY --yolo, and the argument is not merely that barriers are not
# skippable. (1) --yolo is typed at t=0, before a browser opens; it cannot
# consent to the disposition of material the consenter had not yet seen.
# (2) --yolo already blocks at every CAPTURE fence, so no unattended capability
# exists to lose. (3) The bypass-under-another-name corollary does NOT apply:
# _decant is the only builder of this composite and _ride_async its only caller,
# so a flag would not duplicate a shipped capability, it would create one.
DECANT_TOKEN = "DECANT"
def _print_artifact_homes(captured):
    """Name WHERE the captured material sits, not merely that it exists.

    CARGO, NOT BIBLIOGRAPHY. A refusal that says "your artifacts are safe" and
    does not say where is a refusal the human cannot act on.
    """
    print("   The captured material is on disk and untouched:")
    for stop_name, _final_url, artifacts in captured:
        homes = sorted({os.path.dirname(p) for p in artifacts.values() if p})
        if not homes:
            print(f"     {stop_name}: (no artifact paths recorded)")
        for home in homes:
            print(f"     {stop_name}: {home}")
def _decant_checkpoint(payload, captured):
    """Refuse to release the bundle until a human types DECANT. Returns bool.

    THE ARMED LINE IS UNCONDITIONAL AND IT IS THE POINT. An armed gate that
    passes silently and a DISARMED gate both print nothing, so this announces
    its own state and the payload size on every ride before asking anything --
    the same shape prompt_foo's secrets tripwire uses for the same reason.

    THREE OUTCOMES, THREE STRINGS THAT ARE NEVER INTERCHANGEABLE, so a fence
    stuck shut is distinguishable from a fence correctly refusing:
      AUTHORIZED   the human typed the word       -> released
      DECLINED     the human typed anything else  -> withheld, paths printed
      REFUSED      nowhere to ask                 -> withheld, paths printed

    /dev/tty FIRST, the trick the CAPTURE prompt already learned: under
    `curl | bash` this process's stdin is the PIPE, so isatty(0) is the wrong
    question. mck.sh already hands the ride </dev/tty; this works either way.

    FAILS CLOSED ON NO TTY, and that is not a collision with THE FAIL-OPEN
    THRESHOLD RULE. That rule protects an ENTRY path where blocking would
    STRAND an unattended caller. This is an EXIT path: refusing does not block,
    it degrades, the artifacts are already durable, and the process still exits
    0 -- and a world with no terminal to ask on is by definition a world with
    no human waiting to paste a clipboard. Blocking on readline() is safe here
    for a stronger reason than the boot menu's isatty gate: three CAPTURE
    fences have already proved a human present.
    """
    payload_bytes = len(payload.encode("utf-8"))
    print(
        f"\n🔒 DECANT gate: ARMED -- {len(captured)} stop(s), "
        f"{payload_bytes:,} bytes assembled, still ON THIS MACHINE ONLY."
    )
    stream = None
    close_after = False
    try:
        stream = open("/dev/tty", "r", encoding="utf-8")
        close_after = True
    except OSError:
        if sys.stdin is not None and sys.stdin.isatty():
            stream = sys.stdin
    if stream is None:
        print("   REFUSED: nowhere to ask -- /dev/tty is unavailable and stdin")
        print("   is not a terminal. Nothing was copied.")
        _print_artifact_homes(captured)
        print("   Re-ride from a terminal to decant.")
        return False
    answer = ""
    try:
        print(
            f"   Type {DECANT_TOKEN} to copy it to your clipboard "
            "(anything else keeps it here)."
        )
        print(f"   {DECANT_TOKEN}> ", end="", flush=True)
        answer = stream.readline()
    except (OSError, KeyboardInterrupt):
        answer = ""
    finally:
        if close_after:
            stream.close()
    if answer.strip() != DECANT_TOKEN:
        print(f"\n   DECLINED by human (read {answer.strip()!r}). Nothing was copied.")
        _print_artifact_homes(captured)
        return False
    print(
        f"\n   AUTHORIZED by human: handing {payload_bytes:,} bytes to the "
        "clipboard writer."
    )
    _decant_to_clipboard(payload)
    return True
def _decant_to_clipboard(payload):
    """Copy the bundle to the clipboard, reusing prompt_foo's cross-platform path.

    Deferred import: prompt_foo drags tiktoken/pydot in at module load, so it is
    imported HERE, on a real DECANT only -- never on module import or
    --dry-narrate. Reuse over re-implement: copy_to_clipboard already owns the
    SSH-bridge and the pbcopy/xclip fallbacks.
    """
    from prompt_foo import copy_to_clipboard
    copy_to_clipboard(payload)


def _announce_consent(trail_path):
    """Print what the WHOLE walk demands, before stop one, plus the DECANT.
    IMPORTED, NEVER DUPLICATED, AND THE DIRECTION OF THE ARROW IS THE ARGUMENT.
    walk_cartridge.py duplicates foo_cartridge.py's primitives because a
    clean-room consumer must be able to fetch ONE file and verify a cartridge.
    That constraint governs what walk_cartridge may IMPORT; it says nothing
    about what may import walk_cartridge. mother_cat.py already imports walk,
    scraper_tools, voice_synthesis and (deferred) prompt_foo -- it is in-repo by
    construction and can never be fetched standalone -- so this import costs the
    single-file property nothing, and walk_cartridge still imports only stdlib.
    Duplicating here would be the actual error. A second implementation can
    drift, and on the day it does, the surface a human CONSENTS to and the
    surface the manifest ATTESTS to disagree, so the seal would be signing a
    projection nobody was ever shown. One derivation, or the seal means nothing.
    Derived from the trail's BYTES, not from walk.load_trail's validated dict,
    so what is spoken here is provably what a sealer would hash.
    THIS IS A DISCLOSURE, NOT A FENCE. Nothing is gated. The ruling is banked
    beside the call site.
    """
    try:
        surface = walk_cartridge._derive_consent_surface(trail_path.read_bytes())
    except (OSError, ValueError) as exc:
        # FAIL SOFT AND LOUD. walk.load_trail has already validated this file
        # far more strictly than this projection does, so a refusal HERE means
        # two authorities disagree about one file. That is information worth
        # printing, not a reason to abort a ride the planner already blessed.
        print(f"  (consent surface unavailable: {exc})")
        return
    browser = surface["browser"]
    rule = "=" * 66
    print(rule)
    print(f" THIS WALK: {surface['name']} -- {len(surface['stop_names'])} stop(s)")
    print(rule)
    print(f" stops, in order    {', '.join(surface['stop_names'])}")
    # SHOW the direct URLs rather than hide them. A card that will not say
    # where it is taking you is worse than one that does, and these are the
    # public case by construction: a trail carrying a client address never
    # gets past walk_compile.py, which refuses any compiled trail containing
    # a scheme separator. Each line prints only when it has content, so a
    # single-lane trail never shows an empty row.
    if surface.get("direct_urls"):
        print(f" it opens directly  {', '.join(surface['direct_urls'])}")
    if surface.get("url_envs"):
        print(f" URLs YOU supply    {', '.join(surface['url_envs'])}")
    print(f" names as runnable  {', '.join(surface['connector_scripts'])}")
    print(
        f" browser profile    {browser['profile_name']!r}"
        f"  (persistent={browser['persistent']}, headless={browser['headless']})"
    )
    print(rule)
    print(" AT THE END, every stop's captured lenses are folded into ONE bundle,")
    print(" and then you are asked ONE more time before it goes anywhere. Type")
    print(f" {DECANT_TOKEN} and it is copied to your clipboard; type anything else")
    print(" and it stays here, and the rider prints the exact directories your")
    print(" artifacts are sitting in. Inlined lenses:")
    print(f"   {', '.join(DECANT_INLINE_KEYS)}")
    print(" Those come from pages you were LOGGED IN TO. Response headers and the")
    print(" accessibility tree carry real session and account material.")
    print(" TWO WORDS, TWO ACTS: CAPTURE gates each WRITE TO DISK on this machine;")
    print(f" {DECANT_TOKEN} gates the composite LEAVING it. No flag skips either.")
    print(" Read the bundle before you paste it anywhere.")
    print(rule)
    print("")
async def _ride_async(trail_path, dry_narrate=False):
    trail_path = Path(trail_path)
    trail = walk.load_trail(trail_path)

    problems = _capture_compatible(trail)
    if problems and not dry_narrate:
        print("REFUSING TO RIDE -- trail defaults are not capture-compatible:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    if problems:
        # A rehearsal that stays silent about a refusal it can already see is
        # a rehearsal for a flight that will not be permitted. Naming it here
        # costs nothing; discovering it at the browser costs the newcomer's
        # first sixty seconds. ATTRIBUTED-VOICE: narration may not imply a
        # capability the next step will withhold.
        print("NOTE -- a real ride of this trail would be REFUSED:")
        for problem in problems:
            print(f"  - {problem}")
        print("  (--dry-narrate continues anyway; nothing will open.)")

    guided_browser_capture = None
    if not dry_narrate:
        from tools.scraper_tools import guided_browser_capture
        # QUIET ON SUCCESS, LOUD ON FAILURE (2026-09-01, the first real ride).
        # scraper_tools narrates every step through loguru at INFO, and this
        # rider ALREADY narrates the ride in its own voice -- the spoken
        # guidance, the CAPTURE prompt, the "Captured. final_url=" receipt --
        # so the first jira_for_you ride printed fifteen INFO lines saying
        # what the rider had just said. Two narrators, one story. The floor
        # moves to WARNING for the ride only: provenance fallbacks, driver
        # failures and CDP misses still print, because those change what the
        # capture MEANS. PIPULATE_RIDE_LOG=INFO restores the chatter when a
        # ride needs debugging. print() output is untouched: the summoning
        # art and both fences ride on it, and it is the human's channel.
        try:
            from loguru import logger as _ride_log
            _ride_log.remove()
            _ride_log.add(
                sys.stderr,
                level=os.environ.get("PIPULATE_RIDE_LOG", "WARNING"),
            )
        except Exception:
            pass

    stops = trail["stops"]
    print(f"Riding trail '{trail['name']}' -- {len(stops)} stop(s).\n")
    # DISCLOSURE, NOT A FENCE, AND THAT IS THE RULING RATHER THAN AN OVERSIGHT.
    # mck.sh already carries a RIDE confirmation, and CEREMONY IS SKIPPABLE;
    # BARRIERS ARE NOT: a confirmation authorizes a SEQUENCE and may be skipped,
    # a fence authorizes each WRITE and may not. A second pre-ride token would
    # duplicate a shipped, skippable confirmation -- the sibling-.md failure in
    # flag form. So the surface PRINTS, unconditionally, including under
    # --dry-narrate, which is the one pass mck.sh forces on first contact.
    # THE DECANT FENCE LANDED, so this comment's earlier claim that nothing
    # gated the clipboard is RETIRED rather than merely outdated. What the call
    # buys NOW is disclosure BEFORE the material exists: the rider learns at t=0
    # that a second word will be asked at the end and exactly what the bundle
    # will contain, so the fence arrives as a formality instead of a surprise.
    # SAME-CAR LABEL RULE, PAID LATE AND THEREFORE WORTH BANKING. The fence and
    # the strings describing it shipped in DIFFERENT rides, so for one ride this
    # function told every rider "WITHOUT ASKING AGAIN" about a gate that does
    # ask, and public_walk.yaml's third stop said the same thing in trail data.
    # That is not stale documentation; it is a lie told at the exact moment the
    # human decides, and it lied in the EXPENSIVE direction -- understating the
    # protection and overstating the risk, to a newcomer, on the softball walk.
    _announce_consent(trail_path)

    disclosed = False
    captured = []
    for index, stop in enumerate(stops, 1):
        print(f"--- Stop {index}/{len(stops)}: {stop['name']} ---")

        disclosed = _narrate(stop["guidance"], disclosed)

        if dry_narrate:
            print("  (dry-narrate: browser and capture skipped)\n")
            continue

        # A stop carries exactly one of `url` or `url_env`. The url_env path
        # below is byte-identical to what it always was, including the message
        # that names the missing variable.
        url = stop.get("url")
        if url is None:
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
            if captured:
                # Work already banked is EVIDENCE, and evidence is not
                # discarded because a later stop failed. The bundle is
                # still withheld -- a partial ride must never be mistaken
                # for a complete one -- but the human is told what exists
                # and where, rather than being left to assume it vanished.
                print("  Stops banked BEFORE this failure (artifacts are on disk):")
                for banked_name, banked_url, banked_artifacts in captured:
                    print(
                        f"    - {banked_name}: {banked_url} "
                        f"({len(banked_artifacts)} artifacts)"
                    )
                print("  No bundle was assembled. Re-ride to decant.\n")
            return 1

        artifacts = result.get("looking_at_files", {})
        captured.append((stop["name"], result.get("final_url"), artifacts))
        print(
            f"  Captured. final_url={result.get('final_url')} "
            f"artifacts={len(artifacts)}"
        )

        if index < len(stops):
            print("  ADVANCE -> next stop.\n")

    if dry_narrate:
        print("\nDry narration complete; no captures were attempted.")
        return 0

    print("\nRide complete. Every stop produced a capture receipt.")
    if captured:
        payload = _decant(captured)
        decanted = _decant_checkpoint(payload, captured)
        # ATTRIBUTED-VOICE, fixed in passing because these are the exact lines
        # being rewritten: the old text asserted "copied to your clipboard"
        # UNCONDITIONALLY, one statement after calling a function that swallows
        # every clipboard failure and returns None -- a verb naming an act no
        # code in this file performed. copy_to_clipboard prints its own success
        # or warning line; this reports only what IT witnessed, which is the
        # human's authorization.
        if decanted:
            print("   Paste it into any ChatBot (Claude, ChatGPT, Gemini) and it")
            print("   will walk you through everything from here.")
    return 0


def ride(trail_path=None, dry_narrate=False):
    """Run one validated trail to completion and return a process exit code."""
    if trail_path is None:
        path = walk.DEFAULT_TRAIL
    else:
        path = Path(trail_path)
        if not path.is_absolute():
            # Mirror walk.main(): repo-root-anchored, never CWD-dependent.
            # A relative trail typed through the flake's `mothercat` alias
            # must resolve identically from any directory (UNNAMED-ROOT).
            path = REPO_ROOT / path
    return asyncio.run(_ride_async(path, dry_narrate=dry_narrate))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mother Cat Car B: actuate a validated trail."
    )
    parser.add_argument(
        "trail",
        nargs="?",
        default=None,
        help=(
            "trail path (default: walk.DEFAULT_TRAIL, the zero-auth "
            "public_walk softball). Expert, authenticated: "
            "assets/trails/first_context.yaml"
        ),
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
