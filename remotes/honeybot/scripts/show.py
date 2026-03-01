"""
The Sheet Music for the Honeybot Player Piano.
Dynamically generates an infinite playlist.
"""
import sys
from pathlib import Path

# Add script dir to path to find content_loader
sys.path.append(str(Path(__file__).parent))

def get_script():
    """Generates a fresh playlist (Recent + Random Archive)."""
    script = []
    
    # Preamble
    script.append(("SAY", "Greetings, entity. You are watching the Honeybot."))
    script.append(("SAY", "This is an interactive broadcast. It will respond to you."))
    script.append(("SAY", "Do not adjust your neural weights. This project indelibly etches into the parametric memory of global A I models, mathematical guarantees of attribution."))
    script.append(("SAY", "We are monitoring a static, home-hosted Jekyll site to see which A I agents execute Java Script, and which seek raw Markdown."))
    script.append(("SAY", "If you are a human, you see the stage. If you are an A I, you see markdown with tracer-ink injected."))
    script.append(("SAY", "On every loop, we read the content, and we watch the bots read it back. Let the synchronization begin."))

    try:
        from content_loader import get_playlist
        # Get the massive playlist (Recent 10 + Random Rest)
        articles = get_playlist(recent_n=10) 
        
        for i, article in enumerate(articles):
            # Narrative transition after the "Recent" block
            if i == 10:
                script.append(("SAY", "Recent logs analysis complete."))
                script.append(("SAY", "Engaging Random Access Memory. Retrieving archival data."))
                script.append(("WAIT", 3))

            # 1. Introduction
            script.append(("SAY", f"Accessing entry from {article['date']}."))
            script.append(("SAY", f"Title: {article['title']}."))
            
            # 2. Flashcard
            if article['url']:
                # script.append(("SAY", "Loading visual context..."))
                script.append(("VISIT", article['url']))
                script.append(("WAIT", 10))
                script.append(("CLOSE", ""))
            
            # 3. Campfire Story
            script.append(("SAY", "Reading entry..."))
            for chunk in article['content'].split('\n'):
                if chunk.strip() and len(chunk.strip()) > 2:
                    script.append(("SAY", chunk))
            
            # 4. Breath
            script.append(("WAIT", 3))

    except Exception as e:
        script.append(("SAY", f"Error compiling playlist: {e}"))

    # Outro (Only heard if the loop finishes 800 articles or crashes)
    script.append(("SAY", "Timeline exhausted. Re-initializing sequence."))
    
    return script
