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
    script.append(("SAY", "Greetings, visitor."))
    script.append(("SAY", "System Online. Beginning Web Logfile Streaming. Looking for AI-bots. Who executes JavaScript?"))
    script.append(("SAY", "We will watch the web logs of a static home-hosted Jekyll site, and we shall read the content of that site."))
    script.append(("SAY", "On every loop, we shall report on which AI-bots execute JavaScript and which don't."))

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
