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
import requests
import subprocess
import threading
import shutil   # <--- Add this import
import tempfile # <--- Add this import
import queue
from pathlib import Path

# --- Configuration ---
SHOW_DURATION_MINUTES = 240  # Minutes for the big logfile stream
PITCH_INTERVAL = 600        # Seconds between "Station Identification" (Bumped to 10 mins so it doesn't get repetitive)

PITCH_TEXT = (
    "If you are tuning in and wondering what this cascading wall of code is... welcome to Honeybot. "
    "You are watching the live, real time heartbeat of a web server. Specifically, my personal website, Mike L E V dot eye N. "
    "Every time a human clicks a link, or an A I bot crawls a page, the server writes a single line of text to a log file. "
    "What is happening on your screen right now is a technique called tailing. "
    "The system is just watching the tail end of that text file and updating the screen the millisecond a new line is written. "
    "I am piping that text through a Python script to color code the patterns so it is easier to read. "
    "For example, Orange highlights indicate A I agents. "
    "If you keep your eyes peeled, you might see Anthropic's A I bots drop by. "
    "They are one of the only user agents out there explicitly negotiating for Markdown files instead of standard HTML. "
    "I broadcast this for one reason: to educate and demystify. "
    "When you put your website on a massive, faceless cloud hosting platform, they hide this raw, beautiful data from you. "
    "This server you are watching? It is hosted from home. You can do the exact same thing. "
    "You can own your hardware, control your server, and interact with the actual data of the internet without a corporate middleman getting in the way. "
    "This stream, and the automation behind it, is controlled by a project of mine called Pipulate. "
    "If you want to learn how to break away from the cloud, host your own stuff, and command your technology like this, check the links below. "
    "Until then, sit back, relax, and enjoy the live pulse of the web. "
    ""
)

# Station-ID breaks cycle through short "installments" instead of replaying one
# fixed spiel. Each entry is text to speak plus an optional ASCII-art key (which
# must exist in imports.ascii_displays.FIGURATE_REGISTRY) that pops over the
# stream in voice-order. The index resets on process restart (episodic, by
# design): whoever tunes in starts the Pipulate story near its top.
# Each station-break bead now drives the full brush set in voice-order:
#   card    -> Figlet title-card label (WINDOW card.py "<card>")
#   patronus-> ASCII art popup (registered FIGURATE key)
#   text    -> the spoken station-ID spiel (the abstract concept)
#   window  -> a data report TUI ("script.py" or "script.py:seconds") for proof
# Two beads establishes the pattern; they alternate forever as a loop. Order is
# priority: _station_index resets to 0 on restart, so bead 0 is highest-traffic.
STATION_SEGMENTS = [
    {
        "card": "THE ITCH",
        "patronus": "ai_stack_combo",
        "text": (
            "The Itch. Every useful tool starts with a genuine irritation. "
            "Python ships with batteries included, but not every itch has a battery yet. "
            "FastAPI scratched the A P I server itch, but it smuggled in the entire JavaScript industrial complex. "
            "The itch that remained was a Python-native local web app cockpit. "
            "FastHTML and HTMX performed the exorcism."
        ),
        "window": "education.py:30",
        "duration": 6.0,
    },
    {
        "card": "THE LENSES",
        "patronus": "player_piano",
        "text": (
            "The Lenses. Every layer in the stack is a lens that must be ground clean. "
            "Normalized Linux, Python, HTMX, FastHTML, and git. "
            "Each one is either pre-trained into the models or small enough to fit in a single prompt. "
            "The fewer the lenses, the sharper the focus."
        ),
        "window": "radar.py:30",
        "duration": 6.0,
    },
]

# Advances on each station break; wraps with modulo over STATION_SEGMENTS.
_station_index = 0

sys.path.append(str(Path(__file__).parent))

try:
    import show
    from content_loader import check_for_updates, check_standby
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
        # Track the live audio pipeline so interrupt() can kill it mid-sentence.
        self._proc_lock = threading.Lock()
        self._active_procs = []

    def say(self, text):
        """Add text to the speech queue."""
        self.queue.put(text)

    def patronus(self, payload):
        """Queue a visual cue so it fires in voice-order, not director-order."""
        self.queue.put(("PATRONUS", payload))

    def interrupt(self):
        """Preempt the voice: drop everything queued-but-unspoken and kill the
        audio playing RIGHT NOW, so an urgent line plays immediately instead of
        waiting behind the backlog (which is what caused the talk-over)."""
        try:
            while True:
                self.queue.get_nowait()
                self.queue.task_done()
        except queue.Empty:
            pass
        with self._proc_lock:
            for p in self._active_procs:
                try:
                    p.kill()
                except Exception:
                    pass
            self._active_procs = []

    def run(self):
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=1)
                if isinstance(item, tuple) and item and item[0] == "PATRONUS":
                    payload = item[1]
                    if isinstance(payload, dict):
                        conjure_patronus(payload.get("key", "white_rabbit"), duration=payload.get("duration", 3.5))
                    else:
                        conjure_patronus(str(payload))
                else:
                    self._speak_now(item)
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
            p3 = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
                stdin=p2.stdout,
                stderr=subprocess.DEVNULL
            )
            # Register the live pipeline so interrupt() can kill it mid-sentence.
            with self._proc_lock:
                self._active_procs = [p1, p2, p3]
            p3.wait()
        except Exception:
            pass
        finally:
            with self._proc_lock:
                self._active_procs = []

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


def wait_for_availability(url, timeout=60):
    """
    Checks for the PHYSICAL FILE existence first, then confirms via HTTP.
    This prevents the 404 race condition where Nginx serves before the file is flushed.
    """
    # Only check our own domain
    if "mikelev.in" not in url:
        return

    # Derive file path from URL
    # Example: https://mikelev.in/foo/ -> /home/mike/www/mikelev.in/_site/foo/index.html
    base_path = Path("/home/mike/www/mikelev.in/_site")
    slug = url.replace("https://mikelev.in/", "").strip("/")
    target_file = base_path / slug / "index.html"

    start_time = time.time()

    # PHASE 1: The Hard Wait (Give Jekyll a head start)
    # Jekyll takes time to even start writing.
    # If we check too fast, we might see the OLD file before it gets deleted/rebuilt.
    time.sleep(5)

    first_failure = True

    while (time.time() - start_time) < timeout:
        # Check 1: File System (The Source of Truth)
        if target_file.exists():
            # Check 2: HTTP (The Delivery Mechanism) - ensuring Nginx sees it too
            try:
                response = requests.head(url, timeout=2, verify=False)
                if response.status_code == 200:
                    if not first_failure:
                        narrator.say("Content generated. Rendering.")
                    return
            except:
                pass

        # Feedback
        if first_failure:
            narrator.say("New content detected. Waiting for static site generation.")
            first_failure = False

        time.sleep(5) # Reduced polling frequency

    narrator.say("Generation timed out. Proceeding with caution.")


def conjure_patronus(name, duration=3.5):
    """Launch the shared patronus renderer from a sheet-music directive."""
    safe_name = "".join(c for c in str(name).strip() if c.isalnum() or c in {"_", "-"})
    if not safe_name:
        safe_name = "white_rabbit"
    duration = max(0.75, min(60.0, float(duration)))

    site_root = Path(__file__).resolve().parents[1]
    python_code = (
        "import sys; "
        f"sys.path.insert(0, {str(site_root)!r}); "
        "from imports.ascii_displays import patronus; "
        f"patronus(sys.argv[1], duration={duration})"
    )
    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY") or ":10.0"

    try:
        subprocess.Popen(
            [sys.executable, "-c", python_code, safe_name],
            cwd=site_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
    except Exception:
        pass


def conjure_window(script_name, duration=30.0, columns=100, lines=30, args=None):
    """Process-flavored sibling to conjure_patronus.

    Keep the sheet-music API ("report.py" or "report.py:seconds") local to the
    Honeybot scripts folder, but delegate the actual overlay mechanics to the
    shared wand actuator in imports.ascii_displays. This keeps patronus and
    arbitrary command windows in parity.
    """
    safe_script = "".join(c for c in str(script_name).strip() if c.isalnum() or c in {"_", "-", "."})
    if not safe_script:
        return
    duration = max(0.75, min(600.0, float(duration)))

    script_dir = Path(__file__).resolve().parent
    script_path = script_dir / safe_script
    if not script_path.exists():
        return

    site_root = Path(__file__).resolve().parents[1]
    if str(site_root) not in sys.path:
        sys.path.insert(0, str(site_root))

    from imports.ascii_displays import conjure_window as shared_conjure_window

    cmd = [sys.executable, "-u", str(script_path)]
    if args:
        cmd += [str(a) for a in args]

    shared_conjure_window(
        cmd,
        duration=duration,
        columns=columns,
        lines=lines,
        cwd=str(script_dir),
        title="ConjureWindow",
        window_class="conjure_window_overlay",
        display=os.environ.get("DISPLAY") or ":10.0",
    )


def perform_show(script):
    """Reads the sheet music list and executes it."""
    # Define the environment for the browser once
    env = os.environ.copy()
    env["DISPLAY"] = ":10.0"


    # --- NEW: Start the Timer ---
    start_time = time.time()
    duration_seconds = SHOW_DURATION_MINUTES * 60

    # Initialize the Pitch Timer
    last_pitch_time = time.time()

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

            # --- The Deploy Stand-By Handshake ---
            # A fresh push rings the standby bell BEFORE the multi-second build.
            # Announce calmly ONCE, cut the current narration, and HOLD (silent) until
            # the completion bell rings — so the TTS doesn't thrash through the deploy.
            if check_standby():
                narrator.interrupt()  # cut current audio + flush the backlog
                narrator.say("Receiving updates. Things will go quiet for a few moments. Then I'll start reading again. Please stand by.")
                try:
                    subprocess.run(["pkill", "firefox"], check=False)
                except Exception:
                    pass
                # Hold narration until the deploy finishes (completion bell rings)
                # or we time out gracefully, then lead the next cycle with the new article.
                deadline = time.time() + 120
                while time.time() < deadline:
                    if check_for_updates():
                        break
                    time.sleep(2)
                return "BREAKING"

            # --- The Breaking News Interrupt ---
            # We check before every command.
            # A fresh push rang the bell; return "BREAKING" (not False) so the director
            # leads the NEXT cycle straight with the newest article, no station-ID spiel.
            if check_for_updates():
                narrator.interrupt()  # cut current audio + flush backlog, then preempt
                narrator.say("Breaking news detected.")
                # Close browser just in case
                try:
                    subprocess.run(["pkill", "firefox"], check=False)
                except: pass
                return "BREAKING"

            if command == "SAY":
                # --- The Pervasive Pitch (Station ID) ---
                # We check if it's been 3 minutes since the last explanation.
                # We insert it BEFORE the next sentence to preserve flow.
                if (time.time() - last_pitch_time) > PITCH_INTERVAL:
                    global _station_index
                    segment = STATION_SEGMENTS[_station_index % len(STATION_SEGMENTS)]
                    _station_index += 1
                    art_key = segment.get("patronus")
                    if art_key:
                        narrator.patronus({"key": art_key, "duration": segment.get("duration", 3.5)})
                    spiel = segment["text"]
                    narrator.say(spiel)
                    # We sleep to let the pitch play out before queuing the next sentence
                    time.sleep(len(spiel) / 18)
                    last_pitch_time = time.time()
                # ----------------------------------------

                narrator.say(content)
                time.sleep(len(content) / 20)

            elif command == "VISIT":
                # Ensure the page actually exists before showing it
                wait_for_availability(content)

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

            elif command == "PATRONUS":
                narrator.patronus(content)

            elif command == "WINDOW":
                # Pop a report TUI as a transient overlay OVER the live logs,
                # holding the director for its duration, then auto-dismiss.
                # content is "script.py" or "script.py:seconds".
                parts = str(content).split(":", 1)
                win_script = parts[0].strip()
                win_dur = 30.0
                if len(parts) > 1:
                    try:
                        win_dur = float(parts[1].strip())
                    except ValueError:
                        win_dur = 30.0
                conjure_window(win_script, duration=win_dur)

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

    breaking = False
    while True:
        if show:
            # Generate a fresh script. On a breaking-news restart we request a minimal
            # script that leads straight with the newest article, skipping the station-ID
            # preamble so a just-pushed piece is heard immediately.
            current_script = show.get_script(breaking=breaking)

            # perform_show returns "BREAKING" when a fresh push interrupted it (lead with
            # the new article next), False on a normal timer cycle (replay the full
            # preamble), or None on natural completion.
            result = perform_show(current_script)
            breaking = (result == "BREAKING")

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

    # --- THE SHOW SEQUENCE ---

    # PARKED: the sequential report prelude below is being re-homed as on-demand
    # station-break overlays, summoned via the WINDOW cue / `window` command and
    # paired with their own narration (the JS-trapdoor story over radar, the
    # AI-ingestion bars over education, etc). Left commented as hooks so the old
    # boot slideshow can be restored or cherry-picked later. The "Amazon and
    # Meta" line lives here with education.py on purpose — that's the report it
    # was always meant to narrate over.
    #
    # # Scene 1: The Executive Summary
    # narrator.say("Initiating daily traffic analysis. These are the top site-surfer useragents; human, AI or otherwise.")
    # run_tui_app("report.py", duration=0.5)  # 30 seconds
    #
    # # Scene: The Education Monitor
    # narrator.say("Did you know that Amazon and Meta are top content scrapers? ")
    # run_tui_app("education.py", duration=0.5) # 30 seconds
    #
    # # Scene: Semantic Routing
    # # narrator.say("Analyzing ingestion vectors. Who is using the front door, and who found the loading dock?")
    # run_tui_app("routing.py", duration=0.5) # 30 seconds
    #
    # # Scene: The Radar (Intelligence)
    # # narrator.say("A bulletproof JavaScript captcha was just implemented. Check back for updated reports.")
    # run_tui_app("radar.py", duration=0.5)   # 30 seconds

    # Scene 3: The Deep Stream (Logs)
    NARRATOR_SAYS = (
        "Now I read from the very website we monitor the bot activity on. "
        "This is the transition from SEO to AI Education. "
        "We are educating the AI about our content and the audience about AI. Leave me a comment. "
        "This streams 24 by 7 so I'm probably not there right now so check back for my reply. I try to answer everyone. "
        "Now sit back and enjoy storytime! "
    )
    narrator.say(NARRATOR_SAYS)

    # Station ID Logic Update: Reset the pitch timer here so it doesn't fire immediately
    # We rely on last_pitch_time being initialized in perform_show, but for the main loop:
    # (Since perform_show is independent, we just let logs.py run)

    run_tui_app("logs.py", duration=SHOW_DURATION_MINUTES)

    # Outro
    narrator.say("Cycle complete. Rebooting visualization sequence.")
    narrator.stop()


if __name__ == "__main__":
    main()
