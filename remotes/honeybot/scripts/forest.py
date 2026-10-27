#!/usr/bin/env python3
"""
🌲 forest.py -- The station-break (forest) roll.

The trees roll is the reverse-chronological article reading in show.py. The
forest roll is this slow, front-loaded necklace of self-contained "beads" -- the
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
cold -- no bead may depend on having heard its predecessor.

WINDOW grammar note: the optional third field is a single argument forwarded to
the script (e.g. the Figlet card label). It is delimited by ':' so the argument
must not itself contain a colon. Bare labels like "THE ITCH" are fine.
"""

# 5-PART STATION IDENTIFICATION ARCHITECTURE:
# Every bead in STATION_SEGMENTS follows the 5-beat funnel:
#   1. Figlet Card (CARD)
#   2. What's Happening Here + Viral Trigger (SAY while HUD panels are visible)
#   3. What Article Is Being Read & How to Read It in Full ({CURRENT_ARTICLE})
#   4. Consulting Call-to-Action ($10,000/mo HTML pre-render savings via RFC 9110/9111/9421)
#   5. The ASCII Art Developing the Running "Forest Through the Trees" Story (PATRONUS + SAY)

WHATS_HAPPENING_BEAT = (
    "What is happening on your screen right now? You are watching the live Web Bot AI Observatory. If you are not watching the behavior of AI bots and Agents directly on the wire meaning not behind a CDN, then you don't really have a feel for what's going on. You have to watch it for awhile like fish in a fish tank. It's changing and you need to be watching it on a site like this to develop that intuitive feel of the truth rather than repeating what you hear in the social media echo chambers. Round oranges highlight every self-asserted crawler. Blue diamonds mark agents cryptographically signing requests under R F C 9421 Web Bot Auth. Red stop signs unmask crawlers spoofing Googlebot I P addresses. Hit Like and Subscribe right now so you don't lose this telemetry feed, and copy this live stream link and send it to an engineer or technical S E O who can explain the two bottom intelligence panels to you. "
)

CURRENT_ARTICLE_BEAT = "{CURRENT_ARTICLE}"

CONSULTING_CTA_BEAT = (
    "Are you spending ten to twenty thousand dollars a month and up on H T M L pre-rendering? "
    "Did you know that fully implemented new web standards, including R F C 9110 Markdown content negotiation, "
    "R F C 9111 edge cache partitioning, and R F C 9421 Web Bot Auth, can save you that money? "
    "Contact Mike Levin at Mike L E V dot eye N for a consultation."
)


def _make_station_bead(card_label, card_say, capstone_cue, forest_story_lines, post_linger=None):
    """Assemble a 5-part station identification bead alternating Rich WINDOW reports and PATRONUS art."""
    cues = [
        # 1. Figlet Banner Intro
        ("CARD", {"label": card_label, "say": card_say}),
        # 2. What's Happening Here (spoken over the live Web Bot AI Observatory HUD)
        ("SAY", WHATS_HAPPENING_BEAT),
        # 3. What Article Is Being Read & How to Read It in Full
        ("SAY", CURRENT_ARTICLE_BEAT),
        # 4. Consulting Call-to-Action ($10k/mo HTML Pre-Render Hook)
        ("CARD", {"label": "$15K/MO\nPRE-RENDER?", "say": CONSULTING_CTA_BEAT}),
        # 5. Visual Capstone: Alternates between a Rich Data Report (WINDOW) and Forest ASCII Art (PATRONUS)
        capstone_cue,
        ("WAIT", 2),
    ]
    for line in forest_story_lines:
        cues.append(("SAY", line))
    if post_linger is None:
        is_bar_report = (
            isinstance(capstone_cue, tuple)
            and len(capstone_cue) >= 2
            and capstone_cue[0] == "WINDOW"
            and any(tag in str(capstone_cue[1]) for tag in (":overview", ":bimodal", ":rfc9421"))
        )
        post_linger = 6 if is_bar_report else 0
    if post_linger > 0:
        cues.append(("WAIT", int(post_linger)))
    return cues


STATION_SEGMENTS = [
    # Bead 0 (EVEN -> Rich Horizontal-Bar Telemetry Report: Overview)
    _make_station_bead(
        "WEB BOT AI\nOBSERVATORY",
        (
            "Hello, and welcome to the Web Bot A I Observatory on Honeybot. "
            "What you are looking at is the unmediated, bare-metal heartbeat of a Nix O S web server hosted from home."
        ),
        ("WINDOW", "forest.py:65:overview"),
        [
            "This live telemetry card pulls straight from our SQLite wire ledger.",
            "The first horizontal bar tracks R F C 9110 Markdown adoption along our zero to twenty percent horizon.",
            "The second bar compares DOM hydration JavaScript executions against raw Markdown reads, while the bottom bars track R F C 9421 cryptographic bot signatures and unmasked Googlebot cloakers.",
        ],
    ),
    # Bead 1 (ODD -> Patronus ASCII Art: white_rabbit)
    _make_station_bead(
        "PIPULATE\nNPvg",
        (
            "The open-source project powering this observatory is called Pipulate, running on a stack we call N P v g."
        ),
        ("PATRONUS", {"key": "white_rabbit", "duration": 65.0}),
        [
            "N is for Nix, making the entire software environment reproducible on any machine. P is for Python. The little v is for Vim. And g is for Git.",
            "The white rabbit on screen is both our mascot and a cryptographic wax seal with a registered checksum baked into the codebase.",
            "Pipulate sits where A I assistance meets local hardware ownership. You do not need a multi-tenant cloud subscription to command your own stack.",
        ],
    ),
    # Bead 2 (EVEN -> Rich Horizontal-Bar Telemetry Report: Bimodal JS vs Markdown)
    _make_station_bead(
        "BIMODAL\nWIRE TRUTH",
        (
            "Which A I crawlers execute client-side JavaScript, and which negotiate directly for clean Markdown?"
        ),
        ("WINDOW", "forest.py:65:bimodal"),
        [
            "This report compares our two primary ingestion sensors in real time.",
            "On top are the bots firing our JavaScript DOM hydration trapdoor, led by Open A I's SearchBot, Meta External Agent, and GPTBot.",
            "On the bottom are the R F C 9110 Markdown negotiators requesting clean text at wire speed without spinning up a headless browser.",
        ],
    ),
    # Bead 3 (ODD -> Patronus ASCII Art: ai_pachinko)
    _make_station_bead(
        "AI PACHINKO",
        (
            "Every token an A I model generates is a ball dropped through a pachinko parlor of frozen mathematical weights."
        ),
        ("PATRONUS", {"key": "ai_pachinko", "duration": 65.0}),
        [
            "An L L M has no persistent memory of its own between sessions. When the context window closes, its working memory dissolves.",
            "That is why we pair the pachinko machine with a cybernetic governor: plain-text files in git, before-and-after falsifying probes, and wire-truth receipts.",
        ],
    ),
    # Bead 4 (EVEN -> Rich Horizontal-Bar Telemetry Report: RFC 9421 & Unmasked Cloakers)
    _make_station_bead(
        "RFC 9421\nWEB BOT AUTH",
        (
            "How do you tell a cryptographically signed A I agent from an unmasked IP cloaker?"
        ),
        ("WINDOW", "forest.py:65:rfc9421"),
        [
            "This report shows our three-shape bot identity taxonomy in action.",
            "Blue diamonds mark operators sending R F C 9421 Signature-Agent headers on the wire, including Exa Search Bot, Exa User, Ahrefs Bot, and Desearch Bot.",
            "Red stop signs unmask scrapers claiming to be Googlebot from non-Google I P addresses that fail forward-confirmed reverse D N S.",
        ],
    ),
    # Bead 5 (ODD -> Patronus ASCII Art: mechanical_man)
    _make_station_bead(
        "THE AIRLOCK",
        (
            "How do you collaborate with frontier A I models without letting hallucinations wreck your production systems? Meet Smith and Tinker's Patent Mechanical Man."
        ),
        ("PATRONUS", {"key": "mechanical_man", "duration": 65.0}),
        [
            "In L. Frank Baum's Oz books, Tik-Tok is a clockwork robot with three separate wind-up keys: one for thought, one for speech, and one for action.",
            "In our workflow, the context compiler winds the thought key, and the model's reply winds the speech key. But the action key stays in the human engineer's hand.",
            "Every code edit passes through an exact-match search and replace airlock with syntax tree verification before touching disk.",
        ],
    ),
    # Bead 6 (EVEN -> Rich 8-Door Frequency Dial Report: doors)
    _make_station_bead(
        "EIGHT DOORS\nONE ENGINE",
        (
            "Why does one home-hosted Nix O S head-end broadcast across eight distinct domain names? "
            "Because saying more requires saying less to each audience."
        ),
        ("WINDOW", "forest.py:65:doors"),
        [
            "Each door on this frequency dial scratches one specific engineering itch using the same underlying Software Von Neumann Probe.",
            "Sun Pug dot eye oh frees your A I discussions from disposable browser tabs into portable plain text. "
            "Q A my dot A I seals cryptographic flight-recorder deeds. "
            "N P V G dot org teaches timeless Nix, Python, Vim, and Git skills, while Levinix dot org replaces bloated Electron containers.",
            "Guerilla Tech dot com pits declarative Nix O S against Docker for home hosting, "
            "R F C 9110 dot org demonstrates native Markdown content negotiation, "
            "and R F C 9111 dot eye oh retires wasteful headless pre-render clusters. "
            "Inspect any door safely in your terminal with curl pipe less.",
        ],
    ),
]

DOOR_DIAL_ROWS = (
    ("pipulate", "com", "~/pipulate", "Local-First AI & SEO Readiness Hub"),
    ("npvg", "org", "~/npvg", "Nix, Python, vim & git Future-Proofing"),
    ("qamy", "ai", "~/qamyai", "Flight Data Recorder & QA Archive Deeds"),
    ("levinix", "org", "~/levinix", "Write-Once-Run-Anywhere Nix Flakes"),
    ("sunpug", "io", "~/sunpug", "Portable Plain-Text AI Discussions"),
    ("guerillatech", "com", "~/guerillatech", "NixOS vs. Docker DIY Home-Hosting"),
    ("rfc9110", "org", "~/rfc9110", "HTTP Section 12 Markdown Negotiation"),
    ("rfc9111", "io", "~/rfc9111", "Bimodal Edge Caching (Vary: Accept)"),
)


def _bar(pct, width=32, fill_color="cyan"):
    """Build a Rich-styled horizontal bar gauge string."""
    p = max(0.0, min(100.0, float(pct)))
    filled = int(round((p / 100.0) * width))
    if p > 0 and filled == 0:
        filled = 1
    empty = max(0, width - filled)
    return f"[{fill_color}]{'█' * filled}[/{fill_color}][dim]{'░' * empty}[/dim]"


def _build_station_report_panel(mode="overview"):
    """Query honeybot.db in read-only fast mode and return a Rich Panel renderable."""
    import os
    os.environ.setdefault("HONEYBOT_DB_READONLY", "1")
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from db import db

    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(SUM(count), 0) FROM daily_logs")
    total_hits = int((cur.fetchone() or [1])[0] or 1)

    cur.execute("SELECT COALESCE(SUM(l.count), 0) FROM daily_logs l JOIN paths p ON l.path_id = p.id WHERE p.value LIKE '%.md%'")
    md_reads = int((cur.fetchone() or [0])[0] or 0)
    md_pct = round((md_reads / max(1, total_hits)) * 100.0, 2)
    md_horizon_pct = min(100.0, round((md_pct / 20.0) * 100.0, 1))

    cur.execute("SELECT COALESCE(SUM(l.count), 0) FROM daily_logs l JOIN paths p ON l.path_id = p.id WHERE p.value LIKE '%js_confirm.gif%'")
    js_hits = int((cur.fetchone() or [0])[0] or 0)
    bimodal_total = max(1, js_hits + md_reads)
    js_share = round((js_hits / bimodal_total) * 100.0, 1)
    md_share = round(100.0 - js_share, 1)

    sig_clients, sig_events = db.get_rfc9421_summary()
    cneg_rows = db.get_content_neg_agents(limit=30)
    spoof_md = sum(int(c) for u, c in cneg_rows if str(u).startswith("[SPOOFED-IP]"))
    total_cneg = max(1, sum(int(c) for _, c in cneg_rows))
    spoof_pct = round((spoof_md / total_cneg) * 100.0, 1)
    auth_pct = round(100.0 - spoof_pct, 1)

    tbl = Table(expand=True, show_header=True, header_style="bold cyan", border_style="bright_blue")
    if mode == "bimodal":
        title_str = "⚡ DOM HYDRATION TRAPDOOR vs. 🧠 RFC 9110 MARKDOWN NEGOTIATORS"
        tbl.add_column("Sensor / Agent", style="bold white", ratio=4, no_wrap=True)
        tbl.add_column("Hits", justify="right", style="bold yellow", width=8, no_wrap=True)
        tbl.add_column("Share Bar (Horizontal Proportion)", ratio=3, no_wrap=True)
        js_rows = db.get_js_executors(limit=6)
        max_js = max([int(c) for _, c in js_rows] or [1])
        for ua, cnt in js_rows:
            badge = "🛑" if "[SPOOFED-IP]" in ua else ("🔷" if "[VERIFIED]" in ua else "🟠")
            short_ua = ua.replace("[SPOOFED-IP] ", "").replace("[VERIFIED] ", "").replace("Mozilla/5.0 ", "")[:34]
            tbl.add_row(f"⚡ {badge} {short_ua}", f"{cnt:,}", _bar((cnt / max_js) * 100.0, 28, "yellow"))
        tbl.add_section()
        max_md = max([int(c) for _, c in cneg_rows[:6]] or [1])
        for ua, cnt in cneg_rows[:6]:
            badge = "🛑" if "[SPOOFED-IP]" in ua else ("🔷" if "[VERIFIED]" in ua else "🟠")
            short_ua = ua.replace("[SPOOFED-IP] ", "").replace("[VERIFIED] ", "").replace("Mozilla/5.0 ", "")[:34]
            color = "red" if badge == "🛑" else ("deep_sky_blue1" if badge == "🔷" else "cyan")
            tbl.add_row(f"🧠 {badge} {short_ua}", f"{cnt:,}", _bar((cnt / max_md) * 100.0, 28, color))
    elif mode == "rfc9421":
        title_str = "🔷 RFC 9421 WEB BOT AUTH SIGNERS & 🛑 UNMASKED IP CLOAKERS"
        tbl.add_column("Operator / Signature-Agent", style="bold white", ratio=4, no_wrap=True)
        tbl.add_column("Events", justify="right", style="bold deep_sky_blue1", width=8, no_wrap=True)
        tbl.add_column("Verification Telemetry", ratio=4, no_wrap=True)
        cur.execute(
            """
            SELECT s.value, ua.value, SUM(r.count) as total
            FROM rfc9421_logs r
            JOIN sig_agents s ON r.sig_id = s.id
            JOIN user_agents ua ON r.ua_id = ua.id
            GROUP BY s.id, ua.id
            ORDER BY total DESC
            LIMIT 8
            """
        )
        sig_rows = cur.fetchall()
        max_sig = max([int(r[2]) for r in sig_rows] or [1])
        for sig_val, ua_val, cnt in sig_rows:
            short_ua = ua_val.replace("Mozilla/5.0 ", "")[:26]
            tbl.add_row(f"🔷 {sig_val} ({short_ua})", f"{cnt:,}", _bar((cnt / max_sig) * 100.0, 28, "deep_sky_blue1"))
        tbl.add_section()
        tbl.add_row(
            "🛑 Unmasked Googlebot IP Cloakers",
            f"{spoof_md:,}",
            f"{_bar(spoof_pct, 28, 'red')} [bold red]{spoof_pct}%[/bold red]",
        )
        tbl.add_row(
            "🟠 Authentic Self-Asserted Markdown Bots",
            f"{total_cneg - spoof_md:,}",
            f"{_bar(auth_pct, 28, 'dark_orange')} [bold orange1]{auth_pct}%[/bold orange1]",
        )
    elif mode == "doors":
        title_str = "🎙️ THE 8-DOOR HONEYBOT FREQUENCY DIAL (CURL -fsSL <DOOR> | LESS)"
        tbl.add_column("Door / Frequency", style="bold bright_white", width=20)
        tbl.add_column("Target Folder", style="bold cyan", width=16)
        tbl.add_column("Focused Value Proposition (Saying More by Saying Less)", style="white", ratio=4)
        for d_name, d_tld, d_folder, d_pitch in DOOR_DIAL_ROWS:
            domain_str = f"{d_name}.{d_tld}"
            tbl.add_row(f"🚪 {domain_str}", d_folder, d_pitch)
    else:
        title_str = "🔭 WEB BOT AI OBSERVATORY — LIVE SQLITE WIRE TELEMETRY (MIKELEV.IN)"
        tbl.add_column("Web AI Standard Metric", style="bold white", ratio=3)
        tbl.add_column("Reading", justify="right", style="bold cyan", width=18)
        tbl.add_column("Horizontal Gauge", ratio=4)
        tbl.add_row(
            "1. RFC 9110 Markdown Horizon (0% → 20%)",
            f"{md_pct}% ({md_reads:,} .md)",
            f"{_bar(md_horizon_pct, 28, 'cyan')} [cyan]{md_horizon_pct}% of 20%[/cyan]",
        )
        tbl.add_row(
            "2a. ⚡ DOM Hydration Trapdoor (JS Execs)",
            f"{js_hits:,} ({js_share}%)",
            _bar(js_share, 28, "yellow"),
        )
        tbl.add_row(
            "2b. 🧠 RFC 9110 Raw Markdown Delivery",
            f"{md_reads:,} ({md_share}%)",
            _bar(md_share, 28, "cyan"),
        )
        tbl.add_row(
            "3. 🔷 RFC 9421 Web Bot Auth (Signed)",
            f"{sig_events:,} hits · {sig_clients} clients",
            _bar(min(100.0, sig_clients * 12.0), 28, "deep_sky_blue1"),
        )
        tbl.add_row(
            "4a. 🛑 Unmasked Cloakers (Spoofed IP)",
            f"{spoof_md:,} ({spoof_pct}%)",
            _bar(spoof_pct, 28, "red"),
        )
        tbl.add_row(
            "4b. 🟠 Authentic Self-Asserted Bot UAs",
            f"{total_cneg - spoof_md:,} ({auth_pct}%)",
            _bar(auth_pct, 28, "dark_orange"),
        )

    footer = Text.from_markup(
        "[bold green]💸 Spending $15,000/mo+ on HTML pre-render?[/bold green] "
        "RFC 9110, RFC 9111 & RFC 9421 save that spend -> [bold cyan]https://mikelev.in/#consulting[/bold cyan]"
    )
    return Panel(tbl, title=f"[bold bright_cyan]{title_str}[/bold bright_cyan]", subtitle=footer, padding=(1, 2))


def prerender_station_report_ansi(mode="overview", width=104, out_path=None):
    """Pre-render the station report to an ANSI file BEFORE Alacritty opens so frame 1 is populated."""
    import io
    from pathlib import Path
    from rich.console import Console
    safe_mode = "".join(c for c in str(mode or "overview") if c.isalnum() or c in ("_", "-")) or "overview"
    target = Path(out_path) if out_path else Path(f"/tmp/honeybot_report_{safe_mode}.ansi")
    buf = io.StringIO()
    panel = _build_station_report_panel(mode=safe_mode)
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=int(width))
    console.print(panel)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(buf.getvalue(), encoding="utf-8")
    tmp.replace(target)
    return str(target)


def render_station_report(mode="overview", hold_seconds=65.0):
    """Render a live Python Rich horizontal bar-chart report in an Alacritty overlay window."""
    import time
    from rich.console import Console
    panel = _build_station_report_panel(mode=mode)
    console = Console()
    console.clear()
    console.print(panel)
    time.sleep(max(1.0, float(hold_seconds)))


if __name__ == "__main__":
    import sys as _sys
    _mode = _sys.argv[1] if len(_sys.argv) > 1 else "overview"
    render_station_report(mode=_mode, hold_seconds=65.0)
