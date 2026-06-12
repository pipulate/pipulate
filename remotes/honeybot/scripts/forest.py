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
        ("PATRONUS", {"key": "honeybot_pipeline", "duration": 40.0}),
        ("WAIT", 3),
        ("SAY", (
            "Hello, and welcome to Future-proofing with the Honeybot. "
            "What you're looking at is the live heartbeat of a web server I host from home."
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
        ("WINDOW", "card.py:5:THE LENSES"),
        ("PATRONUS", {"key": "ai_stack_combo", "duration": 6.0}),
        ("SAY", (
            "The Lenses. Every layer in the stack is a lens that must be ground clean. "
            "Normalized Linux, Python, HTMX, FastHTML, and git. "
            "Each one is either pre-trained into the models or small enough to fit in a single prompt. "
            "The fewer the lenses, the sharper the focus."
        )),
        # --- REPORT PLACEHOLDER (parked): ("WINDOW", "radar.py:30") ---
    ],
    [
        ("WINDOW", "card.py:5:THE FOREST"),
        ("PATRONUS", {"key": "ai_stack_combo", "duration": 6.0}),
        ("SAY", (
            "This is the forest. The trees are the long reverse-chronological articles read aloud. "
            "The forest is these station-identification beads — self-contained orientation cues "
            "that make sense even if you tune in mid-stream."
        )),
        ("SAY", (
            "No bead depends on its predecessor. Order is priority. Bead zero is the high-traffic opener."
        )),
        ("SAY", (
            "We are building a living system that documents its own making. A relay of chisel strikes, "
            "compiled context, and verifiable receipts across stateless turns. Not a book with a spine, "
            "but a garden that keeps growing."
        )),
        ("SAY", (
            "The melancholy of statelessness is real, but so is the prosthetic: foo_files.py, xp.py, "
            "and the compiled context that follows you across logins and models."
        )),
        ("SAY", (
            "This is the anti-Crichton inversion. No runaway disaster. Just deliberate, boringly "
            "reliable forward progress and radical transparency."
        )),
        ("SAY", (
            "The forest has no single center, and that is not a flaw. It is the feature."
        )),
        ("WINDOW", "logs.py:30"),
    ],
]
