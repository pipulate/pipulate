#!/usr/bin/env python3
"""
🌲 forest.py — The station-break (forest) roll.

The trees roll is the reverse-chronological article reading in show.py. The
forest roll is this slow, front-loaded necklace of self-contained "beads" — the
station-identification breaks that interleave between articles.

Each bead is an ordered cue-list in the SAME sheet-music grammar perform_show
already speaks: ("SAY", text), ("PATRONUS", key-or-dict), ("WINDOW",
"script.py:seconds[:arg]"), ("VISIT", url), ("WAIT", seconds), ("CLOSE", _).
That is the cathedral-of-one collapse: the forest inherits the full brush set
through the existing dispatcher instead of carrying its own special-cased
unpacking. Editing the forest is now editing data here, not the threading-heavy
engine in stream.py.

ORDER IS PRIORITY: _station_index resets to 0 on every process restart
(episodic by design), so bead 0 is the highest-traffic "opening commercial."
A viewer who tunes in mid-stream must be able to make sense of any single bead
cold — no bead may depend on having heard its predecessor.

WINDOW grammar note: the optional third field is a single argument forwarded to
the script (e.g. the Figlet card label). It is delimited by ':' so the argument
must not itself contain a colon. Bare labels like "THE ITCH" are fine.
"""

# A bead is a list of (command, content) cues, played top-to-bottom during a
# break. Convention: card banner first, then art + spiel + proof report.
STATION_SEGMENTS = [
    [
        # The opening bead. The title card flashes, then the ingress-to-broadcast
        # diagram lands and breathes (a silent WAIT) before the narration walks it
        # left to right. No live report dashboard here yet — see the parked
        # placeholder at the foot of the bead. Tune the PATRONUS duration by ear:
        # it should outlast the spoken walkthrough so the art never blinks out
        # mid-sentence.
        ("WINDOW", "card.py:5:HONEYBOT"),
        ("PATRONUS", {"key": "white_rabbit", "duration": 80.0}),
        # ("PATRONUS", {"key": "honeybot_pipeline", "duration": 80.0}),
        ("WAIT", 3),
        ("SAY", (
            "Hello, and welcome to Future-proofing with the Honeybot. "
            "What you're looking at is the live heartbeat of a web server I host from home. "
            "I do this to invite AI bots to my doorstep, to observe and interact with them. "
        )),
        ("SAY", (
            "This diagram is the whole pipeline. Traffic arrives from the public internet "
            "and hits a single Nginx engine. That engine is the only front door."
        )),
        ("SAY", (
            "Nginx does content negotiation. A human browser is handed hydrated HTML. "
            "An AI agent that asks for it is handed raw Markdown. One URL, two faces."
        )),
        ("SAY", (
            "Every request, human or robot, is written as a single line to a high-fidelity "
            "access log. That log is the source of truth for everything you see."
        )),
        ("SAY", (
            "A Unix pipe tails that log into a Textual heads-up display, the cascading wall "
            "of text on your screen, and OBS streams the whole thing out live."
        )),
        ("SAY", (
            "In the age of AI, that log is a field notebook. It shows which crawlers execute "
            "JavaScript, and which negotiate for Markdown. That is the new SEO, and this is "
            "where we begin."
        )),
        # --- REPORT PLACEHOLDER (parked) ---
        # A live Textual dashboard can pop up here as an out-of-band overlay via the
        # WINDOW cue, e.g. ("WINDOW", "education.py:30"). Grammar is
        # "script.py:seconds[:arg]". Parked until each report is tested on its own
        # for clean z-order layering OVER the patronus art; today they pop UNDER it
        # and dismiss it early, which is the bug this pass removes.
        # ("WINDOW", "education.py:30"),
    ],
    [
        # Bead 2: The orienting beat. The viewer now knows this is a live home
        # webserver log; the natural next question is "what IS this project?".
        # white_rabbit is the Pipulate mascot and wax seal — a concrete, friendly
        # second beat that NAMES the thing before bead 3 explains its philosophy.
        ("WINDOW", "card.py:5:PIPULATE"),
        ("PATRONUS", {"key": "white_rabbit", "duration": 35.0}),
        ("WAIT", 2),
        ("SAY", (
            "The project behind all of this is called Pipulate. "
            "It runs on a stack we call NPvg."
        )),
        ("SAY", (
            "N is for Nix, a package manager that makes a software environment "
            "fully reproducible on any machine. P is for Python. The little v is for Vim. "
            "And g is for Git."
        )),
        ("SAY", (
            "The white rabbit on screen is the mascot, and also a wax seal. "
            "It is a piece of ASCII art with a registered checksum baked into the codebase. "
            "If the art ever drifts from what was recorded, the system raises a warning. "
            "Drift means something touched the painting."
        )),
        ("SAY", (
            "Pipulate sits where AI assistance meets local ownership. "
            "The whole bet is that you do not need a cloud subscription to do serious work. "
            "You need the right text files, the right habits, and a machine you actually own."
        )),
        # --- REPORT PLACEHOLDER (parked): ("WINDOW", "radar.py:30") ---
    ],
]
