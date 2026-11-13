"""
The Sheet Music for the Honeybot Player Piano.
Loops the newest published article with voice-synchronized Figlet title cards
so continuous 24/7 streams slice cleanly into per-article VOD episodes.
"""
import sys
from pathlib import Path

# Add script dir to path to find content_loader
sys.path.append(str(Path(__file__).parent))

# Set True only if you want to walk backward through recent + random archive
# posts after reading the newest article; False (default) loops the newest
# published article continuously for clean VOD episode segmentation.
ARCHIVE_WALK = False


def _extract_article_cues(article):
    """Parse article content into ordered player-piano cues, routing headings to Norma Centroid."""
    cues = []
    for chunk in article['content'].split('\n'):
        chunk = chunk.strip()
        if chunk.startswith("[[PATRONUS:") and chunk.endswith("]]"):
            inner = chunk[len("[[PATRONUS:"):-2].strip()
            parts = inner.rsplit(":", 1)
            key = parts[0].strip()
            try:
                duration = float(parts[1]) if len(parts) > 1 else 3.5
            except ValueError:
                duration = 3.5
            if key:
                cues.append(("PATRONUS", {"key": key, "duration": duration}))
        elif chunk.startswith("[[MEDIA:") and chunk.endswith("]]"):
            inner = chunk[len("[[MEDIA:"):-2].strip()
            parts = inner.rsplit(":", 1)
            key = parts[0].strip()
            try:
                duration = float(parts[1]) if len(parts) > 1 else 8.0
            except ValueError:
                duration = 8.0
            if key:
                cues.append(("MEDIA", {"path": key, "duration": duration}))
        elif chunk.startswith("[[HEADING:") and chunk.endswith("]]"):
            heading_text = chunk[len("[[HEADING:"):-2].strip()
            if heading_text:
                cues.append(("SAY", f"[[HEADING]] {heading_text}"))
        elif chunk and len(chunk) > 2:
            cues.append(("SAY", chunk))
    return cues


def append_article_content(script, article):
    """Append article body chunks, preserving player-piano directives."""
    script.extend(_extract_article_cues(article))


def _find_intermission_split(cues):
    """Locate a clean heading or speaker-turn boundary near the 50% mark of an article."""
    n = len(cues)
    if n < 16:
        return 0
    mid = n // 2
    lo = max(4, n // 3)
    hi = min(n - 4, (2 * n) // 3)
    best_idx = None
    best_dist = n
    turn_prefixes = ("[[heading]]", "mike:", "me:", "gemini", "claude", "chat g p t", "chatgpt", "shipmunk", "a i:")
    for idx in range(lo, hi + 1):
        cmd, val = cues[idx]
        if cmd == "SAY" and isinstance(val, str):
            low = val.strip().lower()
            if any(low.startswith(p) for p in turn_prefixes):
                dist = abs(idx - mid)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
    return best_idx if best_idx is not None else mid


HERO_IMAGE_DURATION = 8.0


def _append_article_performance(script, article, is_latest=True):
    """Emit symmetrical Opening Overture + Act I + Midpoint Intermission + Act II."""
    lead = (
        f"Reading the latest entry from {article['date']}."
        if is_latest
        else f"Accessing entry from {article['date']}."
    )
    title_str = str(article.get("title") or "latest entry")
    script.append((
        "CARD",
        {
            "label": f"STORYTIME\n{article['date']}",
            "say": f"{lead} Title: {title_str}.",
        },
    ))
    script.append(("OVERTURE", {"title": title_str}))
    script.append(("BGM", "START"))
    image_path = str(article.get("image") or "").strip()
    if image_path:
        script.append(("MEDIA", {"path": image_path, "duration": HERO_IMAGE_DURATION}))
    script.append(("SAY", "Reading entry..."))
    body_cues = _extract_article_cues(article)
    split_idx = _find_intermission_split(body_cues)
    if 0 < split_idx < len(body_cues):
        script.extend(body_cues[:split_idx])
        script.append(("BGM", "STOP"))
        script.append(("INTERMISSION", {"title": title_str}))
        script.append(("BGM", "START"))
        script.append(("SAY", "Resuming storytime with Act Two."))
        script.extend(body_cues[split_idx:])
    else:
        script.extend(body_cues)
    script.append(("BGM", "STOP"))
    script.append((
        "CARD",
        {
            "label": "SUNPUG.IO &\nMIKELEV.IN",
            "say": (
                f"That concludes {article['title']}. "
                "Grab your own self-replicating Sun Pug and 911 LLM Optics free at SunPug.io, RFC9110.org, or RFC9111.io, "
                "read the full text and raw receipts at mikelev.in, and forward this broadcast to one sharp builder who needs it. "
                "Join the Founding 1,000 AI-Readiness Consultants at mikelev.in/discord, or drop a message in the live chat — "
                "a human operator monitors this observatory and can break in live."
            ),
        },
    ))
    script.append(("WAIT", 3))


def get_script(breaking=False):
    """Generate the Honeybot playlist.

    By default (ARCHIVE_WALK=False), both breaking=True and breaking=False read
    the single newest published article so the stream loops the current post
    until the next publish or ytroll cut. When breaking=False (cold start), a
    short station-opening card precedes the first reading.
    """
    script = []

    if breaking or not ARCHIVE_WALK:
        if not breaking:
            script.append((
                "CARD",
                {
                    "label": "WEB BOT AI\nOBSERVATORY",
                    "say": (
                        "Greetings, entity. You are watching the Web Bot A I Observatory on Honeybot. "
                        "We are monitoring a home-hosted Nix O S web server and reading "
                        "the latest published article."
                    ),
                },
            ))
        try:
            import importlib
            import content_loader
            importlib.reload(content_loader)
            articles = content_loader.get_playlist(recent_n=1, include_archive=False)
            if articles:
                _append_article_performance(script, articles[0], is_latest=True)
        except Exception as e:
            script.append(("SAY", f"Error compiling latest article: {e}"))
        return script

    # Optional legacy archive walk (only reached when ARCHIVE_WALK = True)
    script.append((
        "CARD",
        {
            "label": "HONEYBOT\nLIVE",
            "say": "Greetings, entity. You are watching the Honeybot.",
        },
    ))
    try:
        import importlib
        import content_loader
        importlib.reload(content_loader)
        articles = content_loader.get_playlist(recent_n=10, include_archive=True)
        for i, article in enumerate(articles):
            if i == 10:
                script.append(("SAY", "Recent logs analysis complete. Engaging Random Access Memory."))
                script.append(("WAIT", 3))
            _append_article_performance(script, article, is_latest=(i == 0))
    except Exception as e:
        script.append(("SAY", f"Error compiling playlist: {e}"))
    return script
