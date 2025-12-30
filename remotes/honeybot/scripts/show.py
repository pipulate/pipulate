"""
The Sheet Music for the Honeybot Player Piano.
Dynamically loads the last N articles from the Jekyll source.
Mode: Campfire Protocol (Read content AFTER closing browser).
"""
import sys
from pathlib import Path

# Add script dir to path to find content_loader
sys.path.append(str(Path(__file__).parent))

PREAMBLE = [
    ("SAY", "Greetings, visitor."),
    ("SAY", "System Online. Initiating Campfire Protocol."),
    ("SAY", "We will now traverse the archives, reading the logs of the past while watching the logs of the present."),
]

try:
    from content_loader import get_playlist
    articles = get_playlist(limit=10) # Last 10 articles
    
    PLAYLIST = []
    
    for article in articles:
        # 1. Introduction
        PLAYLIST.append(("SAY", f"Accessing entry from {article['date']}."))
        PLAYLIST.append(("SAY", f"Title: {article['title']}."))
        
        # 2. The Flashcard (Visual Context)
        if article['url']:
            PLAYLIST.append(("SAY", "Loading visual context..."))
            PLAYLIST.append(("VISIT", article['url']))
            PLAYLIST.append(("WAIT", 10)) # Keep visible for 10s
            PLAYLIST.append(("CLOSE", "")) # Close it!
        
        # 3. The Campfire Story (Audio Context)
        # Now the screen is back to the terminal logs
        PLAYLIST.append(("SAY", "Reading entry..."))
        
        # Split text into chunks for the queue
        for chunk in article['content'].split('\n'):
            if chunk.strip():
                # Skip very short lines that might be artifacts
                if len(chunk.strip()) > 2:
                    PLAYLIST.append(("SAY", chunk))
        
        # 4. Breath between stories
        PLAYLIST.append(("WAIT", 3))

except Exception as e:
    PLAYLIST = [("SAY", f"Error compiling playlist: {e}")]

OUTRO = [
    ("SAY", "Archive traversal complete. The loop will now reset."),
    ("SAY", "Returning to the Black River.")
]

# The Final Script
SCRIPT = PREAMBLE + PLAYLIST + OUTRO