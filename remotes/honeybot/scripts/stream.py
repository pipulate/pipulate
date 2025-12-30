#!/usr/bin/env python3
"""
🌊 Stream Orchestrator
The 'Mind' of the Honeybot.
Handles the intro, launches the visualizer, and maintains the heartbeat.
"""

import os
import sys
import time
import subprocess
import threading
import datetime
from pathlib import Path

# --- Configuration ---
MODEL_DIR = Path.home() / ".local/share/piper_voices"
MODEL_NAME = "en_US-amy-low.onnx"

def speak(text):
    """Speak text using the system's piper-tts capability."""
    # (Same implementation as before, omitted for brevity but kept in file)
    # ... [Implementation of speak()] ...
    # For context recapture, I will include the full function in the output below.
    print(f"🔊 Speaking: {text}")
    model_path = MODEL_DIR / MODEL_NAME
    if not model_path.exists():
        print(f"❌ Voice model not found at {model_path}")
        return

    try:
        p1 = subprocess.Popen(["echo", text], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(
            ["piper", "--model", str(model_path), "--output_raw"],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        p1.stdout.close()
        subprocess.run(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
            stdin=p2.stdout,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except Exception as e:
        print(f"❌ Speech failed: {e}")

class Heartbeat(threading.Thread):
    """A background thread that speaks the time every N seconds."""
    def __init__(self, interval=30):
        super().__init__()
        self.interval = interval
        self.stop_event = threading.Event()
        self.daemon = True # Kill if main process dies

    def run(self):
        while not self.stop_event.is_set():
            # Wait first, so we don't talk over the intro
            if self.stop_event.wait(self.interval):
                break
            
            # The Signal Check
            now = datetime.datetime.now().strftime("%H:%M:%S")
            text = f"Signal check. The time is {now}."
            speak(text)

    def stop(self):
        self.stop_event.set()

def run_logs():
    """Launch the Logs visualizer."""
    print("🌊 Launching Log Stream...")
    script_dir = Path(__file__).parent
    logs_script = script_dir / "logs.py"
    
    # Start the Heartbeat
    heartbeat = Heartbeat(interval=60) # Speak every 60 seconds
    heartbeat.start()
    
    try:
        tail_proc = subprocess.Popen(
            ["tail", "-f", "/var/log/nginx/access.log"],
            stdout=subprocess.PIPE
        )
        
        # Run logs.py (blocks until user exits or crash)
        subprocess.run(
            [sys.executable, str(logs_script)],
            stdin=tail_proc.stdout,
            check=True
        )
    except KeyboardInterrupt:
        print("\n🌊 Log stream stopped.")
    finally:
        # Cleanup
        heartbeat.stop()
        tail_proc.terminate()
        heartbeat.join(timeout=1)

def main():
    print("🎬 Stream Orchestrator Starting...")
    
    # 1. The Intro
    speak("System Online. Connecting to the Black River.")
    time.sleep(1)
    
    # 2. The Main Event (includes Heartbeat)
    run_logs()
    
    # 3. The Outro
    speak("Visual link lost. Resetting connection.")
    time.sleep(1)

if __name__ == "__main__":
    main()