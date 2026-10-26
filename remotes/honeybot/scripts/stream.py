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
import atexit
import fcntl
import signal
from pathlib import Path

# --- Process Singleton ---
STREAM_LOCK_PATH = "/tmp/honeybot-stream.py.lock"
_stream_lock_handle = None


def acquire_singleton_lock():
    """Ensure only one stream.py process owns the Honeybot visual/audio surface."""
    global _stream_lock_handle

    _stream_lock_handle = open(STREAM_LOCK_PATH, "w", encoding="utf-8")

    try:
        fcntl.flock(_stream_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("⚠️ Another stream.py already owns the Honeybot surface. Exiting duplicate child.", flush=True)
        sys.exit(0)

    _stream_lock_handle.seek(0)
    _stream_lock_handle.truncate()
    _stream_lock_handle.write(str(os.getpid()))
    _stream_lock_handle.flush()

    def _release_lock():
        try:
            fcntl.flock(_stream_lock_handle, fcntl.LOCK_UN)
            _stream_lock_handle.close()
        except Exception:
            pass

    atexit.register(_release_lock)


def register_signal_handlers():
    """Convert incoming SIGTERM signals into a KeyboardInterrupt to execute try-finally blocks."""
    def _handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _handler)


# --- Configuration ---
SHOW_DURATION_MINUTES = 240  # Minutes for the big logfile stream
PITCH_INTERVAL = 600        # Seconds between "Station Identification" (Bumped to 10 mins so it doesn't get repetitive)

# Spoken over tick.wav when `publish "msg"` rings .deploy_standby on Honeybot.
# Edit with `ytoutro edit` and audition locally on Prime with `ytoutro`.
STANDBY_INTRO_LINE = "Receiving updates. This broadcast is coming to an end."

STANDBY_LOOP_LINES = (
    "To hear the next article, visit YouTube dot com slash M I K E L E V I N slash live. "
    "If you get there too soon you might have to wait a bit and hit refresh to see the new live-stream appear, but it will be worth it.",
    "If you are actually here seeing this live-performance wrapping up at the time of first broadcast, then you are seeing something brand new.",
    "None of this is trained into the parametric memory of today's frontier models, meaning this is genuinely new information per Claude Shannon's second famous paper, A Mathematical Theory of Communication, in which he would tell you that anything that can be produced by prompting an A I that is built from its existing weights is not information. It is noise.",
    "This live-broadcast and the articles being read here are not that. "
    "The author is macheteing his way through the Noosphere of things being experimentally done for maybe the first time ever.",
    "This is The Signal. "
    "It may not be apparent to you right now, but this is the most unique thing you will see today, and if you tune in again later, then the next one will be the same -- and by that I mean different and equally new. "
    "Welcome to The Information.",
)


def load_standby_speech(stream_file=None):
    """Read (STANDBY_INTRO_LINE, STANDBY_LOOP_LINES) fresh from stream.py on disk via AST.

    Allows an rsynced update to stream.py to play on the very next .deploy_standby
    bell without requiring a stream.py process restart.
    """
    import ast
    intro = STANDBY_INTRO_LINE
    loop_lines = STANDBY_LOOP_LINES
    target = Path(stream_file) if stream_file else Path(__file__).resolve()
    try:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "STANDBY_INTRO_LINE":
                        val = ast.literal_eval(node.value)
                        if isinstance(val, str) and val.strip():
                            intro = val.strip()
                    elif isinstance(t, ast.Name) and t.id == "STANDBY_LOOP_LINES":
                        val = ast.literal_eval(node.value)
                        if isinstance(val, (tuple, list)) and val:
                            loop_lines = tuple(str(x) for x in val if str(x).strip())
    except Exception:
        pass
    return intro, loop_lines

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
# The forest roll (station-break beads) now lives in its own data module so it
# can be edited without touching this threading-heavy engine. Each bead is an
# ordered cue-list in the same SAY/PATRONUS/WINDOW grammar the trees use, played
# through the shared dispatch_cue (the cathedral-of-one collapse).
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from forest import STATION_SEGMENTS
except ImportError:
    STATION_SEGMENTS = []

# Advances on each station break; wraps with modulo over STATION_SEGMENTS.
_station_index = 0


def next_slot(anchor, interval, now):
    """THE COPPER LIST: the next grid slot strictly AFTER `now`, re-derived
    from `anchor` every call.

    A Copper WAIT does not mean "wait N seconds." It means "wait until the
    beam reaches this position," which is why a Copper list cannot accumulate
    error: it never carries a running total, it re-reads the master clock.
    This is that, in arithmetic.

    THE SLOT-SKIP IS THE POINT, NOT A ROUNDING ARTIFACT. If a station break
    overruns and eats the slot behind it, that slot is DROPPED, never queued
    -- the grid does not shift and the next break lands where it always would
    have. The beam does not wait for you. Contrast the old
    `last_pitch_time = time.time()` reset, which measured break-END to
    break-START and therefore added the break's own duration to every cycle
    forever.

    Anchored to perform_show's start_time rather than to a fixed wall-clock
    epoch ON PURPOSE: a global grid would fire a break within seconds of a
    stream restart, and the old code's comment says that is exactly what it
    was avoiding. Absolute derivation, local anchor -- both properties kept.
    """
    if now < anchor:
        return anchor + interval
    return anchor + (int((now - anchor) // interval) + 1) * interval


sys.path.append(str(Path(__file__).parent))

try:
    import score
    from content_loader import check_for_updates, check_standby, trigger_is_fresh, check_live_message
except ImportError:
    score = None
    def check_live_message():
        return None

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
        self._tts_seq = 0
        self.exclusive_mode = threading.Event()

    def _cleanup_item(self, item):
        """Remove any unplayed pre-synthesized .raw file when flushing the queue."""
        if isinstance(item, tuple) and len(item) >= 2 and item[0] == "RAW":
            raw_path = item[1]
            if raw_path and os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                except OSError:
                    pass

    def prep_raw(self, text):
        """Pre-synthesize narration into a back-buffer .raw PCM file before showing a card or advancing."""
        if not text:
            return None
        model_path = MODEL_DIR / MODEL_NAME
        if not model_path.exists() or not shutil.which("piper"):
            return None
        self._tts_seq += 1
        raw_path = f"/tmp/honeybot_tts_{os.getpid()}_{self._tts_seq}.raw"
        try:
            with open(raw_path, "wb") as out_f:
                res = subprocess.run(
                    ["piper", "--model", str(model_path), "--output_raw"],
                    input=text.strip().encode("utf-8"),
                    stdout=out_f,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
            if res.returncode == 0 and os.path.exists(raw_path) and os.path.getsize(raw_path) > 0:
                return raw_path
        except Exception:
            pass
        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass
        return None

    def play_raw(self, raw_path, fallback_text=""):
        """Enqueue a pre-synthesized .raw file for zero-latency playback, falling back to text."""
        if raw_path and os.path.exists(raw_path):
            self.queue.put(("RAW", str(raw_path)))
        elif fallback_text:
            self.queue.put(fallback_text)

    def say(self, text):
        """Add text to the speech queue."""
        self.queue.put(text)

    def patronus(self, payload):
        """Queue a visual cue so it fires in voice-order, not director-order."""
        self.queue.put(("PATRONUS", payload))

    def window(self, payload):
        """Queue a TUI report window overlay so it fires in voice-order on a daemon thread."""
        self.queue.put(("WINDOW", payload))

    def media(self, payload):
        """Queue an image or video popup overlay so it fires in voice-order on a daemon thread."""
        self.queue.put(("MEDIA", payload))

    def interrupt(self):
        """Preempt the voice: drop everything queued-but-unspoken and kill the
        audio playing RIGHT NOW, so an urgent line plays immediately instead of
        waiting behind the backlog (which is what caused the talk-over)."""
        try:
            while True:
                dropped_item = self.queue.get_nowait()
                self._cleanup_item(dropped_item)
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

    def flush_queue(self):
        """Soft sibling of interrupt(): drop the queued-but-unspoken backlog
        but DO NOT kill the audio playing right now. The in-progress line
        finishes cleanly, then the (now-empty) queue takes the next thing to
        say. Used for station breaks, which should never clip a word; the hard
        interrupt() stays reserved for genuinely urgent cuts (deploy/breaking).

        RETURNS THE COUNT DROPPED, because that count is the only available
        measurement of a magic number governing content loss. dispatch_cue
        paces the director with `time.sleep(len(content) / 20)` -- an ESTIMATE
        of Piper's speech rate -- while the Narrator takes however long Piper
        actually takes. Two unsynchronized clocks. If 20 ch/s runs fast the
        director outruns the voice, the queue grows, and everything in it is
        DELETED here rather than deferred: article text the listener never
        hears, once per station break, silently. A nonzero count is that loss,
        in items. A persistent zero retires the question."""
        dropped = 0
        try:
            while True:
                dropped_item = self.queue.get_nowait()
                self._cleanup_item(dropped_item)
                self.queue.task_done()
                dropped += 1
        except queue.Empty:
            pass
        return dropped

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
                elif isinstance(item, tuple) and item and item[0] == "WINDOW":
                    win_script, win_dur, win_args = item[1]
                    threading.Thread(
                        target=conjure_window,
                        args=(win_script,),
                        kwargs={"duration": win_dur, "args": win_args},
                        daemon=True,
                    ).start()
                    time.sleep(0.5)
                elif isinstance(item, tuple) and item and item[0] == "MEDIA":
                    threading.Thread(
                        target=conjure_media,
                        args=(item[1],),
                        daemon=True,
                    ).start()
                    time.sleep(0.5)
                elif isinstance(item, tuple) and item and item[0] == "RAW":
                    self._play_raw_now(item[1])
                else:
                    self._speak_now(item)
                self.queue.task_done()
                time.sleep(0.1)
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

    def _play_raw_now(self, raw_path):
        """Play a pre-synthesized .raw file immediately via aplay and unlink when done."""
        if not raw_path or not os.path.exists(raw_path):
            return
        try:
            p_play = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", str(raw_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with self._proc_lock:
                self._active_procs = [p_play]
            p_play.wait()
        except Exception:
            pass
        finally:
            with self._proc_lock:
                self._active_procs = []
            if os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                except OSError:
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

            if not narrator.exclusive_mode.is_set():
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


# --- The UPDATING Standby Sound (Non-copyright clock tick) ---
# Uses the CC0 assets/sounds/tick.wav shipped in the repo and synced via
# nixops.sh, replacing the retired copyright-flagged Jeopardy wav.
_TICK_CANDIDATES = (
    Path(__file__).resolve().parents[1] / "assets/sounds/tick.wav",
    Path(__file__).resolve().parents[3] / "assets/sounds/tick.wav",
)
MUSIC_FILE = next((p for p in _TICK_CANDIDATES if p.exists()), _TICK_CANDIDATES[0])
MUSIC_MARKER = "honeybot-updating-music"


def start_updating_music():
    """Loop the standby wav in its own PROCESS GROUP. aplay does not loop,
    and the wav (~30s) is far shorter than the standby window (up to ~4
    minutes), hence the while-loop shell wrapper -- which is exactly why the
    group kill matters: kill only the aplay and the shell resurrects it a
    beat later. The MUSIC_MARKER comment rides the command line so the
    idempotent pkill backstop can target this loop and ONLY this loop,
    never the Narrator's own Piper->aplay pipeline."""
    if not MUSIC_FILE.exists():
        return None
    try:
        return subprocess.Popen(
            ["sh", "-c", f'while :; do aplay -q -D default "{MUSIC_FILE}"; sleep 1; done # {MUSIC_MARKER}'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
    except Exception:
        return None


def stop_updating_music(proc):
    """Sharp cut: kill the whole process group (shell + in-flight aplay)."""
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass


MEDIA_OVERLAY_MARKER = "honeybot_media_overlay"


def _find_x11_lib(lib_name):
    """Locate libX11.so.6 or libXext.so.6 via ldd on wmctrl/xdotool/mpv (NixOS store-safe)."""
    for bin_name in ("wmctrl", "xdotool", "feh", "mpv"):
        bin_path = shutil.which(bin_name)
        if not bin_path:
            continue
        try:
            res = subprocess.run(
                ["ldd", bin_path],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            for line in (res.stdout or "").splitlines():
                if lib_name in line and "=>" in line:
                    rhs = line.split("=>", 1)[1].strip().split()[0]
                    if os.path.isfile(rhs):
                        return rhs
        except Exception:
            pass
    return lib_name


def _build_1bit_alpha_mask_stdlib(img_path, win_w, win_h, threshold=24):
    """Build an X11 XBM 1-bit LSB-first alpha mask using PIL if present or pure stdlib (zlib + struct)."""
    if not img_path or not os.path.isfile(img_path):
        return None
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            rgba = im.convert("RGBA")
            if rgba.size != (win_w, win_h):
                rgba = rgba.resize((win_w, win_h), Image.Resampling.LANCZOS)
            alpha_bytes = rgba.split()[3].tobytes()
        row_bytes = (win_w + 7) // 8
        mask_buf = bytearray(row_bytes * win_h)
        for y in range(win_h):
            row_off = y * win_w
            out_off = y * row_bytes
            for x in range(win_w):
                if alpha_bytes[row_off + x] > threshold:
                    mask_buf[out_off + (x >> 3)] |= 1 << (x & 7)
        return bytes(mask_buf)
    except Exception:
        pass
    try:
        import struct
        import zlib
        with open(img_path, "rb") as f:
            data = f.read()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        pos = 8
        src_w = src_h = bit_depth = color_type = interlace = 0
        trns = b""
        idat_parts = []
        while pos + 8 <= len(data):
            length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
            chunk = data[pos + 8:pos + 8 + length]
            pos += 12 + length
            if ctype == b"IHDR" and len(chunk) >= 13:
                src_w, src_h, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk[:13])
            elif ctype == b"tRNS":
                trns = chunk
            elif ctype == b"IDAT":
                idat_parts.append(chunk)
            elif ctype == b"IEND":
                break
        if bit_depth != 8 or interlace != 0 or color_type not in (6, 4, 3) or src_w <= 0 or src_h <= 0:
            return None
        bpp = 4 if color_type == 6 else (2 if color_type == 4 else 1)
        stride = src_w * bpp
        raw = zlib.decompress(b"".join(idat_parts))
        if len(raw) < src_h * (1 + stride):
            return None
        alpha_grid = bytearray(src_w * src_h)
        prev = bytearray(stride)
        cur = bytearray(stride)
        in_off = 0
        for y in range(src_h):
            flt = raw[in_off]
            in_off += 1
            line = raw[in_off:in_off + stride]
            in_off += stride
            if flt == 0:
                cur[:] = line
            elif flt == 1:
                for i in range(stride):
                    left = cur[i - bpp] if i >= bpp else 0
                    cur[i] = (line[i] + left) & 0xFF
            elif flt == 2:
                for i in range(stride):
                    cur[i] = (line[i] + prev[i]) & 0xFF
            elif flt == 3:
                for i in range(stride):
                    left = cur[i - bpp] if i >= bpp else 0
                    cur[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
            elif flt == 4:
                for i in range(stride):
                    a = cur[i - bpp] if i >= bpp else 0
                    b = prev[i]
                    c = prev[i - bpp] if i >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    cur[i] = (line[i] + pr) & 0xFF
            else:
                return None
            row_base = y * src_w
            if color_type == 6:
                alpha_grid[row_base:row_base + src_w] = cur[3::4]
            elif color_type == 4:
                alpha_grid[row_base:row_base + src_w] = cur[1::2]
            else:
                for x in range(src_w):
                    idx = cur[x]
                    alpha_grid[row_base + x] = trns[idx] if idx < len(trns) else 255
            prev[:] = cur
        row_bytes = (win_w + 7) // 8
        mask_buf = bytearray(row_bytes * win_h)
        for y in range(win_h):
            sy = (y * src_h) // win_h
            s_row = sy * src_w
            out_off = y * row_bytes
            for x in range(win_w):
                sx = (x * src_w) // win_w
                if alpha_grid[s_row + sx] > threshold:
                    mask_buf[out_off + (x >> 3)] |= 1 << (x & 7)
        return bytes(mask_buf)
    except Exception:
        return None


def _get_honeybot_screen_dimensions(env):
    """Query XFCE / X11 desktop size (screen_w, screen_h, origin_x, origin_y) on Honeybot :10.0."""
    import re
    q_env = env if env is not None else os.environ.copy()
    q_env["DISPLAY"] = q_env.get("DISPLAY") or ":10.0"
    if shutil.which("xrandr"):
        try:
            res = subprocess.run(
                ["xrandr", "--current"],
                env=q_env,
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            out = res.stdout or ""
            m_prim = re.search(r"\bconnected\s+primary\s+(\d+)x(\d+)\+(\d+)\+(\d+)\b", out)
            if not m_prim:
                m_prim = re.search(r"\bconnected\s+(\d+)x(\d+)\+(\d+)\+(\d+)\b", out)
            if m_prim:
                w, h, ox, oy = (int(m_prim.group(i)) for i in range(1, 5))
                if w > 0 and h > 0:
                    return w, h, ox, oy
        except Exception:
            pass
    if shutil.which("wmctrl"):
        try:
            res = subprocess.run(
                ["wmctrl", "-d"],
                env=q_env,
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            for line in (res.stdout or "").splitlines():
                if "*" in line:
                    m_dg = re.search(r"DG:\s*(\d+)x(\d+)", line)
                    if m_dg:
                        w, h = int(m_dg.group(1)), int(m_dg.group(2))
                        if w > 0 and h > 0:
                            return w, h, 0, 0
        except Exception:
            pass
    if shutil.which("xdotool"):
        try:
            res = subprocess.run(
                ["xdotool", "getdisplaygeometry"],
                env=q_env,
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            parts = (res.stdout or "").strip().split()
            if len(parts) >= 2:
                w, h = int(parts[0]), int(parts[1])
                if w > 0 and h > 0:
                    return w, h, 0, 0
        except Exception:
            pass
    try:
        import ctypes
        libX11 = ctypes.CDLL(_find_x11_lib("libX11.so.6"))
        libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        libX11.XOpenDisplay.restype = ctypes.c_void_p
        libX11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        libX11.XDefaultScreen.restype = ctypes.c_int
        libX11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
        libX11.XDisplayWidth.restype = ctypes.c_int
        libX11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        libX11.XDisplayHeight.restype = ctypes.c_int
        libX11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        dpy = libX11.XOpenDisplay(q_env["DISPLAY"].encode("utf-8"))
        if dpy:
            try:
                scr = libX11.XDefaultScreen(dpy)
                w = int(libX11.XDisplayWidth(dpy, scr))
                h = int(libX11.XDisplayHeight(dpy, scr))
                if w > 0 and h > 0:
                    return w, h, 0, 0
            finally:
                libX11.XCloseDisplay(dpy)
    except Exception:
        pass
    return 1920, 1080, 0, 0


def _apply_x11_shape_mask_honeybot(win_id, mask_bytes, win_w, win_h, env, pos_x=None, pos_y=None):
    """Apply a 1-bit cookie-cutter XShapeCombineMask and centered (pos_x, pos_y) to an X11 window ID on Honeybot."""
    if not win_id:
        return False
    try:
        import ctypes
        libX11 = ctypes.CDLL(_find_x11_lib("libX11.so.6"))
        libXext = ctypes.CDLL(_find_x11_lib("libXext.so.6"))
        libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        libX11.XOpenDisplay.restype = ctypes.c_void_p
        libX11.XMoveResizeWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint
        ]
        libX11.XCreateBitmapFromData.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint
        ]
        libX11.XCreateBitmapFromData.restype = ctypes.c_ulong
        libX11.XFreePixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        libX11.XFlush.argtypes = [ctypes.c_void_p]
        libX11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        libXext.XShapeCombineMask.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong, ctypes.c_int
        ]
        dpy = libX11.XOpenDisplay((env.get("DISPLAY") or ":10.0").encode("utf-8"))
        if not dpy:
            return False
        try:
            wid = int(str(win_id).strip(), 0)
            if pos_x is not None and pos_y is not None:
                libX11.XMoveResizeWindow(dpy, wid, int(pos_x), int(pos_y), int(win_w), int(win_h))
            if mask_bytes:
                bmap = libX11.XCreateBitmapFromData(dpy, wid, mask_bytes, int(win_w), int(win_h))
                if bmap:
                    libXext.XShapeCombineMask(dpy, wid, 0, 0, 0, bmap, 0)
                    libXext.XShapeCombineMask(dpy, wid, 2, 0, 0, bmap, 0)
                    libX11.XFreePixmap(dpy, bmap)
            libX11.XFlush(dpy)
            return True
        finally:
            libX11.XCloseDisplay(dpy)
    except Exception:
        return False


def _shape_honeybot_overlay_window(mask_bytes, win_w, win_h, env, pos_x=None, pos_y=None):
    """Find the honeybot_media_overlay window ID via xdotool, apply XShape mask, and center at (pos_x, pos_y)."""
    if not shutil.which("xdotool"):
        return ""
    for _ in range(10):
        try:
            res = subprocess.run(
                ["xdotool", "search", "--name", f"^{MEDIA_OVERLAY_MARKER}$"],
                env=env,
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
            if lines:
                wid = lines[-1]
                _apply_x11_shape_mask_honeybot(wid, mask_bytes, win_w, win_h, env, pos_x=pos_x, pos_y=pos_y)
                if pos_x is not None and pos_y is not None:
                    subprocess.run(
                        [
                            "xdotool", "windowsize", str(wid), str(win_w), str(win_h),
                            "windowmove", str(wid), str(pos_x), str(pos_y),
                        ],
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                return wid
        except Exception:
            pass
        time.sleep(0.05)
    return ""


def _read_image_dimensions(path):
    """Read (width, height) from PNG/GIF/JPEG header bytes using stdlib only."""
    import struct
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if len(head) >= 24 and head.startswith(b"\x89PNG\r\n\x1a\n") and head[12:16] == b"IHDR":
                w, h = struct.unpack(">II", head[16:24])
                if w > 0 and h > 0:
                    return int(w), int(h)
            if len(head) >= 10 and head[:6] in (b"GIF87a", b"GIF89a"):
                w, h = struct.unpack("<HH", head[6:10])
                if w > 0 and h > 0:
                    return int(w), int(h)
            if head.startswith(b"\xff\xd8"):
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        break
                    while marker[1] == 0xFF:
                        b = f.read(1)
                        if not b:
                            break
                        marker = bytes([0xFF, b[0]])
                    mtype = marker[1]
                    if mtype in (0xD8, 0xD9):
                        continue
                    len_bytes = f.read(2)
                    if len(len_bytes) < 2:
                        break
                    seg_len = struct.unpack(">H", len_bytes)[0]
                    if mtype in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        sof = f.read(5)
                        if len(sof) == 5:
                            h, w = struct.unpack(">HH", sof[1:5])
                            if w > 0 and h > 0:
                                return int(w), int(h)
                        break
                    f.seek(max(0, seg_len - 2), 1)
    except Exception:
        pass
    return 1440, 810


def _resolve_honeybot_media_target(raw_target):
    """Resolve a local path, shorthand key, site-relative '/assets/...' path, or URL on Honeybot."""
    s = str(raw_target or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "file://")):
        return s
    site_root = Path(__file__).resolve().parents[1]
    candidates = [
        Path(s).expanduser(),
        site_root / "_site" / s.lstrip("/"),
        site_root / s.lstrip("/"),
        Path("/home/mike/www/mikelev.in/_site") / s.lstrip("/"),
        Path("/home/mike/www/mikelev.in") / s.lstrip("/"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())
    needle = Path(s.lower()).stem
    if needle in ("seal", "wax", "ambigram", "ambigram-209", "default"):
        for seal_cand in (
            Path("/home/mike/www/mikelev.in/assets/weebo/ambigram-209.png"),
            site_root / "assets" / "weebo" / "ambigram-209.png",
            site_root / "assets" / "images" / "ambigram-209.png",
        ):
            if seal_cand.is_file():
                return str(seal_cand.resolve())
    search_dirs = [
        Path("/home/mike/www/mikelev.in/assets/weebo"),
        site_root / "assets" / "weebo",
        Path("/tmp/honeybot_media"),
    ]
    for d in search_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and (p.stem.lower() == needle or p.stem.lower().startswith(needle)):
                return str(p.resolve())
    return s


def conjure_media(media_spec, duration=15.0, mute=False, _direct=False):
    """Pop up an image or video over the Honeybot :10.0 stream using mpv, feh, or Firefox fallback."""
    if isinstance(media_spec, dict):
        raw_target = str(media_spec.get("path") or media_spec.get("url") or "").strip()
        duration = float(media_spec.get("duration", duration))
        mute = bool(media_spec.get("mute", mute))
    else:
        raw_str = str(media_spec or "").strip()
        if ":" in raw_str and not raw_str.startswith(("http://", "https://", "file://")):
            head, tail = raw_str.rsplit(":", 1)
            try:
                duration = float(tail.strip())
                raw_target = head.strip()
            except ValueError:
                raw_target = raw_str
        else:
            raw_target = raw_str
    target = _resolve_honeybot_media_target(raw_target)
    if not target:
        return
    duration = max(1.0, min(600.0, float(duration)))
    if not _direct:
        try:
            self_path = Path(__file__).resolve()
            if self_path.is_file() and "--conjure-media" in self_path.read_text(encoding="utf-8", errors="ignore"):
                sub_cmd = [sys.executable, str(self_path), "--conjure-media", str(target), f"{duration:.1f}"]
                if mute:
                    sub_cmd.append("--mute")
                subprocess.run(sub_cmd, timeout=duration + 5.0, check=False)
                return
        except Exception:
            pass
    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY") or ":10.0"
    ext = os.path.splitext(target.split("?", 1)[0])[1].lower()
    is_video = ext in (".mp4", ".webm", ".mkv", ".mov", ".gif")
    scr_w, scr_h, scr_ox, scr_oy = _get_honeybot_screen_dimensions(env)
    eff_max_w = min(1440, max(256, int(scr_w * 0.85)))
    eff_max_h = min(840, max(256, int(scr_h * 0.85)))
    img_w, img_h = _read_image_dimensions(target) if os.path.isfile(target) else (int(scr_w * 0.75), int(scr_h * 0.75))
    scale = min(1.0, eff_max_w / max(1, img_w), eff_max_h / max(1, img_h))
    win_w = max(16, int(round(img_w * scale)))
    win_h = max(16, int(round(img_h * scale)))
    pos_x = max(0, (scr_ox + (scr_w // 2)) - (win_w // 2))
    pos_y = max(0, (scr_oy + (scr_h // 2)) - (win_h // 2))

    proc = None
    tmp_profile = None
    try:
        try:
            subprocess.run(["pkill", "-f", MEDIA_OVERLAY_MARKER], check=False)
        except Exception:
            pass
        if is_video and shutil.which("mpv"):
            cmd = [
                "mpv",
                "--no-config",
                f"--title={MEDIA_OVERLAY_MARKER}",
                "--no-border",
                "--ontop",
                f"--geometry={win_w}x{win_h}+{pos_x}+{pos_y}",
                "--keep-open=no",
                "--really-quiet",
            ]
            if ext == ".gif":
                cmd.extend(["--loop-file=inf", f"--length={duration:.1f}"])
            else:
                cmd.append(f"--length={duration:.1f}")
                if mute:
                    cmd.append("--mute=yes")
            cmd.append(target)
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wid = _shape_honeybot_overlay_window(None, win_w, win_h, env, pos_x=pos_x, pos_y=pos_y)
            target_flag = ["-i", "-r", str(wid)] if wid else ["-r", MEDIA_OVERLAY_MARKER]
            subprocess.run(["wmctrl", *target_flag, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"], env=env, check=False)
            subprocess.run(["wmctrl", *target_flag, "-b", "add,above"], env=env, check=False)
            proc.wait(timeout=duration + 2.0)
        elif shutil.which("mpv"):
            alpha_arg = []
            for cand_flags in (["--gpu-context=x11egl", "--background=none"], ["--alpha=yes"], ["--background=none"]):
                if subprocess.run(["mpv", "--no-config", *cand_flags, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
                    alpha_arg = cand_flags
                    break
            cmd = [
                "mpv",
                "--no-config",
                f"--title={MEDIA_OVERLAY_MARKER}",
                "--no-border",
                "--ontop",
                *alpha_arg,
                f"--geometry={win_w}x{win_h}+{pos_x}+{pos_y}",
                f"--image-display-duration={duration:.1f}",
                "--keep-open=no",
                "--really-quiet",
                target,
            ]
            mask_bytes = _build_1bit_alpha_mask_stdlib(target, win_w, win_h) if target.lower().endswith(".png") else None
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wid = _shape_honeybot_overlay_window(mask_bytes, win_w, win_h, env, pos_x=pos_x, pos_y=pos_y)
            target_flag = ["-i", "-r", str(wid)] if wid else ["-r", MEDIA_OVERLAY_MARKER]
            subprocess.run(
                ["wmctrl", *target_flag, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"],
                env=env,
                check=False,
            )
            subprocess.run(["wmctrl", *target_flag, "-b", "add,above"], env=env, check=False)
            proc.wait(timeout=duration + 2.0)
        elif not is_video and shutil.which("feh") and not target.startswith(("http://", "https://")):
            img_w, img_h = _read_image_dimensions(target) if os.path.isfile(target) else (1440, 810)
            max_w, max_h = 1440, 840
            scale = min(max_w / max(1, img_w), max_h / max(1, img_h))
            win_w = max(256, int(round(img_w * scale)))
            win_h = max(256, int(round(img_h * scale)))
            pos_x = max(0, (1920 - win_w) // 2)
            pos_y = max(0, (1080 - win_h) // 2)
            cmd = [
                "feh",
                "--title", MEDIA_OVERLAY_MARKER,
                "--borderless",
                "--image-bg", "black",
                "--auto-zoom",
                "--scale-down",
                "--geometry", f"{win_w}x{win_h}+{pos_x}+{pos_y}",
                target,
            ]
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.35)
            subprocess.run(
                ["wmctrl", "-r", MEDIA_OVERLAY_MARKER, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"],
                env=env,
                check=False,
            )
            subprocess.run(["wmctrl", "-r", MEDIA_OVERLAY_MARKER, "-b", "add,above"], env=env, check=False)
            proc.wait(timeout=duration)
        elif shutil.which("firefox"):
            tmp_profile = tempfile.mkdtemp(prefix=f"{MEDIA_OVERLAY_MARKER}_")
            uri = target if target.startswith(("http://", "https://", "file://")) else Path(target).resolve().as_uri()
            proc = subprocess.Popen(
                ["firefox", "--profile", tmp_profile, "--no-remote", "--new-instance", uri],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.8)
            subprocess.run(["wmctrl", "-r", "Mozilla Firefox", "-b", "add,fullscreen,above"], env=env, check=False)
            proc.wait(timeout=duration)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    finally:
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if tmp_profile and os.path.isdir(tmp_profile):
            shutil.rmtree(tmp_profile, ignore_errors=True)


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
    from imports.ascii_displays import measure_figlet

    # --- 80/20 PULL-TIGHT FOR FIGLET CARDS ---
    # card.py renders a single Figlet banner, and a Figlet footprint is fully
    # deterministic and measurable parent-side -- exactly how patronus() sizes
    # its popup around registered ASCII art. Do the same here: measure the
    # banner BEFORE launch and shrink the Alacritty box around it. The child
    # cannot resize a box whose columns/lines are already baked into the launch
    # command, so the measurement MUST happen out here in the parent.
    #
    # Cushion is intentionally smaller than patronus's +20: a Figlet has no
    # internal line-length ambiguity to guard against, but a few spare cells
    # still keep terminal cell-rounding from wrapping the widest banner row.
    # card.py vertically centers the banner, so matching the box height to the
    # banner (+ a little) is what makes it sit snug instead of floating in dead
    # space.
    #
    # FUTURE (combined card): a card will eventually carry a Figlet banner on
    # top AND figurate ASCII art BELOW it on the same surface -- the framing is
    # "a Figlet banner with an optional ASCII-art body," with card.py as the
    # home that grows a body (rather than the patronus path growing a label).
    # When that lands, render banner + art, measure the UNION of the two
    # footprints (max width, summed heights), and size the box to that. The
    # measure-then-fit pattern generalizes cleanly from one block to two stacked
    # ones.
    if safe_script == "card.py" and args:
        fig_w, fig_h = measure_figlet(str(args[0]))
        columns = max(60, fig_w + 8)
        lines = max(14, fig_h + 4)
        cmd = [sys.executable, "-u", str(script_path)] + [str(a) for a in args]
    elif safe_script == "forest.py":
        columns = 110
        lines = 34
        mode_arg = str(args[0]).strip() if args else "overview"
        ansi_path = None
        try:
            from forest import prerender_station_report_ansi
            ansi_path = prerender_station_report_ansi(mode=mode_arg, width=columns - 2)
        except Exception:
            ansi_path = None
        if ansi_path and os.path.isfile(ansi_path):
            try:
                ansi_lines = len(Path(ansi_path).read_text(encoding="utf-8").splitlines())
                lines = max(lines, ansi_lines + 2)
            except Exception:
                pass
            cmd = [
                "sh",
                "-c",
                f'printf "\\033[?25l"; cat "{ansi_path}"; sleep {max(1.0, float(duration)):.1f}',
            ]
        else:
            cmd = [sys.executable, "-u", str(script_path), mode_arg]
    else:
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


_card_seq = 0


def show_card(label, max_hold=60.0):
    """Display a transient Figlet title card window on Honeybot until dismiss_card(handle)."""
    if not label:
        return None
    global _card_seq
    _card_seq += 1
    stop_file = f"/tmp/honeybot_card_{os.getpid()}_{_card_seq}.stop"
    if os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except OSError:
            pass
    label_str = str(label).replace("\\n", "\n")

    def _run():
        try:
            conjure_window("card.py", duration=max_hold, args=[label_str, str(max_hold), stop_file])
        except Exception:
            pass

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return {"stop_file": stop_file, "thread": th}


def dismiss_card(handle):
    """Dismiss a running card window cleanly via its stop_file."""
    if not handle:
        return
    stop_file = handle.get("stop_file")
    th = handle.get("thread")
    if stop_file:
        try:
            with open(stop_file, "w", encoding="utf-8") as f:
                f.write("done\n")
        except OSError:
            pass
    if th:
        th.join(timeout=1.0)
    if stop_file and os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except OSError:
            pass


def resolve_current_article_line():
    """Return the spoken Beat 3 announcement naming the article currently being read."""
    title = "our latest technical journal entry"
    try:
        from content_loader import get_playlist
        articles = get_playlist(recent_n=1, include_archive=False)
        if articles and articles[0].get("title"):
            title = str(articles[0]["title"])
    except Exception:
        pass
    return (
        f"The article currently being read on this broadcast is titled: {title}. "
        "To read the full article text and inspect the raw code receipts at your own pace, "
        "visit Mike L E V dot eye N slash latest."
    )


def dispatch_cue(command, content, env, profile_dir, pace_say=True):
    """Play one sheet-music cue through the brush set.

    Shared by the article roll (trees) and the station-break roll (forest), so
    the forest inherits the full SAY/PATRONUS/WINDOW/VISIT/WAIT/CLOSE grammar.
    Deliberately contains NO station-break trigger; that loop-control logic
    stays in perform_show's main loop.

    pace_say=True (trees): after queuing speech, sleep an estimate so the
        director paces roughly with the voice. pace_say=False (forest): do NOT
        sleep here -- run_station_break brackets the bead with interrupt() and
        queue.join() so a report WINDOW can overlap the spiel in real voice-time.
    """
    if command == "SAY":
        if isinstance(content, str) and "{CURRENT_ARTICLE}" in content:
            content = content.replace("{CURRENT_ARTICLE}", resolve_current_article_line())
        if pace_say:
            # Double-buffered synthesis: pre-render the next paragraph while the
            # previous paragraph is still playing on aplay, then synchronize on
            # the real voice clock so the director never outruns the voice.
            raw_path = narrator.prep_raw(content)
            if raw_path is not None:
                wait_for_voice_or_live_interrupt(env, profile_dir)
                narrator.play_raw(raw_path, fallback_text=content)
            else:
                narrator.say(content)
                time.sleep(len(content) / 20)
        else:
            narrator.say(content)

    elif command == "CARD":
        if isinstance(content, dict):
            label = content.get("label", "HONEYBOT")
            say_text = content.get("say", "")
            hold = float(content.get("duration", 60.0))
            linger = float(content.get("linger", 0.0))
            pre_raw = content.get("raw_path")
        else:
            label = str(content)
            say_text = ""
            hold = 60.0
            linger = 0.0
            pre_raw = None
        narrator.queue.join()
        raw_path = pre_raw if pre_raw is not None else (narrator.prep_raw(say_text) if say_text else None)
        card_handle = show_card(label, max_hold=hold)
        try:
            time.sleep(0.2)
            if say_text:
                narrator.play_raw(raw_path, fallback_text=say_text)
                narrator.queue.join()
                if linger > 0:
                    time.sleep(linger)
            else:
                time.sleep(min(hold, max(2.5, linger)))
        finally:
            dismiss_card(card_handle)

    elif command == "VISIT":
        # Ensure the page actually exists before showing it
        wait_for_availability(content)
        try:
            subprocess.Popen(
                [
                    "firefox",
                    "--profile", profile_dir,
                    "--no-remote",
                    "--new-instance",
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

    elif command in ("MEDIA", "IMAGE", "VIDEO"):
        if not pace_say:
            narrator.media(content)
        else:
            conjure_media(content)

    elif command == "WINDOW":
        # Grammar: "script.py" | "script.py:seconds" | "script.py:seconds:arg".
        # Queued via narrator.window() when pace_say=False so station-break
        # report windows pop in voice-order and never block subsequent SAY cues.
        parts = str(content).split(":", 2)
        win_script = parts[0].strip()
        win_dur = 30.0
        win_args = None
        if len(parts) > 1 and parts[1].strip():
            try:
                win_dur = float(parts[1].strip())
            except ValueError:
                win_dur = 30.0
        if len(parts) > 2 and parts[2].strip():
            win_args = [parts[2].strip()]
        if not pace_say:
            narrator.window((win_script, win_dur, win_args))
        else:
            conjure_window(win_script, duration=win_dur, args=win_args)

    elif command == "WAIT":
        try:
            time.sleep(int(content))
        except Exception:
            time.sleep(1)

    elif command == "CLOSE":
        try:
            subprocess.run(["pkill", "firefox"], check=False)
        except Exception:
            pass


_in_live_message = False


def run_live_message(msg, env, profile_dir):
    """Preempt article narration for a live operator break-in, blocking audio
    and Z-axis stomping until the operator's card and speech complete.

    When msg is a silent media-only popup (e.g. `weeboh 4`), pop the media
    overlay on a daemon thread without interrupting the active voice narration.
    """
    global _in_live_message
    if not msg or _in_live_message:
        return
    if (
        isinstance(msg, dict)
        and msg.get("media")
        and not str(msg.get("say") or "").strip()
        and not str(msg.get("card") or "").strip()
        and not msg.get("patronus")
        and not msg.get("window")
        and not msg.get("cues")
    ):
        try:
            subprocess.run(["pkill", "-f", MEDIA_OVERLAY_MARKER], check=False)
        except Exception:
            pass
        threading.Thread(
            target=conjure_media,
            args=(msg.get("media"),),
            kwargs={"duration": float(msg.get("linger", 8.0))},
            daemon=True,
        ).start()
        return
    _in_live_message = True
    was_exclusive = narrator.exclusive_mode.is_set()
    narrator.exclusive_mode.set()
    try:
        t_cut = time.time()
        narrator.interrupt()
        for pat in ("conjure_window_overlay", "patronus_visual_shield", MEDIA_OVERLAY_MARKER):
            try:
                subprocess.run(["pkill", "-f", pat], check=False)
            except Exception:
                pass
        pre_pause = float(msg.get("pre_pause", 3.0)) if isinstance(msg, dict) else 3.0
        linger = float(msg.get("linger", 2.5)) if isinstance(msg, dict) else 2.5
        cues = msg.get("cues") if isinstance(msg, dict) else None
        if isinstance(cues, list) and cues:
            rem = pre_pause - (time.time() - t_cut)
            if rem > 0:
                time.sleep(rem)
            for cue_cmd, cue_val in cues:
                dispatch_cue(cue_cmd, cue_val, env, profile_dir, pace_say=True)
            narrator.queue.join()
            return
        card_label = msg.get("card", "") if isinstance(msg, dict) else "LIVE\\nFROM MIKE"
        say_text = msg.get("say", "") if isinstance(msg, dict) else str(msg)
        patronus_key = msg.get("patronus") if isinstance(msg, dict) else None
        media_spec = msg.get("media") if isinstance(msg, dict) else None
        window_spec = msg.get("window") if isinstance(msg, dict) else None
        hold = float(msg.get("duration", 120.0)) if isinstance(msg, dict) else 120.0
        # Pre-synthesize during the pre-banner silence so the 3.0s palate cleanser
        # absorbs Piper synthesis time and the banner speaks the instant it pops.
        raw_path = narrator.prep_raw(say_text) if say_text else None
        rem = pre_pause - (time.time() - t_cut)
        if rem > 0:
            time.sleep(rem)
        if patronus_key or media_spec or window_spec:
            if card_label:
                dispatch_cue("CARD", {"label": card_label, "say": "", "duration": 2.5, "linger": 2.5}, env, profile_dir, pace_say=True)
            if patronus_key:
                conjure_patronus(patronus_key, duration=hold)
            elif media_spec:
                threading.Thread(
                    target=conjure_media,
                    args=(media_spec,),
                    kwargs={"duration": hold},
                    daemon=True,
                ).start()
                time.sleep(0.4)
            elif window_spec:
                threading.Thread(
                    target=dispatch_cue,
                    args=("WINDOW", window_spec, env, profile_dir),
                    kwargs={"pace_say": True},
                    daemon=True,
                ).start()
                time.sleep(0.4)
            if say_text:
                narrator.play_raw(raw_path, fallback_text=say_text)
                narrator.queue.join()
                if linger > 0:
                    time.sleep(linger)
            else:
                time.sleep(min(hold, max(6.0, linger)))
            for pat in ("patronus_visual_shield", "conjure_window_overlay", MEDIA_OVERLAY_MARKER):
                try:
                    subprocess.run(["pkill", "-f", pat], check=False)
                except Exception:
                    pass
        else:
            dispatch_cue(
                "CARD",
                {
                    "label": card_label or "LIVE\\nFROM MIKE",
                    "say": say_text,
                    "duration": hold,
                    "linger": linger,
                    "raw_path": raw_path,
                },
                env,
                profile_dir,
                pace_say=True,
            )
    finally:
        _in_live_message = False
        if not was_exclusive:
            narrator.exclusive_mode.clear()


def wait_for_voice_or_live_interrupt(env, profile_dir):
    """Wait for the active voice queue to drain while polling for a live operator break-in."""
    while True:
        if not _in_live_message:
            live_msg = check_live_message()
            if live_msg:
                run_live_message(live_msg, env, profile_dir)
        with narrator.queue.all_tasks_done:
            if narrator.queue.unfinished_tasks == 0:
                return
            narrator.queue.all_tasks_done.wait(timeout=0.15)


def run_station_break(env, profile_dir):
    """Play the next forest bead as an out-of-band station break.

    Preempt the voice (flush the article backlog), run the bead's cue-list
    through the shared dispatcher with queue-paced speech so the proof WINDOW
    overlaps the spiel, then wait on the real voice clock before resuming the
    article. No-ops gracefully if the forest module failed to import.
    """
    global _station_index
    if not STATION_SEGMENTS:
        return
    bead = STATION_SEGMENTS[_station_index % len(STATION_SEGMENTS)]
    _station_index += 1

    # --- Stage 1: The Soft Preemption ---
    # flush_queue (not interrupt) so the article sentence playing RIGHT NOW
    # finishes instead of being clipped mid-word -- only the queued backlog is
    # dropped. The queue.join() below then rides the real voice clock, so the
    # lead-in lands after the current line ends, not on top of it.
    narrator.exclusive_mode.set()
    try:
        dropped = narrator.flush_queue()
        if dropped:
            # MEANINGFUL SILENCE OVER UNCONDITIONAL CHATTER: gated on the
            # interesting case, so a healthy pipeline says nothing and an unhealthy
            # one says exactly how unhealthy. Deliberately NOT added to interrupt()
            # -- there, dropping the backlog is the INTENT (you are cutting to
            # breaking news); here it is collateral.
            print(f"📉 STATION BREAK DROPPED {dropped} unspoken item(s) -- "
                  f"director ran ahead of the voice; that text was never heard.")
        narrator.say("We interrupt this program for a station identification break.")
        narrator.queue.join()
        time.sleep(1.2)
        for cue_command, cue_content in bead:
            dispatch_cue(cue_command, cue_content, env, profile_dir, pace_say=False)
        wait_for_voice_or_live_interrupt(env, profile_dir)
        for pat in ("patronus_visual_shield", "conjure_window_overlay", MEDIA_OVERLAY_MARKER):
            try:
                subprocess.run(["pkill", "-f", pat], check=False)
            except Exception:
                pass
        time.sleep(1.2)
        narrator.say("We now return to our regularly scheduled program.")
        wait_for_voice_or_live_interrupt(env, profile_dir)
        time.sleep(1.2)
    finally:
        narrator.exclusive_mode.clear()


REBOOT_ANNOUNCEMENT_TEXT = (
    "Scheduled four hour station reset. "
    "Honeybot is about to perform a routine five second memory refresh and restart the broadcast loop. "
    "Do not adjust your set. The live stream will stay connected and storytime will resume in just a few seconds."
)
_reboot_announced = False


def announce_scheduled_reboot():
    """Announce the 4-hour memory-purging restart with a Figlet card and blocking TTS before exiting."""
    global _reboot_announced
    if _reboot_announced:
        return
    _reboot_announced = True
    narrator.exclusive_mode.set()
    try:
        narrator.interrupt()
        for pat in ("conjure_window_overlay", "patronus_visual_shield", MEDIA_OVERLAY_MARKER, "firefox"):
            try:
                subprocess.run(["pkill", "-f", pat], check=False)
            except Exception:
                pass
        raw_path = narrator.prep_raw(REBOOT_ANNOUNCEMENT_TEXT)
        card_handle = show_card("SCHEDULED\nREBOOT", max_hold=45.0)
        try:
            time.sleep(0.2)
            narrator.play_raw(raw_path, fallback_text=REBOOT_ANNOUNCEMENT_TEXT)
            narrator.queue.join()
            time.sleep(1.5)
        finally:
            dismiss_card(card_handle)
    except Exception:
        pass


def perform_show(script):
    """Reads the sheet music list and executes it."""
    # Idempotent safety net: whenever we start performing ANY fresh script --
    # normal playlist progression, a breaking-news restart, anything -- make
    # sure no stale "UPDATING" sentinel card is still lingering on screen.
    # This is a no-op the vast majority of the time, since the deploy-standby
    # handshake below already tears the card down deterministically the
    # instant the completion bell rings. It only does real work if that
    # earlier teardown somehow failed to land -- which is exactly the failure
    # case this exists to bound: the card cannot outlive more than one cycle.
    try:
        subprocess.run(["pkill", "-f", "card.py.*UPDATING"], check=False)
    except Exception:
        pass
    # Same idempotent backstop for the standby music loop. The marker is
    # baked into that loop's sh -c command line, so this cannot touch the
    # narrator's own aplay processes -- it only reaps an orphaned jukebox.
    try:
        subprocess.run(["pkill", "-f", MUSIC_MARKER], check=False)
    except Exception:
        pass

    # Define the environment for the browser once
    env = os.environ.copy()
    env["DISPLAY"] = ":10.0"


    # --- NEW: Start the Timer ---
    start_time = time.time()
    duration_seconds = SHOW_DURATION_MINUTES * 60

    # THE PITCH GRID. Derived from start_time, which is set two lines above and
    # never reset -- the same anchored-once pattern the cycle timer and the
    # standby deadline already use in this file. The first slot is one full
    # PITCH_INTERVAL out, preserving the old behavior of never forcing a break
    # immediately on a fresh restart cycle.
    next_pitch_time = next_slot(start_time, PITCH_INTERVAL, start_time)

    profile_dir = tempfile.mkdtemp(prefix="honeybot_fx_")

    try:
        for command, content in script:

            # --- The Timer Interrupt ---
            # If we exceed the duration, announce the scheduled reboot and return False.
            if (time.time() - start_time) > duration_seconds:
                announce_scheduled_reboot()
                return False

            # --- The Deploy Stand-By Handshake ---
            # A fresh push rings the standby bell BEFORE the multi-second build.
            # Announce calmly ONCE, cut the current narration, and HOLD (silent) until
            # the completion bell rings -- so the TTS doesn't thrash through the deploy.
            if check_standby():
                standby_intro_line, standby_loop_lines = load_standby_speech()
                was_exclusive = narrator.exclusive_mode.is_set()
                narrator.exclusive_mode.set()
                # The outer `duration` here is a generous LAST-RESORT ceiling, not
                # the thing that's supposed to close this window. The deterministic
                # close is the pkill below, fired the instant check_for_updates()
                # proves the deploy is actually done -- never a guessed elapsed time.
                #
                # CRITICAL: launch on a DAEMON THREAD. conjure_window() (in
                # imports/ascii_displays.py) is BLOCKING -- it bottoms out in
                # proc.wait(timeout=duration). Called inline, it froze this entire
                # loop for the full duration, starving the check_for_updates() poll
                # below and leaving the UPDATING banner stuck on screen (narration
                # silent) until the self-cap expired -- the "never resumes without
                # --reboot" bug. Threaded, the poll keeps running and the pkill
                # tears the card down the instant the completion bell rings: pkill
                # ends card.py, alacritty exits, proc.wait returns, the thread dies.
                updating_card = None
                music_proc = None
                try:
                    narrator.interrupt()  # cut current audio + flush the backlog
                    narrator.say(standby_intro_line)
                    for line in standby_loop_lines:
                        narrator.say(line)
                    updating_card = show_card("UPDATING", max_hold=270.0)
                    # Card up -> music up. Born at the same instant as the
                    # UPDATING figlet; dies at the same deterministic teardown
                    # below. PipeWire mixes it under the standby announcement,
                    # broadcast-style.
                    music_proc = start_updating_music()
                    try:
                        subprocess.run(["pkill", "firefox"], check=False)
                    except Exception:
                        pass
                    # Hold narration until the deploy finishes (completion bell rings)
                    # or we time out gracefully, refilling the standby speech queue
                    # whenever it drains so the message genuinely loops until teardown.
                    deadline = time.time() + 240
                    bell_rang = False
                    while time.time() < deadline:
                        if check_for_updates():
                            bell_rang = True
                            break
                        if narrator.queue.unfinished_tasks == 0:
                            for line in standby_loop_lines:
                                narrator.say(line)
                        time.sleep(2)
                    # If the trigger bell rang, hold the UPDATING card up while Jekyll/dye/
                    # Nix activity fully settles. The card disappears exactly when the article
                    # starts reading, with nothing competing for CPU/disk.
                    # Tune SETTLE_SECONDS upward if nixos-rebuild switch is still thrashing.
                    SETTLE_SECONDS = 45
                    if bell_rang:
                        settle_deadline = time.time() + SETTLE_SECONDS
                        while time.time() < settle_deadline:
                            if narrator.queue.unfinished_tasks == 0:
                                for line in standby_loop_lines:
                                    narrator.say(line)
                            time.sleep(1)
                finally:
                    # Tear down the dead-air cover and cut any in-flight standby
                    # speech deterministically the moment we exit standby.
                    narrator.interrupt()
                    stop_updating_music(music_proc)
                    dismiss_card(updating_card)
                    if not was_exclusive:
                        narrator.exclusive_mode.clear()
                    try:
                        subprocess.run(["pkill", "-f", "card.py.*UPDATING"], check=False)
                    except Exception:
                        pass
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

            # One dispatcher, two rolls. Loop-control (timer, standby, breaking
            # news) stays above; the station-break trigger stays here; the brush
            # primitives live in dispatch_cue, shared by the article roll (trees)
            # and the forest roll (STATION_SEGMENTS beads in forest.py).
            live_msg = check_live_message()
            if live_msg:
                run_live_message(live_msg, env, profile_dir)
            if command == "SAY" and time.time() >= next_pitch_time:
                # The Pervasive Pitch: play a forest bead as a station break
                # BEFORE the triggering sentence, preserving the article's flow.
                run_station_break(env, profile_dir)
                # RE-DERIVE, NEVER ACCUMULATE. The old line reset the timer to
                # "now" AFTER the break returned, so every cycle silently grew
                # by the break's own duration (~90-120s of real voice time per
                # bead) plus whatever overshoot the SAY-only check added. Over
                # a 240-minute show that is roughly four lost breaks, each at a
                # wandering position. next_slot() reads the grid instead.
                next_pitch_time = next_slot(start_time, PITCH_INTERVAL, time.time())

            dispatch_cue(command, content, env, profile_dir, pace_say=True)
    finally:
        # CLEANUP: Destroy the memory of this session
        try:
            shutil.rmtree(profile_dir)
        except:
            pass


def start_director_track():
    """The Script for the Show. Runs in parallel to the Log Stream."""
    time.sleep(5)

    # A publish-triggered restart (the [4/4] kill in flake.nix) births a fresh
    # process while .reading_trigger is still warm. Lead the very first cycle with
    # the newest article -- the breaking path Probe 2 already validated end to end --
    # instead of the cold "Greetings, entity" preamble. If content_loader failed to
    # import, score is None and the conditional short-circuits to False before
    # trigger_is_fresh is ever looked up; a stale or absent trigger also yields
    # False, leaving a genuine idle cold start completely unchanged.
    breaking = trigger_is_fresh() if score else False
    while True:
        if score:
            # Generate a fresh script. On a breaking-news restart we request a minimal
            # script that leads straight with the newest article, skipping the station-ID
            # preamble so a just-pushed piece is heard immediately.
            current_script = score.get_script(breaking=breaking)

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
    # Meta" line lives here with education.py on purpose -- that's the report it
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

    # Outro: announce the 4-hour scheduled restart on-air and wait for speech to finish before exiting
    announce_scheduled_reboot()
    narrator.stop()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--conjure-media":
        dur_arg = float(sys.argv[3]) if len(sys.argv) >= 4 else 8.0
        mute_arg = "--mute" in sys.argv[4:]
        conjure_media(sys.argv[2], duration=dur_arg, mute=mute_arg, _direct=True)
        sys.exit(0)
    acquire_singleton_lock()
    register_signal_handlers()
    main()
