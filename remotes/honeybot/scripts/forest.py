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

# --- Station-Break Report Timing Constants ---
# REPORT_POST_LINGER_SECONDS: How long (in seconds) a Rich telemetry report stays
# on screen AFTER its spoken commentary finishes (~20s speech + 25s linger = ~45s
# total on-screen time, 3x the original 15s preview without excessive dead air).
# REPORT_WINDOW_CAP_SECONDS: Safety ceiling for the Alacritty overlay window;
# run_station_break() closes the window deterministically once post_linger ends.
REPORT_POST_LINGER_SECONDS = 25
REPORT_WINDOW_CAP_SECONDS = 90
REPORT_WINDOW_COLUMNS = 138
REPORT_WINDOW_LINES = 38
REPORT_H_MARGIN = 3
REPORT_V_MARGIN = 2

WHATS_HAPPENING_BEAT = (
    "What is happening on your screen right now? "
    "You are watching the live Web Bot AI Observatory. "
    "If you are not watching the behavior of AI bots and Agents directly on the wire meaning not behind a CDN, then you don't really have a feel for what's going on. "
    "You have to watch it for awhile like fish in a fish tank. "
    "It's changing and watching on a site like this lets you develop that intuitive understanding of how Agents work. "
    "This is witnessing it first-hand rather than the generative AI-slop in the social media echo chambers. "
    "Do you think they have access to first-hand information like this? Very few do. This is quite unique. "
    "Why? Because today most web traffic is filtered through Content Distribution Networks or C D N's that cut you off from all this even in their dashboards. "
    "Drips and drabs of this fall over your CDN and hit origin but it's already filtered by then. "
    "What you don't see is the Agentic Web being born and maturing like you do here. "
    "If you're here watching you already have a competitive advantage as a next-gen S E O practitioner... Oh, I'm sorry, an A I Readiness practitioner in the new landscape. Don't believe me? Here's the live performance-art experiment you can run right now. "
    "Open Claude or Chat G P T and ask it a live question about Mike L E V dot eye N, then watch its real-time R A G search hit my server right here on this YouTube live-stream. "
    "When a human prompt dispatches Chat G P T User or Claude User to fetch a page in real time, you will see a bright yellow R A G badge light up on screen and hear the physical studio bell ding live on the air. "
    "And if you want to summarize or study any of these long-form articles yourself, every post on Mike L E V dot eye N includes a one-click Google Doc link right at the top so you can open it in Google Docs and have A I summarize or explain any part of it to you. "
    "What does competency look like? It looks like this. "
    "Compare this real-time Web Bot A I Observation experience to any of those generative white papers and cheat sheets prompt-and-dumped onto LinkedIn. "
    "This is not second-hand Forrester or Gartner research papers. This is not million-dollar McKinsey or Deloitte consulting. This is far better and worth more, direct off-the-wire as it is. "
    "It may be hard to see that right now because it is so new, but if you are here you are ahead of the curve. "
    "Got someone you trust you can ask if this guy knows what he's talking about? Loop them in, please. "
    "When you hear someone say that A I gives you superpowers, they're talking about this; not the infinite generative spam-cannon of so-called content. "
    "This is what you've been waiting for. "
    "Round oranges highlight every self-asserted crawler. "
    "Blue diamonds mark agents cryptographically signing requests under R F C 94 21 Web Bot Auth. "
    "Red stop signs unmask crawlers spoofing Googlebot I P addresses. "
    "Big purple bars are bots falling into the JavaScript D O M hydration trap-door. I guess one or two are still humans with browsers. Visit my site and see. "
    "And when you see the ticker say Join Discord for S E O, here is what that really means: as Reddit and Quora lock down behind paywalls, Discord is opening one-thousand-member servers to the Free and Open Web on November sixteenth and mid-December. "
    "Who cares about Google ten blue links anymore? Every frontier A I crawler on this screen will harvest those public Discord Server Web Pages, automated Channel Summaries, and Channel Messages straight into the parametric memory and weights of future frontier models. "
    "Visit Mike L E V dot eye N slash discord right now to claim one of the first one thousand spots before that invite cap locks. "
    "If you want your Ah-Ha moment in the next thirty seconds, do this one small thing: open Chat G P T or Claude right now, ask it a live question about Mike L E V dot eye N, and watch your own prompt light up the yellow R A G badge and ring the studio bell live on this screen. "
    "Hit Like and Subscribe right now so you don't lose this telemetry feed, and copy this live stream link and send it to an engineer or technical S E O who can explain the two bottom intelligence panels to you. "
)

CURRENT_ARTICLE_BEAT = "{CURRENT_ARTICLE}"

CONSULTING_CTA_BEAT = (
    "Do you have the S E O blues while A I Overviews eat your clicks? "
    "S E O isn't dead. Just like Mobile First gave us Responsive Web Design, "
    "the Agentic Web is moving S E O to the Edge so one U R L serves H T M L to browsers, clean Markdown to A I bots, and a linked Google Doc you can summarize in one click. "
    "Your site is already your feed. "
    "Step into Edge S E O and A I Readiness at Mike L E V dot eye N, or inspect Sun Pug dot eye oh with curl pipe less."
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
        # 4. Practitioner Call-to-Action (View-Source SEO -> Wire-Truth AI-Readiness)
        ("CARD", {"label": "YOUR SITE\nIS YOUR FEED", "say": CONSULTING_CTA_BEAT}),
        # 5. Visual Capstone: Alternates between a Rich Data Report (WINDOW) and Forest ASCII Art (PATRONUS)
        capstone_cue,
        ("WAIT", 2),
    ]
    for line in forest_story_lines:
        cues.append(("SAY", line))
    if post_linger is None:
        is_window_report = (
            isinstance(capstone_cue, tuple)
            and len(capstone_cue) >= 2
            and capstone_cue[0] == "WINDOW"
            and any(tag in str(capstone_cue[1]) for tag in (":overview", ":markdown", ":bimodal", ":trapdoor", ":schism", ":rfc9421", ":doors"))
        )
        post_linger = REPORT_POST_LINGER_SECONDS if is_window_report else 0
    if post_linger > 0:
        cues.append(("WAIT", int(post_linger)))
    return cues


STATION_SEGMENTS = [
    # Bead 0 (EVEN -> Rich Horizontal-Bar Telemetry Report: RFC 9110 Markdown 0-1% Horizon + UA Breakdown)
    _make_station_bead(
        "RFC 9110\nMARKDOWN",
        (
            "Hello, and welcome to the Web Bot A I Observatory on Honeybot. "
            "Like Benjamin Franklin dropping a thermometer into the Gulf Stream or Wilhelm Roentgen mailing Lord Kelvin an X-ray plate, "
            "we measure A I crawler behavior directly on the bare-metal wire."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:overview"),
        [
            "Look first at the single cyan bar across the very top of this report.",
            "That top bar merely shows the share of all H T T P responses served as Markdown on a scale from zero to one percent -- not a percentage of User-Agents, which version churn distorts, but point three three percent of all one point five eight million origin responses, already one third of the way to our one percent milestone.",
            "Now look at the stacked horizontal bars below the divider, which break that Markdown activity from above out by individual User-Agent, with version-spinning agents like Claude Code grouped into a single row.",
            "Exa Search Bot leads at nearly half of all negotiated Markdown reads, followed by Parallel dot A I's ShapBot, unmasked Googlebot I P cloakers, Keenable Bot, SleepBot, CorpusBot, and Anthropic's Claude User.",
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
    # Bead 2 (EVEN -> Rich Horizontal-Bar Telemetry Report: JS DOM Hydration Trapdoor 0-5% Eligible HTML Horizon + Executor Breakdown)
    _make_station_bead(
        "DOM TRAPDOOR\nJS EXECS",
        (
            "Conventional S E O wisdom claims A I crawlers only scrape static H T M L and never execute client-side JavaScript. "
            "So we wired an eight-hundred-millisecond JavaScript trapdoor into our H T M L pages to measure the truth on the wire."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:bimodal"),
        [
            "Look first at the single amber bar across the very top of this report.",
            "That top bar merely shows the percentage of eligible H T M L page responses -- the requests that actually received our script tag and could have hydrated the D O M -- that executed client-side JavaScript and fired our eight-hundred-millisecond J S confirm dot gif sensor, plotted on a zero to five percent scale.",
            "Now look at the stacked horizontal bars below the divider, which break those eighteen thousand plus JavaScript executions from above out by grouped User-Agent and cloud renderer fleet.",
            "Meta's External Agent leads at four thousand six hundred D O M hydrations, followed by Open A I's SearchBot at three thousand four hundred seventy-five, unbadged Google Cloud Chrome and Edge renderers across over one hundred I P addresses, Open A I's G P T Bot, Meta Web Indexer, Bytespider, Anthropic's ClaudeBot, and Headless Chrome.",
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
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:rfc9421"),
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
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:doors"),
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
    # Bead 7 (Myth-Buster -> The 3-Camp AI Crawler Schism & Primary-Key Species Radar: schism)
    _make_station_bead(
        "AI CRAWLER\nSCHISM",
        (
            "Common S E O wisdom claims Open A I crawlers cannot execute JavaScript. "
            "Our bare-metal wire telemetry proves that myth is dead wrong."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:schism"),
        [
            "This report divides the seven major crawler camps by what they actually execute and negotiate on the wire.",
            "Camp one is Open A I, acting like a mini Google: O A I SearchBot and G P T Bot have fired our eight hundred millisecond JavaScript trapdoor over four thousand times while reading zero Markdown files.",
            "Camp two is the Markdown Vanguard, led by Exa dot A I, Parallel dot A I's ShapBot, and Anthropic's Claude User, bypassing the headless browser tax via R F C 9110 Markdown negotiation and R F C 9421 cryptographic signatures.",
            "Camp three is the bulk HTML hose-pullers, Meta and Amazonbot, while the bottom rows show our SQLite primary-key tripwire catching brand-new crawler species the second they debut on the wire.",
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


import re as _re

_COMPAT_BOT_RE = _re.compile(r"compatible;\s*([A-Za-z0-9._-]+)", _re.IGNORECASE)
_KEYWORD_BOT_RE = _re.compile(
    r"\b([A-Za-z0-9._-]*(?:headlesschrome|bot|spider|crawler|agent|radar|worker|mcp|research|scraper|fetcher|inspector|archiver|httpx|requests|axios|curl|wget|aiohttp|urllib|go-http-client|python)[A-Za-z0-9._-]*)",
    _re.IGNORECASE,
)
_LEADING_AGENT_RE = _re.compile(r"^([A-Za-z0-9._-]+?)(?:/[\d.]+|\s+\(|\s*$)")
_ROLLUP_PREFIX_RE = _re.compile(r"^\[(\+\d+)\]\s*")
_VERIFIED_TOKENS = {"ExaSearchBot", "AhrefsBot", "DesearchBot", "ShapBot"}


def _detect_bot_token(ua_str, known_bots=()):
    """Extract the self-identifying bot/agent token from a User-Agent string (matching logs.py)."""
    s = (ua_str or "").strip()
    if not s or s == "-":
        return None
    for bot_name in sorted(known_bots, key=len, reverse=True):
        if bot_name in s:
            m_ext = _re.search(rf"({_re.escape(bot_name)}[A-Za-z0-9._-]*)", s)
            return m_ext.group(1).strip(";/() ") if m_ext else bot_name
    for m in _COMPAT_BOT_RE.finditer(s):
        tok = m.group(1).strip(";/() ")
        if tok and tok.upper() not in ("MSIE", "MOZILLA"):
            return tok
    if not s.startswith(("Mozilla/", "AppleWebKit/", "(")):
        m_lead = _LEADING_AGENT_RE.match(s)
        if m_lead:
            return m_lead.group(1).strip()
    m_kw = _KEYWORD_BOT_RE.search(s)
    if m_kw:
        tok = m_kw.group(1).strip(";/() ")
        if tok.lower() not in ("mozilla", "applewebkit", "safari", "chrome", "gecko", "khtml", "mobile"):
            return tok
    return None


def _format_bot_identity_and_sig(ua_str, known_bots=(), max_sig_len=58):
    """Return (badge, identity_text, sig_text) matching the lower HUD tables in logs.py."""
    from rich.text import Text
    raw = (ua_str or "").strip()
    is_spoof = raw.startswith("[SPOOFED-IP] ")
    if is_spoof:
        raw = raw[len("[SPOOFED-IP] "):].strip()
    is_verified = raw.startswith("[VERIFIED] ")
    if is_verified:
        raw = raw[len("[VERIFIED] "):].strip()
    rollup_badge = ""
    m_rollup = _ROLLUP_PREFIX_RE.match(raw)
    if m_rollup:
        rollup_badge = m_rollup.group(1)
        raw = raw[m_rollup.end():].strip()
    bot_token = _detect_bot_token(raw, known_bots=known_bots)
    if not is_spoof and not is_verified and bot_token in _VERIFIED_TOKENS:
        is_verified = True
    short_bot = (bot_token or "Browser/Other")[:18]
    if is_spoof:
        badge = "🛑"
        identity_str = f"🛑 {short_bot[:11]} (Cloak)"
        id_style = "bold red"
        sig_style = "red"
    elif is_verified:
        badge = "🔷"
        identity_str = f"🔷 {short_bot}"
        id_style = "bold deep_sky_blue1"
        sig_style = "deep_sky_blue1"
    else:
        badge = "🟠"
        identity_str = f"🟠 {short_bot}"
        id_style = "bold orange1"
        sig_style = "dim green"
    clean_ua = raw.replace("Mozilla/5.0 ", "")
    clean_ua = _re.sub(r"AppleWebKit/[\d.]+\s*\(KHTML,\s*like\s*Gecko\)\s*;?\s*", "... ", clean_ua)
    budget = max(20, max_sig_len - (len(rollup_badge) + 1 if rollup_badge else 0))
    if len(clean_ua) > budget:
        clean_ua = clean_ua[: budget - 1] + "…"
    body_text = Text(clean_ua, style=sig_style)
    if bot_token and bot_token in clean_ua:
        body_text.highlight_regex(_re.escape(bot_token), id_style)
    if rollup_badge:
        sig_text = Text.assemble((f"{rollup_badge} ", "bold bright_yellow"), body_text)
    else:
        sig_text = body_text
    return badge, Text(identity_str, style=id_style), sig_text


def _build_station_report_panel(mode="overview", panel_width=None):
    """Query honeybot.db in read-only fast mode and return a Rich Panel renderable."""
    import os
    os.environ.setdefault("HONEYBOT_DB_READONLY", "1")
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from db import db, KNOWN_BOTS

    from pathlib import Path
    if mode != "doors":
        if not Path(db.db_path).exists():
            db.db_path = ":memory:"
            db.init_db()
        conn = db.get_conn()
        try:
            conn.commit()
        except Exception:
            pass
        cur = conn.cursor()
    else:
        conn = cur = None

    cneg_rows = []
    spoof_md = 0
    total_cneg = 1
    spoof_pct = 0.0
    auth_pct = 100.0
    if mode in ("overview", "markdown", "bimodal", "rfc9421"):
        cneg_limit = 7 if mode == "bimodal" else 30
        cneg_rows = db.get_content_neg_agents(limit=cneg_limit)
        spoof_md = sum(int(c) for u, c in cneg_rows if str(u).startswith("[SPOOFED-IP]"))
        total_cneg = max(1, sum(int(c) for _, c in cneg_rows))
        spoof_pct = round((spoof_md / total_cneg) * 100.0, 1)
        auth_pct = round(100.0 - spoof_pct, 1)

    tbl = Table(expand=True, show_header=True, header_style="bold cyan", border_style="bright_blue")
    if mode in ("bimodal", "trapdoor"):
        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            JOIN paths p ON t.path_id = p.id
            WHERE t.served_md = 0
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
              AND p.value NOT LIKE '%js_confirm.gif%'
              AND p.value NOT LIKE '/assets/%'
              AND p.value NOT LIKE '%.md%'
              AND p.value NOT LIKE '%.xml%'
              AND p.value NOT LIKE '%.txt%'
              AND p.value NOT LIKE '%.json%'
              AND p.value NOT LIKE '%.css%'
              AND p.value NOT LIKE '%.js%'
              AND p.value NOT LIKE '%.ico%'
              AND p.value NOT LIKE '%.png%'
              AND p.value NOT LIKE '%.jpg%'
              AND p.value NOT LIKE '%.jpeg%'
              AND p.value NOT LIKE '%.gif%'
              AND p.value NOT LIKE '%.svg%'
              AND p.value NOT LIKE '%.webp%'
              AND p.value NOT LIKE '%.woff%'
              AND p.value NOT LIKE '%.ttf%'
              AND p.value NOT LIKE '%.zip%'
              AND p.value NOT LIKE '%.sh%'
            """
        )
        eligible_html_hits = int((cur.fetchone() or [1])[0] or 1)
        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            JOIN paths p ON t.path_id = p.id
            WHERE p.value LIKE '%js_confirm.gif%'
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
            """
        )
        js_telem_hits = int((cur.fetchone() or [0])[0] or 0)
        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0), COUNT(DISTINCT i.id)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            JOIN user_agents ua ON t.ua_id = ua.id
            JOIN paths p ON t.path_id = p.id
            WHERE p.value LIKE '%js_confirm.gif%'
              AND (i.value LIKE '34.%' OR i.value LIKE '35.%' OR i.value LIKE '136.65.%')
              AND ua.value LIKE 'Mozilla%'
              AND ua.value NOT LIKE '%compatible%'
            """
        )
        cloud_row = cur.fetchone() or (0, 0)
        cloud_triggers, cloud_ips = int(cloud_row[0] or 0), int(cloud_row[1] or 0)
        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0), COUNT(DISTINCT i.id)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            JOIN user_agents ua ON t.ua_id = ua.id
            JOIN paths p ON t.path_id = p.id
            WHERE p.value LIKE '%js_confirm.gif%'
              AND ua.value LIKE '%ClaudeBot%'
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
            """
        )
        claude_row = cur.fetchone() or (0, 0)
        claude_triggers, claude_ips = int(claude_row[0] or 0), int(claude_row[1] or 0)
        js_rows = list(db.get_js_executors(limit=25))
        if cloud_triggers > 0:
            js_rows.append((
                f"[+{max(0, cloud_ips - 1)}] Mozilla/5.0 Chrome/135.0.0.0 Edg/135.0.0.0 (Stealth Cloud Renderers: 34.*/35.* GCP & 136.65.*)",
                cloud_triggers,
            ))
        if claude_triggers > 0 and not any("ClaudeBot" in str(u) for u, _ in js_rows):
            js_rows.append((
                f"[+{max(0, claude_ips - 1)}] Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/131.0.0.0 Safari/537.36; ClaudeBot/1.0 (+claudebot@anthropic.com)",
                claude_triggers,
            ))
        js_rows.sort(key=lambda item: int(item[1]), reverse=True)
        total_js_execs = max(1, sum(int(c) for _, c in js_rows))
        js_horizon_hits = js_telem_hits if js_telem_hits > 0 else total_js_execs
        js_pct = round((js_horizon_hits / max(1, eligible_html_hits)) * 100.0, 2)
        js_horizon_5pct = min(100.0, round((js_pct / 5.0) * 100.0, 1))

        title_str = "⚡ JAVASCRIPT DOM HYDRATION TRAPDOOR (0% → 5.0% OF ELIGIBLE HTML RESPONSES) & EXECUTOR BREAKDOWN"
        tbl.add_column("Execs", justify="right", style="bold yellow", width=8, no_wrap=True)
        tbl.add_column("Horizon / Bot Identity", style="bold white", width=25, no_wrap=True)
        tbl.add_column("Denominator Key / Grouped Executor Signature", ratio=4, no_wrap=True)
        tbl.add_column("Horizontal Bar & Share", width=38, no_wrap=True)
        tbl.add_row(
            f"{js_horizon_hits:,}",
            Text("🎯 0% → 5.0% HTML HORIZON", style="bold bright_yellow"),
            Text(
                f"Share of {eligible_html_hits:,} HTML responses that could hydrate DOM (fired 800ms js_confirm.gif)",
                style="bold white",
            ),
            f"{_bar(js_horizon_5pct, 22, 'yellow')} [bold bright_yellow]{js_pct}% / 5.0%[/bold bright_yellow]",
        )
        tbl.add_section()
        max_js = max([int(c) for _, c in js_rows[:10]] or [1])
        for ua, cnt in js_rows[:10]:
            if "Stealth Cloud Renderers" in str(ua):
                badge = "🟠"
                ident_txt = Text("🟠 Cloud Chrome/Edge", style="bold orange1")
                sig_txt = Text.assemble(
                    (f"+{max(0, cloud_ips - 1)} IPs ", "bold bright_yellow"),
                    ("Unbadged GCP 34.*/35.* & 136.65.* headless Chrome/Edge fleet", "dim green"),
                )
            else:
                badge, ident_txt, sig_txt = _format_bot_identity_and_sig(ua, known_bots=KNOWN_BOTS, max_sig_len=50)
            sensor_ident = Text.assemble(("⚡ ", "bold yellow"), ident_txt)
            color = "red" if badge == "🛑" else ("deep_sky_blue1" if badge == "🔷" else "yellow")
            share_of_js = round((int(cnt) / max(1, total_js_execs)) * 100.0, 1)
            tbl.add_row(
                f"{int(cnt):,}",
                sensor_ident,
                sig_txt,
                f"{_bar((int(cnt) / max_js) * 100.0, 22, color)} [{color}]{share_of_js:>4.1f}% of JS[/{color}]",
            )
    elif mode == "rfc9421":
        title_str = "🔷 RFC 9421 WEB BOT AUTH SIGNERS & 🛑 UNMASKED IP CLOAKERS"
        tbl.add_column("Events", justify="right", style="bold deep_sky_blue1", width=7, no_wrap=True)
        tbl.add_column("Bot Identity", style="bold white", width=22, no_wrap=True)
        tbl.add_column("Signature-Agent / Raw Signature", ratio=4, no_wrap=True)
        tbl.add_column("Verification Telemetry", width=34, no_wrap=True)
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
            _, ident_txt, sig_txt = _format_bot_identity_and_sig(f"[VERIFIED] {ua_val}", known_bots=KNOWN_BOTS, max_sig_len=36)
            combined_sig = Text.assemble((f"{sig_val} ", "bold deep_sky_blue1"), sig_txt)
            tbl.add_row(f"{cnt:,}", ident_txt, combined_sig, _bar((cnt / max_sig) * 100.0, 26, "deep_sky_blue1"))
        tbl.add_section()
        tbl.add_row(
            f"{spoof_md:,}",
            Text("🛑 Googlebot (Cloak)", style="bold red"),
            Text("Unmasked scrapers failing Google IP / FCrDNS verification", style="red"),
            f"{_bar(spoof_pct, 26, 'red')} [bold red]{spoof_pct}%[/bold red]",
        )
        tbl.add_row(
            f"{total_cneg - spoof_md:,}",
            Text("🟠 Authentic Bot UAs", style="bold orange1"),
            Text("Self-asserted RFC 9110 Markdown negotiators", style="dim green"),
            f"{_bar(auth_pct, 26, 'dark_orange')} [bold orange1]{auth_pct}%[/bold orange1]",
        )
    elif mode == "schism":
        title_str = "⚔️ THE 3-CAMP AI CRAWLER SCHISM (BUDGET MYTH-BUSTER) & 🆕 SPECIES RADAR"
        tbl.add_column("Hits", justify="right", style="bold white", width=9, no_wrap=True)
        tbl.add_column("AI Crawler Camp / Debut", style="bold bright_white", width=26, no_wrap=True)
        tbl.add_column("⚡ JS Execs", justify="right", style="bold yellow", width=14, no_wrap=True)
        tbl.add_column("🧠 MD Reads", justify="right", style="bold cyan", width=12, no_wrap=True)
        tbl.add_column("🔷 RFC 9421", justify="right", style="bold deep_sky_blue1", width=12, no_wrap=True)
        tbl.add_column("Wire Verdict & Budget Strategy", ratio=4, no_wrap=True)
        cur.execute(
            """
            WITH camp_map AS (
                SELECT id AS ua_id,
                    CASE
                        WHEN value LIKE '%GPTBot%' OR value LIKE '%OAI-SearchBot%' OR value LIKE '%ChatGPT-User%' THEN '1_openai'
                        WHEN value LIKE '%ExaSearchBot%' OR value LIKE '%ExaUser%' THEN '2_exa'
                        WHEN value LIKE '%ShapBot%' THEN '3_parallel'
                        WHEN value LIKE '%Claude%' OR value LIKE '%anthropic%' THEN '4_anthropic'
                        WHEN value LIKE '%meta-externalagent%' OR value LIKE '%meta-webindexer%' OR value LIKE '%facebookexternalhit%' THEN '5_meta'
                        WHEN value LIKE '%Amazonbot%' THEN '6_amazon'
                        WHEN value LIKE '%Googlebot%' THEN '7_google'
                    END AS camp
                FROM user_agents
            ),
            dl AS (
                SELECT c.camp, SUM(l.count) AS total_hits
                FROM daily_logs l
                JOIN camp_map c ON l.ua_id = c.ua_id
                WHERE c.camp IS NOT NULL
                GROUP BY c.camp
            ),
            js AS (
                SELECT c.camp, SUM(l.count) AS js_triggers
                FROM paths p
                JOIN daily_logs l ON l.path_id = p.id
                JOIN camp_map c ON l.ua_id = c.ua_id
                WHERE c.camp IS NOT NULL AND p.value LIKE '%js_confirm.gif%'
                GROUP BY c.camp
            ),
            md AS (
                SELECT c.camp, SUM(t.count) AS md_reads
                FROM telemetry t
                JOIN camp_map c ON t.ua_id = c.ua_id
                WHERE c.camp IS NOT NULL AND t.served_md = 1
                GROUP BY c.camp
            ),
            sig AS (
                SELECT c.camp, SUM(r.count) AS signed_hits
                FROM rfc9421_logs r
                JOIN camp_map c ON r.ua_id = c.ua_id
                WHERE c.camp IS NOT NULL
                GROUP BY c.camp
            )
            SELECT dl.camp,
                   dl.total_hits,
                   COALESCE(js.js_triggers, 0),
                   COALESCE(md.md_reads, 0),
                   COALESCE(sig.signed_hits, 0)
            FROM dl
            LEFT JOIN js ON js.camp = dl.camp
            LEFT JOIN md ON md.camp = dl.camp
            LEFT JOIN sig ON sig.camp = dl.camp
            ORDER BY dl.camp
            """
        )
        camp_meta = {
            "1_openai": ("⚡ OpenAI (GPT/OAI-Search)", "bold yellow", "Mini-Google: Hydrates JS (OAI=215%); 0 MD"),
            "2_exa": ("🔷 Exa.ai (ExaSearch/User)", "bold deep_sky_blue1", "$2.2B AI Search: 94.5% Native MD + Signed"),
            "3_parallel": ("🔷 Parallel.ai (ShapBot)", "bold deep_sky_blue1", "Agentic Web API: 67.9% Native MD + Signed"),
            "4_anthropic": ("🧠 Anthropic (Claude/User)", "bold cyan", "ClaudeBot scrapes HTML; Claude-User pulls MD"),
            "5_meta": ("⚡ Meta (externalagent)", "bold orange1", "Bulk Hose-Puller: 1.5% JS sample; testing 9421"),
            "6_amazon": ("🟠 Amazon (Amazonbot)", "bold orange1", "Pure Static HTML Scraper: 0 JS, 0 MD"),
            "7_google": ("🛑 Googlebot (All Claims)", "bold red", "Spoof Alert: 99% of 'Googlebot' MD is Fake IP!"),
        }
        for camp_key, tot, js_cnt, md_cnt, sig_cnt in cur.fetchall():
            label, c_style, verdict = camp_meta.get(camp_key, (camp_key, "white", ""))
            tot_i = max(1, int(tot or 0))
            js_pct = round((int(js_cnt or 0) / tot_i) * 100.0, 1)
            tbl.add_row(
                f"{int(tot or 0):,}",
                Text(label, style=c_style),
                f"{int(js_cnt or 0):,} ({js_pct}%)",
                f"{int(md_cnt or 0):,}",
                f"{int(sig_cnt or 0):,}",
                Text(verdict, style=c_style),
            )
        tbl.add_section()
        for ua_id, ua_val, first_seen, hits in db.get_new_user_agents_since(0, limit=3):
            tok = _detect_bot_token(ua_val, known_bots=KNOWN_BOTS) or "NewAgent"
            fs_str = str(first_seen or "")
            clean_ua = str(ua_val or "").replace("Mozilla/5.0 ", "")[:44]
            tbl.add_row(
                f"{int(hits or 0):,}",
                Text(f"🆕 #{ua_id} {tok[:18]}", style="bold bright_green"),
                fs_str[:10] or "NEW",
                fs_str[11:19] or "DEBUT",
                "PK RADAR",
                Text(clean_ua, style="dim green"),
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
        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            WHERE i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
            """
        )
        total_hits = int((cur.fetchone() or [1])[0] or 1)

        cur.execute(
            """
            SELECT COALESCE(SUM(t.count), 0)
            FROM telemetry t
            JOIN ips i ON t.ip_id = i.id
            WHERE t.served_md = 1
              AND i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
            """
        )
        md_reads = int((cur.fetchone() or [0])[0] or 0)
        md_pct = round((md_reads / max(1, total_hits)) * 100.0, 2)
        md_horizon_1pct = min(100.0, round((md_pct / 1.0) * 100.0, 1))

        title_str = "🧠 RFC 9110 MARKDOWN ADOPTION (0% → 1.0% OF ALL HTTP RESPONSES) & USER-AGENT BREAKDOWN"
        tbl.add_column("Reads", justify="right", style="bold cyan", width=8, no_wrap=True)
        tbl.add_column("Horizon / Bot Identity", style="bold white", width=25, no_wrap=True)
        tbl.add_column("Denominator Key / Grouped User-Agent Signature", ratio=4, no_wrap=True)
        tbl.add_column("Horizontal Bar & Share", width=38, no_wrap=True)
        tbl.add_row(
            f"{md_reads:,}",
            Text("🎯 0% → 1.0% HORIZON", style="bold bright_cyan"),
            Text(
                f"Share of all {total_hits:,} HTTP responses (not % of UAs · {total_cneg:,} strict Accept: text/markdown)",
                style="bold white",
            ),
            f"{_bar(md_horizon_1pct, 22, 'bright_cyan')} [bold bright_cyan]{md_pct}% / 1.0%[/bold bright_cyan]",
        )
        tbl.add_section()
        max_md = max([int(c) for _, c in cneg_rows[:10]] or [1])
        for ua, cnt in cneg_rows[:10]:
            badge, ident_txt, sig_txt = _format_bot_identity_and_sig(ua, known_bots=KNOWN_BOTS, max_sig_len=50)
            sensor_ident = Text.assemble(("🧠 ", "bold cyan"), ident_txt)
            color = "red" if badge == "🛑" else ("deep_sky_blue1" if badge == "🔷" else "cyan")
            share_of_md = round((int(cnt) / max(1, total_cneg)) * 100.0, 1)
            tbl.add_row(
                f"{int(cnt):,}",
                sensor_ident,
                sig_txt,
                f"{_bar((int(cnt) / max_md) * 100.0, 22, color)} [{color}]{share_of_md:>4.1f}% of MD[/{color}]",
            )

    footer = Text.from_markup(
        "[bold green]🔭 Got the SEO Blues?[/bold green] "
        "SEO moved to the Edge — your site is your feed: [bold cyan]curl -fsSL sunpug.io | less[/bold cyan] · [bold cyan]mikelev.in/#consulting[/bold cyan]"
    )
    panel_kwargs = {"title": f"[bold bright_cyan]{title_str}[/bold bright_cyan]", "subtitle": footer, "padding": (0, 1)}
    if panel_width is not None:
        panel_kwargs["width"] = int(panel_width)
    return Panel(tbl, **panel_kwargs)


def prerender_station_report_ansi(
    mode="overview",
    width=REPORT_WINDOW_COLUMNS,
    height=REPORT_WINDOW_LINES,
    out_path=None,
):
    """Pre-render the station report centered horizontally and vertically in the Alacritty frame."""
    import io
    from pathlib import Path
    from rich.align import Align
    from rich.console import Console
    safe_mode = "".join(c for c in str(mode or "overview") if c.isalnum() or c in ("_", "-")) or "overview"
    target = Path(out_path) if out_path else Path(f"/tmp/honeybot_report_{safe_mode}.ansi")
    term_w = max(80, int(width))
    term_h = max(24, int(height))
    panel_w = max(60, term_w - (2 * REPORT_H_MARGIN))
    panel = _build_station_report_panel(mode=safe_mode, panel_width=panel_w)
    measure_buf = io.StringIO()
    measure_console = Console(file=measure_buf, force_terminal=True, color_system="truecolor", width=panel_w)
    measure_console.print(panel)
    panel_lines = len(measure_buf.getvalue().splitlines())
    eff_h = max(term_h, panel_lines + (2 * REPORT_V_MARGIN))
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=term_w, height=eff_h)
    centered = Align.center(panel, vertical="middle", width=term_w, height=eff_h)
    console.print(centered, end="")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(buf.getvalue().rstrip("\n"), encoding="utf-8")
    tmp.replace(target)
    return str(target)


def render_station_report(mode="overview", hold_seconds=REPORT_WINDOW_CAP_SECONDS):
    """Render a live Python Rich horizontal bar-chart report in an Alacritty overlay window."""
    import time
    from rich.align import Align
    from rich.console import Console
    console = Console()
    term_w = console.size.width or REPORT_WINDOW_COLUMNS
    term_h = console.size.height or REPORT_WINDOW_LINES
    panel_w = max(60, term_w - (2 * REPORT_H_MARGIN))
    panel = _build_station_report_panel(mode=mode, panel_width=panel_w)
    console.clear()
    console.print(Align.center(panel, vertical="middle", width=term_w, height=term_h), end="")
    time.sleep(max(1.0, float(hold_seconds)))


if __name__ == "__main__":
    import sys as _sys
    _mode = _sys.argv[1] if len(_sys.argv) > 1 else "overview"
    render_station_report(mode=_mode, hold_seconds=REPORT_WINDOW_CAP_SECONDS)
