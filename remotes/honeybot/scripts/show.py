"""
The Sheet Music for the Honeybot Player Piano.
Structure: A list of tuples (COMMAND, CONTENT)
Commands:
  - SAY:   Narrate the text (waits for audio queue)
  - VISIT: Open a URL in the browser (fire and forget)
  - WAIT:  Sleep for N seconds (pacing)
  - CLOSE: Close the browser
"""

SCRIPT = [
    # --- The Hook ---
    ("SAY", "Greetings, visitor."),
    ("SAY", "What you are seeing here is the real-time web log file data for a site preparing itself for AI-readiness."),
    ("SAY", "You are welcome to tag along as we carry out project after project, narrating them right here like this as we go."),
    
    # --- The Visual Handshake ---
    ("SAY", "Let's open a secure channel to the target."),
    ("VISIT", "https://mikelev.in/"),
    ("WAIT", 5),
    ("SAY", "There is nothing new under the Sun and everything old is new again. You have found it."),
    ("SAY", "Web logfiles are really, really important again because it is where much of your competitive intelligence resides."),
    ("WAIT", 10),
    ("CLOSE", ""), 
    
    # --- The Argument ---
    ("SAY", "And you are probably cut off from yours. Here I am showing mine steaming in real time. Not impossible. See?"),
    ("SAY", "So now that something old, our web logfiles, are seeing the light of day again, what can we do?"),
    
    # --- The Bot Trap Tease ---
    ("SAY", "Well, we can see what bots execute JavaScript for starters."),
    ("SAY", "Wouldn't you like smoking gun evidence whether OpenAI or Anthropic really execute JavaScript or not?"),
    
    # --- The 404 Project ---
    ("SAY", "I really should take care of my 404s. I could use AI to make those redirection decisions."),
    ("SAY", "I mean just imagine well implemented 404 page-not-found redirect mapping possibilities in the age of AI!"),
    ("SAY", "But that is something I *have* to get to. Let's talk about what I *want* to get to."),
    
    # --- The Trap Implementation Plan ---
    ("SAY", "Gemini wanted me to call my bot captcha 'beacon dot J S'."),
    ("SAY", "But that sounds like tracking."),
    ("SAY", "Instead, I will call it 'J query dot min dot J S'."),
    ("SAY", "Why? Because if a bot claims to render the web, it *must* load jQuery."),
    ("SAY", "If we see the HTML request in the logs, but *not* the jQuery request... we know they are faking it."),
    
    # --- The Outro ---
    ("SAY", "So keep checking back as this article gets longer each time it is replaced by the next chapter in the ongoing adventure we call AI-readiness."),
    ("SAY", "Or more broadly, future-proofing your skills in the age of AI.")
]