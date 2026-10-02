#!/usr/bin/env python3
"""
stick_bug.py -- osb, OPERATION STICK BUG: the one loud screen in a quiet workshop.

The menu stays dry on purpose; this is what hides under it. A twig that
moves, a banner, a block of READINGS this program takes at the moment it
prints them, and then six short transmissions that say they are a story.
Every reading names what it looked at. Nothing in the story is a reading.

  osb              the whole thing; at a keyboard, Enter between transmissions
  osb --readings   the readings only, then exit (what a compile can witness)

Stdlib first. rich and pyfiglet, which the workshop's venv carries, make it
louder; without them it prints the same words in plain text. If narration is
on, Piper says one line from a detached child, the way the menu's hint does,
and says that it is reading a script.
"""
import os
import platform
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TRANSMISSIONS = (
    ("THE TWIG",
     "A stick bug lives by looking like a twig: nothing to see, so nothing eats it. "
     "This workshop looks like a dull checklist for checking what an AI said, and it "
     "is one. Under the bark there is a clock, a probe, a fence, a primer and a "
     "tortoise."),
    ("THE CLOCK",
     "The clock reading above counts seconds from the first second of 1970, the way "
     "Unix does. Unix was started at Bell Labs in Murray Hill, New Jersey, in 1969, "
     "and named as a pun on Multics, a far bigger system: Unics, said like eunuchs. "
     "Small, plain and hard to corrupt beat big and clever, and its descendants run "
     "under almost everything, this workshop included."),
    ("THE PROBE",
     "John von Neumann worked out, on paper, a machine that builds a copy of itself "
     "from parts it finds (Theory of Self-Reproducing Automata, 1966). Science fiction "
     "sent such machines to the stars as probes. You typed one line. It fetched a "
     "recipe, and the recipe built this workshop from parts on your own computer, "
     "pinned to the same versions it pins everywhere. Java promised that in 1995: "
     "write once, run anywhere. Eelco Dolstra's 2006 PhD thesis worked out how to "
     "deliver it. The thing it describes is Nix."),
    ("THE FENCE",
     "In Michael Crichton's Jurassic Park (1990), the park's computer counted its "
     "animals by searching for the number it expected, 238, so it could never find "
     "more. Told to search for more, it kept finding more, 292 in the end: the "
     "animals were breeding. A check that cannot fail is not a check. Every check "
     "here is built so that it can fail, and apply.py, the fence around every edit, "
     "is short enough to read in one sitting. Read it."),
    ("THE PRIMER",
     "In Neal Stephenson's The Diamond Age (1995), a girl named Nell is raised by a "
     "book that talks back, the Young Lady's Illustrated Primer. It worked for her "
     "because a person, Miranda, voiced it from far away. The voice in this workshop "
     "is Piper, a small text-to-speech program, and it says that it is reading a "
     "script, because a voice should say who is talking."),
    ("THE TORTOISE",
     "In 1895 Lewis Carroll wrote a short dialogue in which a Tortoise will not accept "
     "a conclusion until Achilles writes the rule that leads to it down as one more "
     "premise, and then the rule for that one, forever. Douglas Hofstadter put the "
     "pair back to work in Gödel, Escher, Bach (1979). Asking one AI to check another "
     "AI's answer is the Tortoise's game: one more premise every time. The way out is "
     "to run something and read what it printed. That is what a receipt is."),
)

FINALE = ("So'wI' yIchu'.  (Klingon: engage the cloaking device.)",
          "Type menu to go back to being a twig.")

TWIG = "  " + "=" * 46
BUG = ("     \\      \\      \\",
       "  " + "=" * 46 + "<o)",
       "     /      /      /")
SPOKEN = "This is Piper, reading a script. You found Operation Stick Bug."


def tilde(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def readings() -> list:
    """(label, value) pairs, each taken now; a failed lookup says so in its row."""
    rows = [("folder", tilde(str(ROOT)))]

    try:
        sys.path.insert(0, str(ROOT))
        from imports.voice_synthesis import read_door, voice_consent, local_ai_line
        door = read_door().get("door")
        rows.append(("door", f"{door} (read from .door)" if door else "none (no .door in this folder)"))
        voice = {"yes": "on", "no": "off"}.get(voice_consent(), "not asked yet")
        local_ai = local_ai_line()
    except Exception as exc:
        unread = f"unread ({type(exc).__name__}: {exc})"[:70]
        rows.append(("door", unread))
        voice = local_ai = unread

    rows.append(("computer", f"{platform.system()} {platform.machine()}"))

    exe = os.path.realpath(sys.executable)
    if exe.startswith("/nix/store/"):
        store = "/".join(exe.split("/")[:4])
        writable = "writable by you" if os.access(store, os.W_OK) else "read-only to you"
        rows.append(("python", f"{platform.python_version()} in {store}"))
        rows.append(("", f"{writable} (checked just now)"))
    else:
        rows.append(("python", f"{platform.python_version()} at {exe} (not in the Nix store)"))

    try:
        text = (ROOT / "__init__.py").read_text(encoding="utf-8")
        version = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M).group(1)
        name = re.search(r'^__version_description__\s*=\s*"([^"]+)"', text, re.M)
        rows.append(("version", f"v{version}" + (f" {name.group(1)}" if name else "")))
    except Exception as exc:
        rows.append(("version", f"unread ({type(exc).__name__})"))

    rows.append(("voice", voice))
    rows.append(("local AI", local_ai))
    rows.append(("clock", f"{int(time.time()):,} seconds since 1970 began (Unix time)"))
    return rows


def say(line: str) -> None:
    """Piper says one line if narration is on; never waits, never raises."""
    if not sys.stdout.isatty():
        return
    try:
        import subprocess
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from imports.voice_synthesis import chip_voice_system as v; "
                "v and v.speak_text(sys.argv[2])")
        subprocess.Popen([sys.executable, "-c", code, str(ROOT), line],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass


def print_readings(console=None) -> None:
    title = "OPERATION STICK BUG: readings, each one taken just now"
    rows = readings()
    width = max(len(label) for label, _ in rows)
    if console is not None:
        console.print(f"[bold green]{title}[/bold green]")
        for label, value in rows:
            console.print(f"  [green]{label.ljust(width)}[/green]  {value}", highlight=False, soft_wrap=True)
    else:
        print(title)
        for label, value in rows:
            print(f"  {label.ljust(width)}  {value}")


def wait_or_quit(interactive: bool) -> bool:
    """At a keyboard, Enter goes on and q stops. Returns False to stop."""
    if not interactive:
        return True
    try:
        answer = input("  (Enter for the next transmission, q to stop) ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return not answer.strip().lower().startswith("q")


def main() -> int:
    args = set(sys.argv[1:])
    if "--readings" in args:
        print_readings()
        return 0

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    console = None
    try:
        from rich.console import Console
        console = Console(highlight=False)
    except Exception:
        pass

    print()
    if interactive:
        print(TWIG, flush=True)
        time.sleep(1.2)
        print("\033[1A\033[2K", end="")
    for line in BUG:
        print(line)
    print("          the twig moved.")
    print()
    say(SPOKEN)

    banner = "OPERATION STICK BUG"
    try:
        from pyfiglet import Figlet
        banner = Figlet(font="slant", width=100).renderText("STICK BUG").rstrip("\n")
    except Exception:
        pass
    if console is not None:
        from rich.panel import Panel
        from rich.text import Text
        console.print(Panel(Text(banner, style="bold green"),
                            title="[bold]osb[/bold]",
                            subtitle="operation stick bug: you typed the twig",
                            border_style="green", expand=False))
    else:
        print(banner)
        print("osb -- operation stick bug: you typed the twig")
    print()
    print_readings(console)
    print()

    count = len(TRANSMISSIONS)
    for number, (title, body) in enumerate(TRANSMISSIONS, start=1):
        if not wait_or_quit(interactive):
            break
        heading = f"TRANSMISSION {number} OF {count}: {title}   (a story; nothing here was measured)"
        if console is not None:
            from rich.panel import Panel
            from rich.text import Text
            console.print(Panel(Text(body), title=f"[bold green]{heading}[/bold green]",
                                border_style="green", width=min(console.width, 80)))
        else:
            import textwrap
            print(heading)
            print(textwrap.fill(body, width=76, initial_indent="  ", subsequent_indent="  "))
            print()
    else:
        for line in FINALE:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
