#!/usr/bin/env python3
"""
🌊 Stream Orchestrator
The 'Mind' of the Honeybot.
Handles the intro, launches the visualizer, and maintains the heartbeat.
"""

import os
import sys
import time
import datetime
import subprocess
import threading
import shutil   # <--- Add this import
import tempfile # <--- Add this import
import queue
from pathlib import Path

# --- Configuration ---
SHOW_DURATION_MINUTES = 45  # <--- The New "T" Variable

sys.path.append(str(Path(__file__).parent))

try:
    import show 
    from content_loader import check_for_updates
except ImportError:
    show = None

# --- Configuration ---
MODEL_DIR = Path.home() / ".local/share/piper_voices"
MODEL_NAME = "en_US-amy-low.onnx"


def run_tui_app(script_name, duration=None):
    """Launch a TUI script. If duration is set, kill it after N seconds."""
    script_path = Path(__file__).parent / script_name
    
    # --- NEW: Prepare Environment with Time Data ---
    # We copy the current env to preserve DISPLAY, PATH, etc.
    local_env = os.environ.copy()
    if duration:
        local_env["SONAR_DURATION"] = str(duration)
        local_env["SONAR_START_TIME"] = str(time.time())
    # -----------------------------------------------
    
    try:
        # Start the process
        if script_name == "logs.py":
             # Logs needs the pipe
             tail_proc = subprocess.Popen(
                ["tail", "-f", "/var/log/nginx/access.log"],
                stdout=subprocess.PIPE
            )
             proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=tail_proc.stdout,
                env=local_env  # <--- Pass the modified env
            )
        else:
             # Normal app (report.py)
             tail_proc = None
             # We pass local_env here too, though report.py doesn't use it yet
             proc = subprocess.Popen(
                 [sys.executable, str(script_path)],
                 env=local_env 
             )

        # Wait for duration or death
        if duration:
            try:
                proc.wait(timeout=duration * 60)
            except subprocess.TimeoutExpired:
                proc.terminate()
        else:
            proc.wait()

    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None: proc.terminate()
        if tail_proc: tail_proc.terminate()


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
                text = self.queue.get(timeout=1)
                self._speak_now(text)
                self.queue.task_done()
                time.sleep(0.5) 
            except queue.Empty:
                continue

    def _speak_now(self, text):
        """Internal method to actually generate and play audio."""
        # Note: We avoid print() here because it might corrupt the TUI layout
        model_path = MODEL_DIR / MODEL_NAME
        
        if not model_path.exists():
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
        except Exception:
            pass

    def stop(self):
        self.stop_event.set()

# Initialize Global Narrator
narrator = Narrator()

class Heartbeat(threading.Thread):
    """A background thread that queues the time every N seconds."""
    # CHANGED: Default interval to 90 seconds
    def __init__(self, interval=90):
        super().__init__()
        self.interval = interval
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self):
        while not self.stop_event.is_set():
            if self.stop_event.wait(self.interval):
                break
            
            now = datetime.datetime.now().strftime("%H:%M:%S")
            narrator.say(f"Signal check. The time is {now}.")

    def stop(self):
        self.stop_event.set()


def perform_show(script):
    """Reads the sheet music list and executes it."""
    # Define the environment for the browser once
    env = os.environ.copy()
    env["DISPLAY"] = ":10.0" 

    # --- NEW: Start the Timer ---
    start_time = time.time()
    duration_seconds = SHOW_DURATION_MINUTES * 60

    profile_dir = tempfile.mkdtemp(prefix="honeybot_fx_")
    
    try:
        for command, content in script:

            # --- The Timer Interrupt ---
            # If we exceed the duration, we return False to restart the cycle.
            # This allows the "Preamble" to run again in the next loop.
            if (time.time() - start_time) > duration_seconds:
                narrator.say("Cycle complete. Refreshing narrative feed.")
                # Close browser just in case
                try:
                    subprocess.run(["pkill", "firefox"], check=False)
                except: pass
                return False 
            
            # --- The Breaking News Interrupt ---
            # We check before every command.
            # If new content exists, we return False to signal "Abort & Restart"
            if check_for_updates():
                narrator.say("Interrupting program. Breaking news detected.")
                # Close browser just in case
                try:
                    subprocess.run(["pkill", "firefox"], check=False)
                except: pass
                return False 

            if command == "SAY":
                narrator.say(content)
                time.sleep(len(content) / 20)
                
            elif command == "VISIT":
                try:
                    subprocess.Popen(
                        [
                            "firefox", 
                            "--profile", profile_dir,  # <--- MAGIC: Use temp profile
                            "--no-remote",             # <--- Don't connect to existing instances
                            "--new-instance",          # <--- Force new process
                            content
                        ],
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
                    
            elif command == "WAIT":
                try: time.sleep(int(content))
                except: time.sleep(1)
                    
            elif command == "CLOSE":
                try: 
                    # We kill the specific firefox instance running on this profile if possible,
                    # but pkill is safer for the kiosk mode.
                    subprocess.run(["pkill", "firefox"], check=False)
                except: pass
    finally:
        # CLEANUP: Destroy the memory of this session
        try:
            shutil.rmtree(profile_dir)
        except:
            pass


def start_director_track():
    """The Script for the Show. Runs in parallel to the Log Stream."""
    time.sleep(5)
    
    while True:
        if show:
            # Generate a fresh script
            current_script = show.get_script()
            
            # Run the show. 
            # If perform_show returns False, it means "New Content Detected",
            # so the loop restarts immediately, generating a NEW script with the new article at top.
            perform_show(current_script)
            
        else:
            narrator.say("Error. Show module not found.")
            time.sleep(30)


def run_logs():
    """Launch the Logs visualizer."""
    # print("🌊 Launching Log Stream...") # Commented out to save TUI
    script_dir = Path(__file__).parent
    logs_script = script_dir / "logs.py"
    
    # Start the Heartbeat
    heartbeat = Heartbeat(interval=90)
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
        pass
    finally:
        heartbeat.stop()
        tail_proc.terminate()
        heartbeat.join(timeout=1)


def main():
    narrator.start()
    director = threading.Thread(target=start_director_track, daemon=True)
    director.start()

    # --- ONE CYCLE ONLY ---
    
    # 1. The Commercial Break (Report)
    narrator.say("Initiating analysis report.")
    # CHANGE: 0.2 -> 1.0 (Give it a full minute)
    run_tui_app("report.py", duration=1.0) 
    
    # 2. The Main Event (Logs)
    narrator.say("Switching to live feed.")
    
    # FIX: Use the variable!
    run_tui_app("logs.py", duration=SHOW_DURATION_MINUTES) 
    
    # 3. The Exit
    narrator.say("Cycle complete. Rebooting system.")
    narrator.stop()


if __name__ == "__main__":
    main()
