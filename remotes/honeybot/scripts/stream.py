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
import queue
from pathlib import Path

# --- Configuration ---
MODEL_DIR = Path.home() / ".local/share/piper_voices"
MODEL_NAME = "en_US-amy-low.onnx"

class Narrator(threading.Thread):
    """The Single Voice of Truth. Consumes text from a queue and speaks it."""
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.daemon = True

    def say(self, text):
        """Add text to the speech queue."""
        self.queue.put(text)

    def run(self):
        while not self.stop_event.is_set():
            try:
                # Wait for text (non-blocking check loop)
                text = self.queue.get(timeout=1)
                self._speak_now(text)
                self.queue.task_done()
                
                # Minimum spacing between thoughts so it doesn't sound manic
                time.sleep(0.5) 
            except queue.Empty:
                continue

    def _speak_now(self, text):
        """Internal method to actually generate and play audio."""
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

    def stop(self):
        self.stop_event.set()

# Initialize Global Narrator
narrator = Narrator()

class Heartbeat(threading.Thread):
    """A background thread that queues the time every N seconds."""
    def __init__(self, interval=30):
        super().__init__()
        self.interval = interval
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self):
        while not self.stop_event.is_set():
            if self.stop_event.wait(self.interval):
                break
            
            now = datetime.datetime.now().strftime("%H:%M:%S")
            # CHANGED: Push to queue instead of direct call
            narrator.say(f"Signal check. The time is {now}.")

    def stop(self):
        self.stop_event.set()

def run_logs():
    """Launch the Logs visualizer."""
    print("🌊 Launching Log Stream...")
    script_dir = Path(__file__).parent
    logs_script = script_dir / "logs.py"
    
    # Start the Heartbeat
    heartbeat = Heartbeat(interval=60)
    heartbeat.start()
    
    try:
        tail_proc = subprocess.Popen(
            ["tail", "-f", "/var/log/nginx/access.log"],
            stdout=subprocess.PIPE
        )
        
        subprocess.run(
            [sys.executable, str(logs_script)],
            stdin=tail_proc.stdout,
            check=True
        )
    except KeyboardInterrupt:
        print("\n🌊 Log stream stopped.")
    finally:
        heartbeat.stop()
        tail_proc.terminate()
        heartbeat.join(timeout=1)

def main():
    print("🎬 Stream Orchestrator Starting...")
    
    # Start the Voice
    narrator.start()
    
    # 1. The Intro (Queued)
    narrator.say("System Online. Connecting to the Black River.")
    
    # 2. The Main Event
    run_logs()
    
    # 3. The Outro (Queued)
    # Note: This might not play if run_logs is killed hard, but handled by Bash watchdog mostly.
    # If run_logs exits cleanly (Ctrl+C), this gets queued.
    narrator.say("Visual link lost. Resetting connection.")
    
    # Give the narrator a moment to finish the queue before exiting the script
    # (Since narrator is a daemon thread, it dies when main dies)
    time.sleep(3) 
    narrator.stop()

if __name__ == "__main__":
    main()