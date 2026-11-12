#!/usr/bin/env python3
"""
terms.py — Master Eye-Orthography -> Ear-Orthography Table for Piper TTS.

Edit quickly from any Pipulate Nix shell by typing:
    terms

Synced automatically to Honeybot via `nixops` / `publish`, and shared locally
by `imports/voice_synthesis.py` so every headline, article body, station break,
and workshop prompt pronounces terms identically.

HOW TO ADD A TERM:
  1. CASE_INSENSITIVE_TERMS: Domains & mixed-case terms ("SaaS", "SunPug.io").
  2. EXACT_CASE_TERMS      : All-caps acronyms ("SEO", "FOSS", "RAG", "DOM").
     (Both literal tables auto-sort longest-first, so plurals & domains always
     match before shorter prefixes regardless of line order.)
  3. REGEX_TERMS           : Parameterized patterns ($10K, 911 Optics, etc.).
"""

import re
import sys

# Words after "$10K" that keep plural "dollars" (vs. attributive "$10K Pre-Render Scam" -> "dollar").
_NON_ATTRIBUTIVE_FOLLOWERS = (
    r"(?:and|or|but|nor|vs\.?|versus|which|that|who|whom|whose|where|when|while|if|as|than"
    r"|in|of|for|to|from|at|on|by|with|without|into|over|under|per|through|across|between"
    r"|a|an|the|is|was|are|were|be|been|has|have|had|can|could|will|would|should|may|might"
    r"|more|less|each|apiece|worth|away|back|up|down|out|off|today|now|here|there|alone|total|flat)\b"
)

# 1. Parameterized / Context-Sensitive Rules (evaluated in exact listed order)
REGEX_TERMS = (
    # Currency + /mo or /month ($10K/mo, $2.5M/month, $10,000/mo)
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[kK]\s*/\s*mo(?:nth)?\b"), r"\1 thousand dollars a month"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[mM]\s*/\s*mo(?:nth)?\b"), r"\1 million dollars a month"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[bB]\s*/\s*mo(?:nth)?\b"), r"\1 billion dollars a month"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*/\s*mo(?:nth)?\b"), r"$\1 a month"),
    # Hyphenated attributive currency ($10K-a-month, $10,000-a-month)
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[kK]-(?=a\b|per\b|[A-Za-z])"), r"\1 thousand dollar "),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)-(?=a-month\b|per-month\b)"), r"\1 dollar "),
    # Trailing plus ($300M+, $10K+, $1B+)
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[kK]\+"), r"\1 thousand dollars plus"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[mM]\+"), r"\1 million dollars plus"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[bB]\+"), r"\1 billion dollars plus"),
    # Attributive currency before a noun ("the $10K Pre-Render Scam" -> "10 thousand dollar")
    (
        re.compile(rf"\$(\d[\d,]*(?:\.\d+)?)\s*[kK]\b(?=\s+(?!{_NON_ATTRIBUTIVE_FOLLOWERS})[A-Za-z])"),
        r"\1 thousand dollar",
    ),
    (
        re.compile(rf"\$(\d[\d,]*(?:\.\d+)?)\s*[mM]\b(?=\s+(?!{_NON_ATTRIBUTIVE_FOLLOWERS})[A-Za-z])"),
        r"\1 million dollar",
    ),
    (
        re.compile(rf"\$(\d[\d,]*(?:\.\d+)?)\s*[bB]\b(?=\s+(?!{_NON_ATTRIBUTIVE_FOLLOWERS})[A-Za-z])"),
        r"\1 billion dollar",
    ),
    # Standalone / non-attributive currency ("I need $10K", "($10K)" -> "10 thousand dollars")
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[kK]\b"), r"\1 thousand dollars"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[mM]\b"), r"\1 million dollars"),
    (re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s*[bB]\b"), r"\1 billion dollars"),
    # SaaS: guard against "SaaS (Software as a Service)" double-expansion before expanding bare SaaS
    (re.compile(r"\bSaaS\b(?=\s*\(\s*Software as a Service)", re.IGNORECASE), "S A A S"),
    # 911 LLM Optics & emergency first-aid phrasing (never "nine hundred eleven")
    (re.compile(r"\b911_optics(?:_workflow)?(?:\.py)?\b", re.IGNORECASE), "nine eleven optics workflow"),
    (
        re.compile(
            r"\b911(?=\s+(?:LLM|L\s+L\s+M|Optics|emergency|first-aid|first\s+aid|audit|workflow|spectrometer)\b)",
            re.IGNORECASE,
        ),
        "nine eleven",
    ),
    # Numbered IETF RFCs & MIME content-negotiation headers
    (re.compile(r"\brfc9110\.org\b", re.IGNORECASE), "R F C 91 10 dot org"),
    (re.compile(r"\brfc9111\.io\b", re.IGNORECASE), "R F C 91 11 dot eye oh"),
    (re.compile(r"\bRFC[ -]?9110\b", re.IGNORECASE), "R F C 91 10"),
    (re.compile(r"\bRFC[ -]?9111\b", re.IGNORECASE), "R F C 91 11"),
    (re.compile(r"\bRFC[ -]?9421\b", re.IGNORECASE), "R F C 94 21"),
    (re.compile(r"\btext/markdown\b", re.IGNORECASE), "text slash markdown"),
    (re.compile(r"\btext/html\b", re.IGNORECASE), "text slash H T M L"),
    # Special capitonyms & punctuation-bearing shorthands
    (re.compile(r"\*{0,2}\bTL;DR\b\*{0,2}\s*[:.]?", re.IGNORECASE), "T L D R:"),
    (re.compile(r"(?<!Reverse )\bPolish\b(?!\s+notation\b)"), "polish"),
    (re.compile(r"\bWeb\s+1\.0\b", re.IGNORECASE), "Web one point oh"),
    (re.compile(r"\bWeb\s+2\.0\b", re.IGNORECASE), "Web two point oh"),
    (re.compile(r"\bWeb\s+3\.0\b", re.IGNORECASE), "Web three point oh"),
    (re.compile(r"\bSHA-?256\b", re.IGNORECASE), "S H A 256"),
    (re.compile(r"\b(?:Neovim|nvim)\b", re.IGNORECASE), "Neo vim"),
    (re.compile(r"\bdx/dy\b", re.IGNORECASE), "D X over D Y"),
    (re.compile(r"\bdy/dx\b", re.IGNORECASE), "D Y over D X"),
)

# 2. Case-Insensitive Domains, Brands, & Jargon (auto-sorted longest-first)
CASE_INSENSITIVE_TERMS = (
    # Domains & repo files
    ("mikelev.in", "Mike L E V dot eye N"),
    ("sunpug.io", "Sun Pug dot eye oh"),
    ("qamy.ai", "Q A my dot A I"),
    ("npvg.org", "N P V G dot org"),
    ("levinix.org", "Levinix dot org"),
    ("levinux.com", "Levinux dot com"),
    ("guerillatech.com", "Guerilla Tech dot com"),
    ("pipulate.com", "Pipulate dot com"),
    ("prerender.io", "Pre-render dot eye oh"),
    ("tryprofound.com", "try profound dot com"),
    ("hittail.com", "Hit Tail dot com"),
    ("HitTail", "Hit Tail"),
    ("commodore.net", "Commodore dot net"),
    ("exa.ai", "Exa dot A I"),
    ("llms.txt", "L L M S dot text"),
    ("GLOSSARY.md", "GLOSSARY dot M D"),
    ("README.md", "README dot M D"),
    ("AGENTS.md", "AGENTS dot M D"),
    ("SKILL.md", "SKILL dot M D"),
    ("AUDIT.md", "AUDIT dot M D"),
    # Industry & stack terms
    ("SaaS", "Software as a Service"),
    ("SerpApi", "surp A P I"),
    ("SERPs", "surps"),
    ("SERP", "surp"),
    ("Sunpugio", "Sun-pug-ee-oh"),
    ("SunPug", "Sun Pug"),
    ("Ahrefs", "H refs"),
    ("360i", "three sixty eye"),
    ("SQLite", "S Q Lite"),
    ("FastHTML", "Fast H T M L"),
    ("HTMX", "H T M X"),
    ("ChatGPT", "Chat G P T"),
    ("Nginx", "Engine X"),
    ("PyPI", "Pie P I"),
    ("kubectl", "kube control"),
    ("stdout", "standard out"),
    ("stderr", "standard error"),
    ("stdin", "standard in"),
    ("stdio", "standard I O"),
    ("rsync", "R sync"),
    ("JSONL", "J S O N L"),
    # Crawlers
    ("OAI-SearchBot", "O A I SearchBot"),
    ("ExaSearchBot", "Exa Search Bot"),
    ("ExaUser", "Exa User"),
    ("ClaudeBot", "Claude Bot"),
    ("ShapBot", "Shap Bot"),
)

# 3. Exact-Case Acronyms & MixedCase Proper Nouns (auto-sorted longest-first)
EXACT_CASE_TERMS = (
    ("NixOS", "Nix O S"),
    ("NPvg", "N P V G"),
    ("LPvg", "L P V G"),
    ("GPTBot", "G P T Bot"),
    ("OpenGraph", "Open Graph"),
    ("InnerTube", "Inner Tube"),
    ("FCrDNS", "F C R D N S"),
    ("RLVR", "R L V R"),
    ("RLHF", "R L H F"),
    ("vi", "vee eye"),
    ("FOSS", "foss"),
    ("RFCs", "R F C's"),
    ("RFC", "R F C"),
    ("SEOs", "S E O's"),
    ("SEO", "S E O"),
    ("AEOs", "A E O's"),
    ("AEO", "A E O"),
    ("GEOs", "G E O's"),
    ("GEO", "G E O"),
    ("AIO", "A I O"),
    ("ADNS", "A D N S"),
    ("QED", "Q E D"),
    ("SGE", "S G E"),
    ("RAG", "R A G"),
    ("MCP", "M C P"),
    ("GSC", "G S C"),
    ("GA4", "G A 4"),
    ("PDPs", "P D Ps"),
    ("PDP", "P D P"),
    ("PLPs", "P L Ps"),
    ("PLP", "P L P"),
    ("SKUs", "S K Us"),
    ("SKU", "S K U"),
    ("CTAs", "C T As"),
    ("CTA", "C T A"),
    ("KPIs", "K P Is"),
    ("KPI", "K P I"),
    ("CRO", "C R O"),
    ("ROI", "R O I"),
    ("CMS", "C M S"),
    ("CDNs", "C D Ns"),
    ("CDN", "C D N"),
    ("DOM", "D O M"),
    ("HTTPS", "H T T P S"),
    ("HTTP", "H T T P"),
    ("HTML", "H T M L"),
    ("SSH", "S S H"),
    ("CLI", "C L I"),
    ("TUI", "T U I"),
    ("URLs", "U R Ls"),
    ("URL", "U R L"),
    ("URIs", "U R Is"),
    ("URI", "U R I"),
    ("APIs", "A P Is"),
    ("API", "A P I"),
    ("DNS", "D N S"),
    ("TLS", "T L S"),
    ("SSL", "S S L"),
    ("W3C", "W 3 C"),
    ("CPUs", "C P Us"),
    ("CPU", "C P U"),
    ("GPUs", "G P Us"),
    ("GPU", "G P U"),
    ("LLMs", "L L Ms"),
    ("LLM", "L L M"),
)

# Multiline speaker-turn normalizers for Storytime Markdown articles
AI_SPEAKER_LABEL_PAT = (
    r"(?:(?:Gemini|Claude|ChatGPT|OpenAI|Opus|Sonnet|Shipmunk)\b"
    r"(?:[ \t]+(?:\d+(?:\.\d+)*"
    r"|Argon|Carbon|Neon|Helium|Krypton|Xenon|Radon"
    r"|Pro|Flash|Ultra|Nano|High|Medium|Low"
    r"|Opus|Sonnet|Haiku|Code|User|Web|Bot"
    r"|Thinking|Exp|Experimental|Preview|Lite|Mini|Max|Plus|Turbo"
    r"|o\d+|O'Theseus"
    r"|[A-Za-z][A-Za-z0-9-]{1,15}(?=[ \t]+(?:High|Medium|Low|Pro|Flash|Ultra|Nano|Lite|Mini|Max|Plus|Thinking|Preview|Exp)\b))){0,4}"
    r"|AI)"
)

SPEAKER_TURN_RULES = (
    (
        re.compile(
            r"(?m)^[ \t]*(?:\*\*[ \t]*(?:MikeLev\.in|Mike[ \t]+Levin|Mike|Me)[ \t]*:?[ \t]*\*\*[ \t]*:?|(?:MikeLev\.in|Mike[ \t]+Levin|Mike|Me)[ \t]*:)[ \t]*(?:\r?\n[ \t]*(?!\*\*[ \t]*(?:Gemini|Claude|ChatGPT|OpenAI|Opus|Sonnet|Shipmunk|AI|MikeLev\.in|Mike|Me)\b))*",
            re.IGNORECASE,
        ),
        "\n\nMike: ",
    ),
    (
        re.compile(
            rf"(?m)^[ \t]*\*\*[ \t]*({AI_SPEAKER_LABEL_PAT})[ \t]*:?[ \t]*\*\*[ \t]*:?[ \t]*(?:\r?\n[ \t]*(?!\*\*[ \t]*(?:Gemini|Claude|ChatGPT|OpenAI|Opus|Sonnet|Shipmunk|AI|MikeLev\.in|Mike|Me)\b))*",
            re.IGNORECASE,
        ),
        r"\n\n\1: ",
    ),
)


def _compile_literal_term(term: str, flags: int = 0) -> re.Pattern:
    lead = r"\b" if (term[0].isalnum() or term[0] == "_") else r"(?<!\w)"
    tail = r"\b" if (term[-1].isalnum() or term[-1] == "_") else r"(?!\w)"
    return re.compile(f"{lead}{re.escape(term)}{tail}", flags)


INLINE_TTS_MAP = tuple(
    list(REGEX_TERMS)
    + [
        (_compile_literal_term(term, re.IGNORECASE), repl)
        for term, repl in sorted(CASE_INSENSITIVE_TERMS, key=lambda pair: -len(pair[0]))
    ]
    + [
        (_compile_literal_term(term, 0), repl)
        for term, repl in sorted(EXACT_CASE_TERMS, key=lambda pair: -len(pair[0]))
    ]
)

MARKDOWN_TTS_MAP = SPEAKER_TURN_RULES + INLINE_TTS_MAP


def apply_inline_tts_terms(text: str) -> str:
    """Apply phonetic ear-orthography rules to a single title, station break, or spoken line."""
    if not text:
        return ""
    out = str(text)
    for pattern, spoken_repl in INLINE_TTS_MAP:
        out = pattern.sub(spoken_repl, out)
    return re.sub(r"[ \t]+,", ",", out)


def apply_markdown_tts_terms(text: str) -> str:
    """Strip Markdown rules/tables/box-art and apply speaker + phonetic rules for Storytime articles."""
    if not text:
        return ""
    out = str(text)
    out = re.sub(r"(?m)^[ \t]*[-*_]{3,}[ \t]*$", "", out)
    out = re.sub(r"(?m)^[ \t]*\|[ \t:|-]+\|[ \t]*$", "", out)
    out = re.sub(
        r"(?m)^[ \t]*\|(.+)\|[ \t]*$",
        lambda m: ", ".join(c.strip() for c in m.group(1).split("|") if c.strip()),
        out,
    )
    out = re.sub(r"[─━│┃┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬░▒▓█▲▼◄►]{2,}", " ", out)
    out = re.sub(r"\s*(?:<-->|<->|-->|->|==>|<==)\s*", ", ", out)
    for pattern, spoken_repl in MARKDOWN_TTS_MAP:
        out = pattern.sub(spoken_repl, out)
    return re.sub(r"[ \t]+,", ",", out)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(apply_inline_tts_terms(" ".join(sys.argv[1:])))
    else:
        demo = "Killing the $10K Pre-Render Scam: SaaS & SERPs for SEOs at SunPug.io with 911 LLM Optics ($10K/mo vs $10K)"
        print(f"Loaded {len(INLINE_TTS_MAP)} inline TTS rules.")
        print(f"  IN : {demo}")
        print(f"  OUT: {apply_inline_tts_terms(demo)}")
