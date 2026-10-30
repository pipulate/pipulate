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


def append_article_content(script, article):
    """Append article body chunks, preserving player-piano directives."""
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
                script.append(("PATRONUS", {"key": key, "duration": duration}))
        elif chunk.startswith("[[MEDIA:") and chunk.endswith("]]"):
            inner = chunk[len("[[MEDIA:"):-2].strip()
            parts = inner.rsplit(":", 1)
            key = parts[0].strip()
            try:
                duration = float(parts[1]) if len(parts) > 1 else 8.0
            except ValueError:
                duration = 8.0
            if key:
                script.append(("MEDIA", {"path": key, "duration": duration}))
        elif chunk and len(chunk) > 2:
            script.append(("SAY", chunk))


def _append_article_performance(script, article, is_latest=True):
    """Emit a voice-synchronized Figlet title card followed by the article body."""
    lead = (
        f"Reading the latest entry from {article['date']}."
        if is_latest
        else f"Accessing entry from {article['date']}."
    )
    script.append((
        "CARD",
        {
            "label": f"STORYTIME\n{article['date']}",
            "say": f"{lead} Title: {article['title']}.",
        },
    ))
    script.append(("BGM", "START"))
    script.append(("SAY", "Reading entry..."))
    append_article_content(script, article)
    script.append(("BGM", "STOP"))
    script.append((
        "CARD",
        {
            "label": "READ MORE\nMIKELEV.IN",
            "say": (
                f"That concludes {article['title']}. "
                "You can read the full text and source code at Mike L E V dot eye N, "
                "or inspect the portable workshop through any of our eight doors, including "
                "Sun Pug dot eye oh, Guerilla Tech dot com, R F C 9110 dot org, and R F C 9111 dot eye oh, "
                "using curl pipe less. "
                "Drop a message in the live chat if you are tuning in. "
                "A human operator monitors this observatory and can break in live."
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
