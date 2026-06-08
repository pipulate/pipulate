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
        ("WINDOW", "card.py:5:THE ITCH"),
        ("PATRONUS", {"key": "player_piano", "duration": 6.0}),
        ("SAY", (
            "The Itch. Every useful tool starts with a genuine irritation. "
            "Python ships with batteries included, but not every itch has a battery yet. "
            "FastAPI scratched the A P I server itch, but it smuggled in the entire JavaScript industrial complex. "
            "The itch that remained was a Python-native local web app cockpit. "
            "FastHTML and HTMX performed the node-echtomy."
        )),
        ("WINDOW", "education.py:30"),
    ],
    [
        ("WINDOW", "card.py:5:THE LENSES"),
        ("PATRONUS", {"key": "ai_stack_combo", "duration": 6.0}),
        ("SAY", (
            "The Lenses. Every layer in the stack is a lens that must be ground clean. "
            "Normalized Linux, Python, HTMX, FastHTML, and git. "
            "Each one is either pre-trained into the models or small enough to fit in a single prompt. "
            "The fewer the lenses, the sharper the focus."
        )),
        ("WINDOW", "radar.py:30"),
    ],
]
