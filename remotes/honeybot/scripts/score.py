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
    jb_idx = int(article.get("jukebox_index") or 0)
    raw_title = str(article.get("raw_title") or article.get("title") or "latest entry")
    title_str = str(article.get("title") or raw_title)
    jb_tag = f"story number {jb_idx}, " if jb_idx else ""
    lead = (
        f"Reading the latest entry, {jb_tag}published {article['date']}."
        if is_latest
        else f"Playing {jb_tag}from {article['date']}."
    )
    art_id = str(
        article.get("id")
        or article.get("slug")
        or article.get("permalink")
        or f"{article.get('date', '')}:{raw_title}"
    ).strip()
    card_lbl = f"STORYTIME #{jb_idx}" if jb_idx else "STORYTIME"
    script.append((
        "CARD",
        {
            "label": card_lbl,
            "subtitle": f"{raw_title}\n[{article['date']}]",
            "say": f"{lead} Headline: {title_str}.",
            "article": art_id,
            "meta": {
                "title": title_str,
                "raw_title": raw_title,
                "image": str(article.get("image") or "").strip(),
                "jukebox_index": jb_idx,
            },
        },
    ))
    script.append(("OVERTURE", {"title": title_str, "raw_title": raw_title, "jukebox_index": jb_idx, "article": art_id}))
    script.append(("BGM", "START"))
    script.append(("BUMPER", {"slot": "post_overture"}))
    image_path = str(article.get("image") or "").strip()
    if image_path:
        script.append(("MEDIA", {"path": image_path, "duration": HERO_IMAGE_DURATION}))
    script.append(("SAY", "Reading entry..."))
    body_cues = _extract_article_cues(article)
    split_idx = _find_intermission_split(body_cues)
    if 0 < split_idx < len(body_cues):
        script.extend(body_cues[:split_idx])
        script.append(("BUMPER", {"slot": "pre_intermission"}))
        script.append(("INTERMISSION", {"title": title_str}))
        script.append(("SAY", "Resuming storytime with Act Two."))
        script.extend(body_cues[split_idx:])
    else:
        script.extend(body_cues)
    script.append((
        "CARD",
        {
            "label": "SUNPUG.IO &\nMIKELEV.IN",
            "pace": "standard",
            "say": (
                f"That concludes {article['title']}. "
                "Remember the two addresses: you get the long-form articles and raw book receipts at MikeLev.in, "
                "and you get the local-first A I-Readiness tools and 911 L L M Optics free at SunPug.io. "
                "Join the Founding 1,000 A I-Readiness Consultants at MikeLev.in/discord, or drop a message in the live chat — "
                "a human operator monitors this observatory and can break in live."
            ),
        },
    ))
    script.append(("WAIT", 1))


def get_script(breaking=False, jukebox_index=None):
    """Generate the Honeybot playlist (or a specific 1..N Jukebox selection)."""
    script = [("BUMPER", {"slot": "pre_intro"})]

    if jukebox_index:
        try:
            import importlib
            import content_loader
            importlib.reload(content_loader)
            jb_art = content_loader.get_article_by_jukebox_index(int(jukebox_index))
            if jb_art:
                _append_article_performance(script, jb_art, is_latest=False)
                return script
        except Exception as e:
            script.append(("SAY", f"Error loading Jukebox entry {jukebox_index}: {e}"))

    if breaking or not ARCHIVE_WALK:
        articles = []
        try:
            import importlib
            import content_loader
            importlib.reload(content_loader)
            articles = content_loader.get_playlist(recent_n=1, include_archive=False)
        except Exception as e:
            script.append(("SAY", f"Error compiling latest article: {e}"))
        if not breaking:
            a0 = articles[0] if articles else {}
            jb0 = a0.get("jukebox_index")
            sub0 = f"Up Next #{jb0}: {a0['raw_title']}" if (a0.get("raw_title") and jb0) else (f"Up Next: {a0['raw_title']}" if a0.get("raw_title") else "")
            say0 = (
                f"Greetings, entity. You are watching A.I. Fishtank Story-Time on Honeybot. "
                f"Up next is story number {jb0}, titled: {a0['title']}. "
                "Type any available story number or nine eleven in live chat to take control."
                if a0.get("title") and jb0
                else (
                    "Greetings, entity. You are watching A.I. Fishtank Story-Time on Honeybot. "
                    "We are monitoring a home-hosted Nix O S web server and reading the latest Storytime entry."
                )
            )
            script.append(("CARD", {"label": "A.I. FISHTANK\nSTORY-TIME", "subtitle": sub0, "say": say0}))
        if articles:
            _append_article_performance(script, articles[0], is_latest=True)
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
