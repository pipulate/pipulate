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
PATRONUS_POST_LINGER_SECONDS = 8
REPORT_WINDOW_CAP_SECONDS = 90
REPORT_WINDOW_COLUMNS = 138
REPORT_WINDOW_LINES = 38
REPORT_H_MARGIN = 3
REPORT_V_MARGIN = 2

WHATS_HAPPENING_BEAT = (
    "You are watching the live Web Bot AI Observatory on bare metal — not filtered behind a CDN. "
    "Watching AI crawlers and agents directly on the wire like fish in an aquarium builds an intuition you will never get from social media echo chambers. "
    "Want your thirty-second ah-ha moment right now? Open ChatGPT or Claude and ask it a live question about mikelev.in. "
    "When your prompt dispatches a live retrieval agent, a yellow RAG badge lights up on screen and rings the physical studio bell on the air. "
    "Get your screenshot key ready for the wire-truth proof coming right up, forward this live feed to one sharp builder who needs to see it, "
    "and join our Founding 1,000 practitioners at mikelev.in/discord."
)

CURRENT_ARTICLE_BEAT = "{CURRENT_ARTICLE}"

CONSULTING_CTA_BEAT = (
    "Got the SEO blues while AI Overviews eat your clicks and vendors pitch $10K/mo JavaScript pre-render taxes? "
    "SEO moved to the Edge: one URL serving HTML to humans and clean RFC 9110 Markdown to AI agents, cached cleanly via RFC 9111 Vary Accept. "
    "Grab your own free Sun Pug and 911 LLM Optics right now at SunPug.io, RFC9110.org, or RFC9111.io — "
    "and rally with fellow AI-Readiness Consultants on Discord at mikelev.in/discord."
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
    is_window_report = (
        isinstance(capstone_cue, tuple)
        and len(capstone_cue) >= 2
        and capstone_cue[0] == "WINDOW"
        and any(tag in str(capstone_cue[1]) for tag in (":overview", ":markdown", ":bimodal", ":trapdoor", ":schism", ":rfc9421", ":doors", ":pirates"))
    )
    is_patronus_art = (
        isinstance(capstone_cue, tuple)
        and len(capstone_cue) >= 2
        and capstone_cue[0] == "PATRONUS"
    )
    if is_window_report:
        cues.append((
            "SAY",
            "This is the moment — take your screenshot right now! Both MikeLev.in and SunPug.io are stamped right on the report frame so you have the links.",
        ))
    for line in forest_story_lines:
        cues.append(("SAY", line))
    if post_linger is None:
        post_linger = REPORT_POST_LINGER_SECONDS if is_window_report else (PATRONUS_POST_LINGER_SECONDS if is_patronus_art else 0)
    if post_linger > 0:
        cues.append(("WAIT", int(post_linger)))
    return cues


# --- ACTIVE LINEAR-ARC STATION SEGMENTS ---
# Paired with score.py's OVERTURE (Beat 1) and MIDPOINT INTERMISSION (Beat 4):
#   Beat 1 (0%)   : OVERTURE — Around-the-HUDs stage & cast introduction
#   Beat 2 (+7m)  : Bead 0 — RFC 9110 MARKDOWN (:overview data proof + 911 LLM Optics teaser)
#   Beat 3 (+14m) : Bead 1 — 911 LLM OPTICS (FOSS "Screaming Frog for the Age of AI" live showcase @ SunPug.io)
#   Beat 4 (50%)  : MIDPOINT INTERMISSION — Around-the-HUDs stage & cast refresh
#   Beat 5a (+7m) : Bead 2 — DOM TRAPDOOR JS EXECS (:bimodal JS hydration proof)
#   Beat 5b (+14m): Bead 3 — SEOS ASSEMBLE! (white_rabbit -> RFC 9110/9111 Edge readiness @ SunPug.io)
STATION_SEGMENTS = [
    # Bead 0 (Beat 2 -> First Data Proof: Who Accepts Markdown on the Wire + Teaser for 911 LLM Optics)
    _make_station_bead(
        "RFC 9110\nMARKDOWN",
        (
            "Welcome to the Web Bot AI Observatory. "
            "Like Benjamin Franklin dropping a thermometer into the Gulf Stream, "
            "we measure which AI agents negotiate clean Markdown directly on the bare-metal wire."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:overview"),
        [
            "{LIVE_REPORT:overview}",
            "Coming up on our next station break, we open 911 LLM Optics — our free, open-source Screaming Frog for the Age of AI at SunPug.io — to X-ray raw HTTP headers, hydrated DOM bloat, and RFC 9110 Markdown readiness side by side.",
        ],
    ),
    # Bead 1 (Beat 3 -> Killer-App Payoff Promoted Ahead of White Rabbit: 911 LLM Optics @ SunPug.io)
    [
        (
            "CARD",
            {
                "label": "911 LLM\nOPTICS",
                "say": (
                    "Meet 911 LLM Optics: the FOSS Screaming Frog for the Age of AI, "
                    "built to inspect exact wire truth inside the portable workshop at SunPug.io."
                ),
            },
        ),
        ("OPTICS_SLOT", {"handshake_wait": 20.0, "claim_grace": 35.0, "timeout": 180.0}),
        ("SAY", CURRENT_ARTICLE_BEAT),
        ("CARD", {"label": "TRY SUNPUG.IO\n911 OPTICS", "say": CONSULTING_CTA_BEAT}),
    ],
    # Bead 2 (Beat 5a -> Second Data Proof: JavaScript DOM Hydration Trapdoor)
    _make_station_bead(
        "DOM TRAPDOOR\nJS EXECS",
        (
            "Conventional SEO wisdom claims AI crawlers never execute client-side JavaScript. "
            "So we wired an eight-hundred-millisecond JavaScript trapdoor into our HTML pages to measure the truth on the wire."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:bimodal"),
        [
            "{LIVE_REPORT:bimodal}",
            "When OpenAI and Meta already hydrate JavaScript on their own dime and Markdown-native agents ask for text/markdown directly, $10K/mo pre-render middleware becomes pure dead weight.",
        ],
    ),
    # Bead 3 (Beat 5b -> Follow the White Rabbit: "SEOs Assemble!" RFC 9110/9111 Edge Manifesto)
    _make_station_bead(
        "SEOS\nASSEMBLE!",
        (
            "Follow the White Rabbit. SEOs, assemble! "
            "Google is locking down the SERPs, and we are gathering the sharpest practitioners in the world "
            "who are ready to become real AI-Readiness Consultants."
        ),
        ("PATRONUS", {"key": "white_rabbit", "duration": 65.0}),
        [
            "For years, enterprise teams paid a $10K/mo JavaScript pre-render tax just to spoon-feed bloated HTML snapshots to search crawlers.",
            "Roy Fielding and Mark Nottingham already wired the cure into HTTP: RFC 9110 content negotiation and RFC 9111 Vary Accept caching let your existing CDN serve HTML to humans and clean Markdown to AI agents from one URL with zero SaaS rent.",
            "Grab your own Sun Pug free at SunPug.io, tell one colleague there is real engineering life after GEO doorway-page slop, and join the Founding 1,000 on Discord at mikelev.in/discord.",
        ],
    ),
]

# --- MODULAR STORYTELLING VAULT (INACTIVE IN AUTONOMOUS ROTATION, ON-DEMAND VIA `--bead <key>`) ---
# Preserved intact so no Patronus or Rich telemetry piece is ever buried in git history.
# Summon any archived bead live with: `ytapp tiktok`, `ytapp pachinko`, `ytapp pirates`, etc.
ARCHIVED_STATION_BEADS = {
    "ai_pachinko": _make_station_bead(
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
    "mechanical_man": _make_station_bead(
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
    "rfc9421": _make_station_bead(
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
    "doors": _make_station_bead(
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
    "schism": _make_station_bead(
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
    "pirates": _make_station_bead(
        "CT LOG\nPIRATES",
        (
            "The moment you mint a fresh Let's Encrypt T L S certificate, automated script-kiddie scanners watching the public Certificate Transparency logs pounce on the new domain within seconds."
        ),
        ("WINDOW", f"forest.py:{REPORT_WINDOW_CAP_SECONDS}:pirates"),
        [
            "Look at the crimson horizontal bars on this Intrusion Detection report.",
            "Every time we bring a new domain door online, like L P V G dot org or Sun Pug dot eye oh, bots tailing the A C M E certificate stream immediately probe for WordPress logins, dot E N V secrets, and P H P shells hoping to catch an unconfigured server before default passwords are changed.",
            "Because this is a declarative Nix O S appliance serving static representations and an S Q Lite telemetry ledger, there is no P H P runtime or admin login to breach -- every exploit probe simply unmasks the attacker's I P address on the live broadcast and records their exact fingerprint for instant Engine X filtering.",
        ],
    ),
}

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


_SPOKEN_BOT_NAMES = {
    "meta-externalagent": "Meta's External Agent",
    "meta-webindexer": "Meta Web Indexer",
    "oai-searchbot": "Open A I's SearchBot",
    "gptbot": "Open A I's G P T Bot",
    "chatgpt-user": "Chat G P T User",
    "exasearchbot": "Exa Search Bot",
    "exauser": "Exa User",
    "shapbot": "Parallel dot A I's ShapBot",
    "claudebot": "Anthropic's ClaudeBot",
    "claude-user": "Anthropic's Claude User",
    "claude-code": "Anthropic's Claude Code",
    "keenablebot": "Keenable Bot",
    "googlebot": "unmasked Googlebot I P cloakers",
    "headlesschrome": "Headless Chrome",
    "bytespider": "Bytespider",
    "amazonbot": "Amazonbot",
}


def _spoken_bot_label(raw_ua: str, known_bots=()) -> str:
    """Convert a raw or rolled-up User-Agent row into a clean TTS-friendly bot name."""
    s = str(raw_ua or "").strip()
    if "Stealth Cloud Renderers" in s:
        return "unbadged Google Cloud Chrome and Edge renderers"
    is_spoof = s.startswith("[SPOOFED-IP] ")
    for pfx in ("[SPOOFED-IP] ", "[VERIFIED] "):
        if s.startswith(pfx):
            s = s[len(pfx):].strip()
    s = _ROLLUP_PREFIX_RE.sub("", s).strip()
    tok = _detect_bot_token(s, known_bots=known_bots) or "Browser Agent"
    low = tok.lower()
    if is_spoof and "googlebot" in low:
        return "unmasked Googlebot I P cloakers"
    if low in _SPOKEN_BOT_NAMES:
        return _SPOKEN_BOT_NAMES[low]
    return tok.replace("-", " ").replace("_", " ")


_REPORT_META_TTL_SEC = 90.0


def _approx_count_words(n: int) -> str:
    """Round counts UP with 'about' so spoken narration stays natural and resilient to live-stream ticks."""
    import math
    val = max(0, int(n or 0))
    if val == 0:
        return "0"
    if val < 20:
        return f"about {val}"
    if val < 100:
        return f"about {int(math.ceil(val / 5.0) * 5)}"
    if val < 1_000:
        return f"about {int(math.ceil(val / 10.0) * 10):,}"
    if val < 10_000:
        return f"about {int(math.ceil(val / 100.0) * 100):,}"
    if val < 1_000_000:
        return f"about {int(math.ceil(val / 1000.0) * 1000):,}"
    return f"about {math.ceil((val / 1_000_000.0) * 10.0) / 10.0:.1f} million"


def _approx_pct_words(pct: float, whole_above: float = 10.0) -> str:
    """Round percentages UP behind 'about' so the last decimal never fights the visual chart."""
    import math
    p = max(0.0, float(pct or 0.0))
    if p == 0.0:
        return "0 percent"
    if p >= whole_above:
        return f"about {int(math.ceil(p))} percent"
    return f"about {math.ceil(p * 10.0) / 10.0:.1f} percent"


def _write_report_speech_snapshot(mode: str, payload: dict) -> None:
    import json
    import os
    import time
    from pathlib import Path
    safe = "".join(c for c in str(mode or "overview") if c.isalnum() or c in ("_", "-")) or "overview"
    p = Path(f"/tmp/honeybot_report_{safe}.meta.json")
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    data = dict(payload or {})
    data["updated_at"] = round(time.time(), 3)
    try:
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, p)
    except Exception:
        pass


def _read_report_speech_snapshot(mode: str, max_age: float = _REPORT_META_TTL_SEC):
    import json
    import time
    from pathlib import Path
    safe = "".join(c for c in str(mode or "overview") if c.isalnum() or c in ("_", "-")) or "overview"
    p = Path(f"/tmp/honeybot_report_{safe}.meta.json")
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if (time.time() - float(data.get("updated_at") or 0.0)) > max_age:
            return None
        return data
    except Exception:
        return None


def _format_overview_speech(total_hits: int, md_reads: int, total_cneg: int, md_pct: float, top_bots: list) -> str:
    top_parts = []
    for bname, cnt, share in top_bots[:4]:
        top_parts.append(f"{bname} with {_approx_count_words(cnt)} reads, or {_approx_pct_words(share)}")
    leaders_str = ", followed by ".join(top_parts[:2])
    if len(top_parts) > 2:
        leaders_str += ", and " + ", ".join(top_parts[2:])
    return (
        "Look first at the single cyan bar across the very top of this report. "
        "That top bar shows the live share of all H T T P responses served as Markdown on a scale from zero to one percent: "
        f"currently {_approx_pct_words(md_pct)} across {_approx_count_words(total_hits)} total origin responses, "
        f"with {_approx_count_words(md_reads)} total Markdown deliveries and {_approx_count_words(total_cneg)} strict R F C 9110 Accept text slash markdown negotiations. "
        "Now look at the stacked horizontal bars below the divider, which break that Markdown activity out by grouped User-Agent: "
        f"{leaders_str}."
    )


def _format_bimodal_speech(eligible_html: int, js_horizon_hits: int, js_pct: float, top_bots: list) -> str:
    top_js = []
    for bname, cnt, share in top_bots[:4]:
        top_js.append(f"{bname} at {_approx_count_words(cnt)} D O M hydrations, or {_approx_pct_words(share)} of J S")
    leaders_js = ", followed by ".join(top_js[:2])
    if len(top_js) > 2:
        leaders_js += ", and " + ", ".join(top_js[2:])
    return (
        "Look first at the single amber bar across the very top of this report. "
        "That top bar shows the live percentage of eligible H T M L page responses that executed client-side JavaScript and fired our eight-hundred-millisecond J S confirm dot gif sensor: "
        f"currently {_approx_pct_words(js_pct)} across {_approx_count_words(eligible_html)} eligible H T M L responses, "
        f"with {_approx_count_words(js_horizon_hits)} total trapdoor executions on our zero to five percent scale. "
        "Now look at the stacked horizontal bars below the divider, which break those live JavaScript executions out by grouped User-Agent and cloud renderer fleet: "
        f"{leaders_js}."
    )


def resolve_dynamic_report_speech(text: str) -> str:
    """Replace {LIVE_REPORT:overview} or {LIVE_REPORT:bimodal} using the chart's own snapshot + 'about' upward rounding."""
    s = str(text or "")
    if "{LIVE_REPORT:" not in s:
        return s
    import os
    from pathlib import Path
    os.environ.setdefault("HONEYBOT_DB_READONLY", "1")
    try:
        from db import db, KNOWN_BOTS
        if not Path(db.db_path).exists():
            db.db_path = ":memory:"
            db.init_db()
        conn = db.get_conn()
        try:
            conn.commit()
        except Exception:
            pass
        cur = conn.cursor()
    except Exception:
        cur = None
        KNOWN_BOTS = ()

    if "{LIVE_REPORT:overview}" in s:
        try:
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
            total_hits = int((cur.fetchone() or [0])[0] or 0)
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
            snap_ov = _read_report_speech_snapshot("overview")
            if snap_ov and snap_ov.get("top_bots"):
                live_ov = _format_overview_speech(
                    int(snap_ov["total_hits"]),
                    int(snap_ov["md_reads"]),
                    int(snap_ov["total_cneg"]),
                    float(snap_ov["md_pct"]),
                    snap_ov["top_bots"],
                )
            else:
                cneg_rows = db.get_content_neg_agents(limit=30)
                total_cneg = max(1, sum(int(c) for _, c in cneg_rows))
                if total_hits > 0 and cneg_rows:
                    md_pct = round((md_reads / max(1, total_hits)) * 100.0, 2)
                    top_bots = [
                        (_spoken_bot_label(ua, known_bots=KNOWN_BOTS), int(cnt), round((int(cnt) / total_cneg) * 100.0, 1))
                        for ua, cnt in cneg_rows[:4]
                    ]
                    live_ov = _format_overview_speech(total_hits, md_reads, total_cneg, md_pct, top_bots)
                else:
                    raise ValueError("empty overview db")
        except Exception:
            live_ov = (
                "Look first at the single cyan bar across the very top of this report. "
                "That top bar shows the live share of all H T T P responses served as Markdown on a scale from zero to one percent. "
                "Now look at the stacked horizontal bars below the divider, which break that Markdown activity out by grouped User-Agent, led by Exa Search Bot, Parallel dot A I's ShapBot, and Anthropic's Claude User."
            )
        s = s.replace("{LIVE_REPORT:overview}", live_ov)

    if "{LIVE_REPORT:bimodal}" in s:
        try:
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
            eligible_html = int((cur.fetchone() or [0])[0] or 0)
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
            snap_bi = _read_report_speech_snapshot("bimodal")
            if snap_bi and snap_bi.get("top_bots"):
                live_bi = _format_bimodal_speech(
                    int(snap_bi["eligible_html"]),
                    int(snap_bi["js_horizon_hits"]),
                    float(snap_bi["js_pct"]),
                    snap_bi["top_bots"],
                )
            else:
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
                c_row = cur.fetchone() or (0, 0)
                c_triggers, c_ips = int(c_row[0] or 0), int(c_row[1] or 0)
                js_rows = list(db.get_js_executors(limit=25))
                if cloud_triggers > 0:
                    js_rows.append((
                        f"[+{max(0, cloud_ips - 1)}] Mozilla/5.0 Chrome/135.0.0.0 Edg/135.0.0.0 (Stealth Cloud Renderers)",
                        cloud_triggers,
                    ))
                if c_triggers > 0 and not any("ClaudeBot" in str(u) for u, _ in js_rows):
                    js_rows.append((f"[+{max(0, c_ips - 1)}] ClaudeBot/1.0", c_triggers))
                js_rows.sort(key=lambda item: int(item[1]), reverse=True)
                total_js_execs = max(1, sum(int(c) for _, c in js_rows))
                js_horizon_hits = js_telem_hits if js_telem_hits > 0 else total_js_execs
                if eligible_html > 0 and js_rows:
                    js_pct = round((js_horizon_hits / max(1, eligible_html)) * 100.0, 2)
                    top_bots = [
                        (_spoken_bot_label(ua, known_bots=KNOWN_BOTS), int(cnt), round((int(cnt) / total_js_execs) * 100.0, 1))
                        for ua, cnt in js_rows[:4]
                    ]
                    live_bi = _format_bimodal_speech(eligible_html, js_horizon_hits, js_pct, top_bots)
                else:
                    raise ValueError("empty bimodal db")
        except Exception:
            live_bi = (
                "Look first at the single amber bar across the very top of this report. "
                "That top bar shows the live percentage of eligible H T M L page responses that executed client-side JavaScript and fired our eight-hundred-millisecond J S confirm dot gif sensor on a zero to five percent scale. "
                "Now look at the stacked horizontal bars below the divider, which break those JavaScript executions out by grouped User-Agent, led by Meta's External Agent, Open A I's SearchBot, and unbadged Google Cloud Chrome and Edge renderers."
            )
        s = s.replace("{LIVE_REPORT:bimodal}", live_bi)

    return s


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
        _write_report_speech_snapshot(
            mode,
            {
                "eligible_html": eligible_html_hits,
                "js_horizon_hits": js_horizon_hits,
                "total_js_execs": total_js_execs,
                "js_pct": js_pct,
                "top_bots": [
                    (_spoken_bot_label(ua, known_bots=KNOWN_BOTS), int(cnt), round((int(cnt) / total_js_execs) * 100.0, 1))
                    for ua, cnt in js_rows[:4]
                ],
            },
        )

        title_str = "⚡ JS DOM HYDRATION TRAPDOOR (0% → 5.0% OF ELIGIBLE HTML)"
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
    elif mode == "pirates":
        title_str = "🏴‍☠️ ACME CT-LOG PIRATE RADAR & NGINX IDS FOOTPRINT (UNMASKED EXPLOIT PROBES)"
        tbl.add_column("Probes", justify="right", style="bold bright_yellow", width=8, no_wrap=True)
        tbl.add_column("Horizon / Unmasked IP", style="bold red", width=25, no_wrap=True)
        tbl.add_column("Targeted Door · Exploit Vector · Scanner Signature", ratio=4, no_wrap=True)
        tbl.add_column("Horizontal Bar & Share", width=38, no_wrap=True)
        pirate_cond = """
            (
                p.value LIKE '%.php%'
                OR p.value LIKE '/wp-%'
                OR p.value LIKE '/.%'
                OR p.value LIKE '%/.env%'
                OR p.value LIKE '%/.git%'
                OR p.value LIKE '%phpmyadmin%'
                OR p.value LIKE '%/cgi-bin%'
                OR p.value LIKE '%/boaform%'
                OR p.value LIKE '%/actuator%'
                OR p.value LIKE '%/autodiscover%'
                OR p.value LIKE '%/owa%'
                OR p.value LIKE '%..%'
                OR p.value LIKE '%.bak%'
                OR p.value LIKE '%.sql%'
                OR ua.value LIKE '%sqlmap%'
                OR ua.value LIKE '%nikto%'
                OR ua.value LIKE '%nmap%'
                OR ua.value LIKE '%nuclei%'
                OR ua.value LIKE '%zgrab%'
                OR ua.value LIKE '%masscan%'
                OR ua.value LIKE '%wpscan%'
                OR EXISTS (
                    SELECT 1 FROM sqlite_master sm
                    WHERE sm.type = 'table' AND sm.name = 'pirate_logs'
                ) AND EXISTS (
                    SELECT 1 FROM pirate_logs pl
                    WHERE pl.ip_id = l.ip_id AND pl.path_id = l.path_id
                )
            )
        """
        cur.execute(
            """
            SELECT COALESCE(SUM(l.count), 0)
            FROM daily_logs l
            JOIN ips i ON l.ip_id = i.id
            WHERE i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
            """
        )
        total_http = int((cur.fetchone() or [1])[0] or 1)
        cur.execute(
            f"""
            SELECT COALESCE(SUM(l.count), 0), COUNT(DISTINCT l.ip_id), COUNT(DISTINCT l.path_id)
            FROM daily_logs l
            JOIN ips i ON l.ip_id = i.id
            JOIN paths p ON l.path_id = p.id
            JOIN user_agents ua ON l.ua_id = ua.id
            WHERE i.value NOT LIKE '127.%'
              AND i.value NOT LIKE '10.%'
              AND i.value NOT LIKE '192.168.%'
              AND {pirate_cond}
            """
        )
        p_tot_row = cur.fetchone() or (0, 0, 0)
        pirate_total = int(p_tot_row[0] or 0)
        pirate_ips = int(p_tot_row[1] or 0)
        pirate_paths = int(p_tot_row[2] or 0)
        pirate_pct = round((pirate_total / max(1, total_http)) * 100.0, 2)
        pirate_horizon_5pct = min(100.0, round((pirate_pct / 5.0) * 100.0, 1))
        tbl.add_row(
            f"{pirate_total:,}",
            Text("🎯 0% → 5.0% IDS HORIZON", style="bold bright_yellow"),
            Text(
                f"Share of {total_http:,} HTTP responses ({pirate_ips:,} unmasked Pirate IPs · {pirate_paths:,} exploit paths)",
                style="bold white",
            ),
            f"{_bar(pirate_horizon_5pct, 22, 'red')} [bold bright_yellow]{pirate_pct}% / 5.0%[/bold bright_yellow]",
        )
        tbl.add_section()
        cur.execute(
            f"""
            WITH pirate_hits AS (
                SELECT
                    l.ip_id,
                    l.ua_id,
                    l.path_id,
                    SUM(l.count) AS hits
                FROM daily_logs l
                JOIN ips i ON l.ip_id = i.id
                JOIN paths p ON l.path_id = p.id
                JOIN user_agents ua ON l.ua_id = ua.id
                WHERE i.value NOT LIKE '127.%'
                  AND i.value NOT LIKE '10.%'
                  AND i.value NOT LIKE '192.168.%'
                  AND {pirate_cond}
                GROUP BY l.ip_id, l.ua_id, l.path_id
            ),
            ip_rollup AS (
                SELECT
                    ph.ip_id,
                    SUM(ph.hits) AS total_probes,
                    COUNT(DISTINCT ph.path_id) AS distinct_paths
                FROM pirate_hits ph
                GROUP BY ph.ip_id
                ORDER BY total_probes DESC
                LIMIT 10
            )
            SELECT
                i.value AS ip_str,
                r.total_probes,
                r.distinct_paths,
                (
                    SELECT p2.value
                    FROM pirate_hits ph2
                    JOIN paths p2 ON ph2.path_id = p2.id
                    WHERE ph2.ip_id = r.ip_id
                    ORDER BY ph2.hits DESC
                    LIMIT 1
                ) AS top_path,
                (
                    SELECT ua2.value
                    FROM pirate_hits ph3
                    JOIN user_agents ua2 ON ph3.ua_id = ua2.id
                    WHERE ph3.ip_id = r.ip_id
                    ORDER BY ph3.hits DESC
                    LIMIT 1
                ) AS top_ua,
                COALESCE(
                    (
                        SELECT d.value
                        FROM pirate_logs pl
                        JOIN domains d ON pl.domain_id = d.id
                        WHERE pl.ip_id = r.ip_id
                        ORDER BY pl.count DESC
                        LIMIT 1
                    ),
                    (
                        SELECT d2.value
                        FROM pirate_hits ph4
                        JOIN domain_daily_logs dl2 ON dl2.path_id = ph4.path_id AND dl2.ua_id = ph4.ua_id
                        JOIN domains d2 ON dl2.domain_id = d2.id
                        WHERE ph4.ip_id = r.ip_id
                        ORDER BY dl2.count DESC
                        LIMIT 1
                    ),
                    'mikelev.in'
                ) AS top_domain
            FROM ip_rollup r
            JOIN ips i ON r.ip_id = i.id
            ORDER BY r.total_probes DESC
            """
        )
        p_rows = cur.fetchall()
        max_p = max([int(r[1]) for r in p_rows] or [1])
        for ip_str, probes_cnt, dist_paths, top_path, top_ua, top_dom in p_rows:
            clean_ua = str(top_ua or "-").replace("Mozilla/5.0 ", "")
            if len(clean_ua) > 26:
                clean_ua = clean_ua[:25] + "…"
            clean_path = str(top_path or "/")
            if len(clean_path) > 24:
                clean_path = clean_path[:23] + "…"
            dom_tag = str(top_dom or "mikelev.in").lower()
            vec_txt = Text.assemble(
                (f"[{dom_tag}] ", "bold bright_white"),
                (f"{clean_path} ", "bold bright_yellow"),
                (f"({int(dist_paths)}p) ", "dim white"),
                (clean_ua, "red"),
            )
            share_p = round((int(probes_cnt) / max(1, pirate_total)) * 100.0, 1)
            tbl.add_row(
                f"{int(probes_cnt):,}",
                Text(f"🏴‍☠️ {ip_str}", style="bold bright_white on #5a0000"),
                vec_txt,
                f"{_bar((int(probes_cnt) / max_p) * 100.0, 22, 'red')} [bold red]{share_p:>4.1f}% of IDS[/bold red]",
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
        _write_report_speech_snapshot(
            "overview",
            {
                "total_hits": total_hits,
                "md_reads": md_reads,
                "total_cneg": total_cneg,
                "md_pct": md_pct,
                "top_bots": [
                    (_spoken_bot_label(ua, known_bots=KNOWN_BOTS), int(cnt), round((int(cnt) / max(1, total_cneg)) * 100.0, 1))
                    for ua, cnt in cneg_rows[:4]
                ],
            },
        )

        title_str = "🧠 RFC 9110 MARKDOWN ADOPTION (0% → 1.0% OF HTTP RESPONSES)"
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
        "[bold bright_white]📡 Wire:[/bold bright_white] [bold #ffd700]https://MikeLev.in[/bold #ffd700] "
        "[dim]│[/dim] [bold bright_green]Free 911 Optics:[/bold bright_green] [bold bright_cyan]https://SunPug.io[/bold bright_cyan] "
        "[dim]│[/dim] [bold bright_magenta]Discord:[/bold bright_magenta] [bold bright_white]MikeLev.in/discord[/bold bright_white] "
        "[dim]·[/dim] [bold cyan]curl -fsSL sunpug.io | less[/bold cyan]"
    )
    panel_title = (
        f"[bold bright_cyan]{title_str}[/bold bright_cyan] "
        "[dim]·[/dim] [bold #ffd700]MikeLev.in[/bold #ffd700] "
        "[dim]·[/dim] [bold bright_green]SunPug.io[/bold bright_green]"
    )
    panel_kwargs = {"title": panel_title, "subtitle": footer, "padding": (0, 1)}
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
