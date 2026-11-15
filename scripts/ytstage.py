#!/usr/bin/env python3
"""
ytstage.py — LAN-to-DMZ Live Stage Projector for Honeybot (:10.0 OBS Broadcast).

Commands (via flake.nix wrappers `ytapp` and `ytvim`):
  • ytapp [start] [/path|optics] [--say "Intro"]  Project local Pipulate FastHTML app (localhost:5001)
                                                  onto Honeybot :10.0 via SSH reverse tunnel (15001).
  • ytapp say "Commentary..."                     Speak scripted Piper TTS on Honeybot's live audio bus.
  • ytapp status                                  Check reverse tunnel & Honeybot Firefox stage window.
  • ytapp stop                                    Dismiss Firefox stage window, resume Storytime, & close tunnel.
  • ytvim [start]                                 Pop fullscreen Alacritty stage window on Honeybot :10.0
                                                  and stream local terminal/Neovim session live.
  • ytvim status                                  Check Honeybot Alacritty stage window status.
  • ytvim stop                                    Dismiss Alacritty stage window & resume Storytime on Honeybot.
"""

import argparse
import base64
import fcntl
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import urllib.request

def _parse_port_env(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name, "").strip()
    if raw.isdigit():
        port = int(raw)
        if 1 <= port <= 65535:
            return port
    return default


HONEYBOT_HOST = os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
LOCAL_PORT = _parse_port_env("PIPULATE_PORT", 5001)
STAGE_PORT = _parse_port_env("PIPULATE_STAGE_PORT", 5002)
STAGE_DIR = Path(
    os.path.expanduser(os.environ.get("PIPULATE_STAGE_DIR", "~/.local/share/pipulate/stage"))
)
REMOTE_TUNNEL_PORT = 15001
STAGE_PROFILE_DIR = "/tmp/honeybot_ytapp_profile"
STAGE_PROFILE_PGREP = "[/]tmp/honeybot_ytapp_profile"
DARK_FIREFOX_PREFS = (
    'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n'
    'user_pref("ui.systemUsesDarkTheme", 1);\n'
    'user_pref("layout.css.prefers-color-scheme.content-override", 0);\n'
    'user_pref("browser.theme.content-theme", 0);\n'
    'user_pref("browser.theme.toolbar-theme", 0);\n'
    'user_pref("browser.display.background_color", "#0b0f19");\n'
    'user_pref("browser.display.background_color.dark", "#0b0f19");\n'
    'user_pref("browser.startup.blankWindow", false);\n'
    'user_pref("browser.sessionstore.resume_from_crash", false);\n'
    'user_pref("browser.shell.checkDefaultBrowser", false);\n'
    'user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\n'
    'user_pref("trailhead.firstrun.didSeeAboutWelcome", true);\n'
    'user_pref("browser.startup.homepage_override.mstone", "ignore");\n'
    'user_pref("media.autoplay.default", 0);\n'
    'user_pref("media.autoplay.blocking_policy", 0);\n'
)
DARK_USERCHROME_CSS = (
    ":root, window, #main-window, #navigator-toolbox, #tabbrowser-tabpanels, "
    "tabpanels, browser, #appcontent, #browser { "
    "background: #0b0f19 !important; background-color: #0b0f19 !important; }\n"
)
DARK_USERCONTENT_CSS = (
    '@-moz-document url("about:blank"), url("about:newtab"), url("about:home") { '
    "html, body { background: #0b0f19 !important; background-color: #0b0f19 !important; } }\n"
)
VIM_ANSI_FIFO = "/tmp/ytvim.ansi"
WEEBO_STAGE_PAUSE_FILE = "/tmp/honeybot_weebo_active"
STREAM_LOCK_PATH = "/tmp/honeybot-stream.py.lock"
STAGE_PAUSED_PIDS_FILE = "/tmp/honeybot_ytstage_paused.json"
STAGE_AUDIO_BRIDGE_FILE = "/tmp/pipulate_ytstage_audio.json"
OPTICS_SLOT_FILE = "/tmp/honeybot_optics_slot.json"
YTBREAKS_TMUX_SESSION = "ytbreaks"
YTBREAKS_LOG_FILE = "/tmp/ytbreaks.log"
DEFAULT_OPTICS_SIFT_TEXT = (
    "Capturing live wire headers, raw HTML source, hydrated DOM, and RFC 9110 Markdown right now. "
    "This tool can be yours — you can just go get it at SunPug.io and join the army of AI-Readiness Consultants, "
    "and step inside our Founding 1,000 practitioner chat at mikelev.in/discord."
)
DEFAULT_OPTICS_OUTRO_TEXT = (
    "Every tool you just watched can be yours right now, in this single sitting. "
    "Go get your own Sun Pug at Sun Pug dot I O "
    "and join us on Discord at Mike Lev dot I N slash discord. "
    "Returning now to the web bot AI Observatory."
)


def _manage_ytbreaks_daemon(action: str, dry_run: bool = False) -> int:
    """Start, ensure, stop, or inspect the background tmux 'ytbreaks' (ytapp watch-breaks) session on Prime."""
    repo_root = Path(__file__).resolve().parents[1]
    log_path = Path(YTBREAKS_LOG_FILE)
    if dry_run:
        print(f"🔭 [DRY RUN] ytbreaks daemon action={action} (session={YTBREAKS_TMUX_SESSION}, log={log_path})")
        return 0
    is_running = (
        subprocess.run(
            ["tmux", "has-session", "-t", YTBREAKS_TMUX_SESSION],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )
    if action == "watch-status":
        print(f"📡 ytbreaks daemon: {'RUNNING (tmux session: ' + YTBREAKS_TMUX_SESSION + ')' if is_running else 'STOPPED'}")
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
            if lines:
                print(f"--- Last {len(lines)} line(s) of {log_path} ---")
                for ln in lines:
                    print(f"   {ln}")
        return 0
    if action == "watch-stop":
        if is_running:
            subprocess.run(["tmux", "kill-session", "-t", YTBREAKS_TMUX_SESSION], check=False)
            print(f"🛑 Stopped background tmux session '{YTBREAKS_TMUX_SESSION}'.")
        else:
            print(f"ℹ️  No background '{YTBREAKS_TMUX_SESSION}' tmux session was running.")
        return 0
    if action == "watch-log":
        if not is_running:
            rc = _manage_ytbreaks_daemon("daemon", dry_run=False)
            if rc != 0:
                return rc
        if not sys.stdout.isatty():
            return _manage_ytbreaks_daemon("watch-status", dry_run=False)
        subprocess.run(["tmux", "bind-key", "-n", "q", "detach-client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            subprocess.run(["tmux", "attach-session", "-r", "-t", YTBREAKS_TMUX_SESSION], check=False)
        finally:
            subprocess.run(["tmux", "unbind-key", "-n", "q"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return 0
    if action == "ensure-daemon" and is_running:
        return 0
    if is_running:
        subprocess.run(["tmux", "kill-session", "-t", YTBREAKS_TMUX_SESSION], check=False)
    py_bin = repo_root / ".venv" / "bin" / "python"
    if not py_bin.is_file():
        py_bin = Path(sys.executable)
    script_path = Path(__file__).resolve()
    cmd_str = f"PYTHONUNBUFFERED=1 {py_bin} {script_path} app watch-breaks 2>&1 | tee -a {log_path}"
    res = subprocess.run(
        ["tmux", "new-session", "-d", "-s", YTBREAKS_TMUX_SESSION, "-c", str(repo_root), cmd_str],
        check=False,
    )
    if res.returncode == 0:
        target_port = _resolve_target_port()
        for opt, val in (
            ("status", "on"),
            ("status-style", "bg=colour235,fg=colour46,bold"),
            ("status-left-length", "48"),
            ("status-left", f" 🎬 YTBREAKS OPTICS WATCHER ({REMOTE_TUNNEL_PORT}->{target_port}) "),
            ("status-right-length", "64"),
            ("status-right", " EXIT (KEEP RUNNING): Press q OR Ctrl+b then d "),
        ):
            subprocess.run(
                ["tmux", "set-option", "-t", YTBREAKS_TMUX_SESSION, opt, val],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        print(f"🎬 Started background '{YTBREAKS_TMUX_SESSION}' (`ytapp watch-breaks`) daemon in tmux.")
        print("   • Check Optics watcher: ytbreaks   (or `ytapp watch-log` — press `q` to detach)")
        print("   • Stop Optics watcher : ytapp watch-stop")
        return 0
    print(f"❌ Failed to start tmux session '{YTBREAKS_TMUX_SESSION}'.")
    return 1

REMOTE_PAUSE_SNIPPET = """
def _pause_honeybot_stage(pause_audio=True):
    import json, os, pathlib, signal
    paused = []
    try:
        pathlib.Path("/tmp/honeybot_weebo_active").write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass
    my_pid, parent_pid = os.getpid(), os.getppid()
    lock_p = pathlib.Path("/tmp/honeybot-stream.py.lock")
    if lock_p.is_file():
        raw_lp = lock_p.read_text(encoding="utf-8", errors="ignore").strip()
        if raw_lp.isdigit() and int(raw_lp) not in (my_pid, parent_pid):
            try:
                os.kill(int(raw_lp), signal.SIGSTOP)
                paused.append(int(raw_lp))
            except Exception:
                pass
    bgm_running = False
    for p in sorted(pathlib.Path("/proc").glob("[0-9]*/cmdline")):
        try:
            pid = int(p.parent.name)
            if pid in (my_pid, parent_pid) or pid in paused:
                continue
            raw = p.read_bytes().replace(b"\\x00", b" ").decode("utf-8", errors="ignore")
            if "honeybot-storytime-bgm" in raw or ("aplay" in raw and "dripulate.wav" in raw):
                bgm_running = True
                try:
                    os.kill(pid, signal.SIGCONT)
                except Exception:
                    pass
                continue
            if pause_audio and (
                ("aplay" in raw and ("-t raw" in raw or "honeybot_tts" in raw or "tick.wav" in raw))
                or ("piper" in raw and "output_raw" in raw)
            ):
                os.kill(pid, signal.SIGSTOP)
                paused.append(pid)
        except Exception:
            continue
    bgm_wav = pathlib.Path("/home/mike/www/mikelev.in/assets/sounds/dripulate.wav")
    if not bgm_running and bgm_wav.is_file() and os.environ.get("HONEYBOT_NO_AUDIO") != "1":
        try:
            import subprocess as _sp
            bgm_env = os.environ.copy()
            bgm_env["PATH"] = "/etc/profiles/per-user/mike/bin:/home/mike/.nix-profile/bin:/run/current-system/sw/bin:/usr/bin:/bin:" + bgm_env.get("PATH", "")
            _sp.Popen(
                ["sh", "-c", 'while :; do aplay -q -D default "/home/mike/www/mikelev.in/assets/sounds/dripulate.wav"; sleep 0.2; done # honeybot-storytime-bgm'],
                env=bgm_env,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                preexec_fn=os.setsid,
            )
        except Exception:
            pass
    try:
        pathlib.Path("/tmp/honeybot_ytstage_paused.json").write_text(json.dumps(paused), encoding="utf-8")
    except Exception:
        pass
"""

REMOTE_RESUME_SNIPPET = """
import json, os, pathlib, signal
pathlib.Path("/tmp/honeybot_weebo_active").unlink(missing_ok=True)
paused = []
state_p = pathlib.Path("/tmp/honeybot_ytstage_paused.json")
if state_p.is_file():
    try:
        paused = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        paused = []
    state_p.unlink(missing_ok=True)
lock_p = pathlib.Path("/tmp/honeybot-stream.py.lock")
if lock_p.is_file():
    raw_lp = lock_p.read_text(encoding="utf-8", errors="ignore").strip()
    if raw_lp.isdigit() and int(raw_lp) not in paused:
        paused.append(int(raw_lp))
resumed = set()
for pid in paused:
    try:
        os.kill(int(pid), signal.SIGCONT)
        resumed.add(int(pid))
    except Exception:
        pass
for p in sorted(pathlib.Path("/proc").glob("[0-9]*/cmdline")):
    try:
        pid = int(p.parent.name)
        if pid in resumed:
            continue
        raw = p.read_bytes().replace(b"\\x00", b" ").decode("utf-8", errors="ignore")
        if (
            ("aplay" in raw and ("-t raw" in raw or "honeybot_tts" in raw or "dripulate.wav" in raw))
            or ("piper" in raw and "output_raw" in raw)
        ):
            os.kill(pid, signal.SIGCONT)
        elif "logs.py" in raw:
            stat_txt = (p.parent / "stat").read_text(encoding="utf-8", errors="ignore")
            if ") T " in stat_txt:
                os.kill(pid, signal.SIGCONT)
    except Exception:
        continue
"""

REMOTE_SPEAK_SNIPPET = """
import fcntl, os, pathlib, shutil, subprocess, sys, time
text = base64.b64decode(TEXT_B64).decode("utf-8").strip()
try:
    sys.path.insert(0, "/home/mike/www/mikelev.in/scripts")
    import terms as _terms
    text = _terms.apply_inline_tts_terms(text).strip()
except Exception:
    pass
if text:
    extra = "/etc/profiles/per-user/mike/bin:/home/mike/.nix-profile/bin:/run/current-system/sw/bin:/usr/bin:/bin"
    env = os.environ.copy()
    env["PATH"] = extra + ":" + env.get("PATH", "")
    vdir = pathlib.Path.home() / ".local/share/piper_voices"
    ryan = vdir / "en_US-ryan-low.onnx"
    amy = vdir / "en_US-amy-low.onnx"
    model, rate = (ryan, "19200") if (ryan.is_file() and (vdir / "en_US-ryan-low.onnx.json").is_file()) else (amy, "16000")
    piper_bin = shutil.which("piper", path=env["PATH"])
    aplay_bin = shutil.which("aplay", path=env["PATH"])
    if piper_bin and aplay_bin and model.is_file():
        lf = open("/tmp/honeybot_stage_aplay.lock", "w")
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.1)
        try:
            p1 = subprocess.Popen([piper_bin, "--model", str(model), "--output_raw"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
            p2 = subprocess.Popen([aplay_bin, "-q", "-D", "default", "-r", rate, "-f", "S16_LE", "-t", "raw"], stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            if p1.stdin:
                p1.stdin.write(text.encode("utf-8"))
                p1.stdin.close()
            if p1.stdout:
                p1.stdout.close()
            p2.wait(timeout=90)
        finally:
            try:
                fcntl.flock(lf, fcntl.LOCK_UN)
                lf.close()
            except OSError:
                pass
"""


def _local_server_alive(port: int = LOCAL_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as resp:
            return resp.status < 500
    except Exception:
        return False


def _resolve_target_port() -> int:
    """Prefer STAGE_PORT (default 5002) when listening on 127.0.0.1; fall back to LOCAL_PORT (5001)."""
    if STAGE_PORT != LOCAL_PORT and _local_server_alive(STAGE_PORT):
        return STAGE_PORT
    return LOCAL_PORT


def _ensure_local_server(port: int = LOCAL_PORT, auto_start: bool = True, wait_sec: float = 20.0) -> bool:
    """Ensure Pipulate FastHTML server is answering on 127.0.0.1:port; auto-launch server.py if asleep."""
    if _local_server_alive(port):
        return True
    if not auto_start:
        return False
    repo_root = Path(__file__).resolve().parents[1]
    venv_py = repo_root / ".venv" / "bin" / "python"
    srv_py = repo_root / "server.py"
    if not (venv_py.is_file() and srv_py.is_file()):
        return False
    print(f"🚀 Local Pipulate server asleep on :{port}; auto-starting {srv_py.name}...")
    log_f = open("/tmp/pipulate_ytstage_server.log", "a", encoding="utf-8")
    sub_env = os.environ.copy()
    sub_env["PIPULATE_PORT"] = str(port)
    subprocess.Popen(
        [str(venv_py), str(srv_py)],
        cwd=str(repo_root),
        env=sub_env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        if _local_server_alive(port):
            print(f"✅ Local Pipulate server ready on http://127.0.0.1:{port}")
            return True
        time.sleep(0.5)
    return False


def _tunnel_entries() -> list[tuple[str, int]]:
    pattern = f"{REMOTE_TUNNEL_PORT}:127[.]0[.]0[.]1:[0-9]+"
    res = subprocess.run(
        ["pgrep", "-af", pattern], capture_output=True, text=True, check=False
    )
    entries: list[tuple[str, int]] = []
    marker = f"{REMOTE_TUNNEL_PORT}:127.0.0.1:"
    for raw in (res.stdout or "").splitlines():
        parts = raw.strip().split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit() or marker not in parts[1]:
            continue
        tok = parts[1].split(marker, 1)[1].split()[0]
        if tok.isdigit():
            entries.append((parts[0], int(tok)))
    return entries


def _tunnel_pids(target_port: int | None = None) -> list[str]:
    return [
        pid
        for pid, port in _tunnel_entries()
        if target_port is None or port == target_port
    ]


def _remote_tunnel_healthy() -> bool:
    """Verify from Honeybot itself that 127.0.0.1:REMOTE_TUNNEL_PORT reaches Prime's FastHTML server."""
    probe = (
        "import urllib.request, sys\n"
        f"r = urllib.request.urlopen('http://127.0.0.1:{REMOTE_TUNNEL_PORT}/', timeout=3)\n"
        "sys.exit(0 if r.status < 500 else 1)\n"
    )
    res = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", HONEYBOT_HOST, "python3", "-"],
        input=probe,
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode == 0


def _ensure_reverse_tunnel(target_port: int | None = None) -> bool:
    """Guarantee a working end-to-end SSH reverse tunnel (reaping stale local/remote sockets if dead)."""
    port = target_port if target_port is not None else _resolve_target_port()
    entries = _tunnel_entries()
    if entries and all(p == port for _, p in entries) and _remote_tunnel_healthy():
        return True
    for pid, _ in entries:
        subprocess.run(["kill", pid], check=False)
    subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            HONEYBOT_HOST,
            f"fuser -k {REMOTE_TUNNEL_PORT}/tcp >/dev/null 2>&1 || true",
        ],
        check=False,
    )
    tun = subprocess.run(
        [
            "ssh",
            "-f",
            "-N",
            "-o",
            "BatchMode=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=2",
            "-R",
            f"{REMOTE_TUNNEL_PORT}:127.0.0.1:{port}",
            HONEYBOT_HOST,
        ],
        check=False,
    )
    if tun.returncode != 0:
        return False
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if _remote_tunnel_healthy():
            return True
        time.sleep(0.4)
    return False


def build_remote_speak_script(say_text: str) -> str:
    b64 = base64.b64encode((say_text or "").strip().encode("utf-8")).decode("ascii")
    return f"import base64\nTEXT_B64 = {b64!r}\n" + REMOTE_SPEAK_SNIPPET


def _write_stage_audio_bridge(mute_stage: bool = False, local_port: int | None = None) -> None:
    payload = {
        "host": HONEYBOT_HOST,
        "remote_port": REMOTE_TUNNEL_PORT,
        "local_port": local_port if local_port is not None else _resolve_target_port(),
        "mute": bool(mute_stage),
        "updated_at": round(time.time(), 3),
    }
    try:
        p = Path(STAGE_AUDIO_BRIDGE_FILE)
        tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def _clear_stage_audio_bridge() -> None:
    try:
        Path(STAGE_AUDIO_BRIDGE_FILE).unlink(missing_ok=True)
    except OSError:
        pass


def _wait_for_local_voice_idle(max_wait: float = 20.0) -> None:
    """Wait until any in-flight ChipVoiceSystem SSH speech releases pipulate_voice.lock."""
    lock_path = f"/tmp/pipulate_voice.lock.{os.getuid()}"
    try:
        lf = open(lock_path, "w")
    except OSError:
        return
    try:
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lf, fcntl.LOCK_UN)
                break
            except BlockingIOError:
                time.sleep(0.15)
    finally:
        try:
            lf.close()
        except OSError:
            pass


def speak_on_honeybot(say_text: str, dry_run: bool = False) -> int:
    clean = (say_text or "").strip()
    if not clean:
        return 0
    if dry_run:
        print(f"🎤 [DRY RUN] Honeybot stage speech: {clean!r}")
        return 0
    lock_path = f"/tmp/pipulate_voice.lock.{os.getuid()}"
    lock_file = None
    try:
        lock_file = open(lock_path, "w")
        deadline = time.monotonic() + 45.0
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    break
                time.sleep(0.1)
    except OSError:
        lock_file = None
    try:
        res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", HONEYBOT_HOST, "python3", "-"],
            input=build_remote_speak_script(clean),
            text=True,
            check=False,
        )
        return res.returncode
    finally:
        if lock_file is not None:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
            except OSError:
                pass


def build_remote_firefox_launch(stage_url: str, freeze_hud: bool, pause_audio: bool) -> str:
    return f"""
import os, pathlib, shutil, subprocess, time
{REMOTE_PAUSE_SNIPPET}
env = os.environ.copy()
extra = "/etc/profiles/per-user/mike/bin:/home/mike/.nix-profile/bin:/run/current-system/sw/bin:/usr/bin:/bin"
env["PATH"] = extra + ":" + env.get("PATH", "")
for p in sorted(pathlib.Path("/proc").glob("[0-9]*/cmdline")):
    try:
        raw_cmd = p.read_bytes().replace(b"\\x00", b" ").decode("utf-8", errors="ignore")
        if not any(tok in raw_cmd for tok in ("stream.py", "logs.py", "obs", "xfce4-session")):
            continue
        for item in (p.parent / "environ").read_bytes().split(b"\\x00"):
            if b"=" in item:
                k, v = item.split(b"=", 1)
                ks = k.decode("utf-8", errors="ignore")
                vs = v.decode("utf-8", errors="ignore")
                if ks in ("XAUTHORITY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER", "PIPEWIRE_RUNTIME_DIR") and vs:
                    env[ks] = vs
        if env.get("XAUTHORITY"):
            break
    except Exception:
        continue
env["DISPLAY"] = ":10.0"
env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{{os.getuid()}}")
xauth = pathlib.Path.home() / ".Xauthority"
if not env.get("XAUTHORITY") and xauth.is_file():
    env["XAUTHORITY"] = str(xauth)
if {freeze_hud!r}:
    _pause_honeybot_stage(pause_audio={pause_audio!r})
if shutil.which("xdotool", path=env["PATH"]):
    subprocess.run(["xdotool", "mousemove", "1916", "540"], env=env, check=False)
subprocess.run(["pkill", "-f", {STAGE_PROFILE_PGREP!r}], check=False)
time.sleep(0.2)
prof = pathlib.Path({STAGE_PROFILE_DIR!r})
prof.mkdir(parents=True, exist_ok=True)
for stale_name in (".parentlock", "lock", "sessionstore.jsonlz4"):
    (prof / stale_name).unlink(missing_ok=True)
shutil.rmtree(prof / "sessionstore-backups", ignore_errors=True)
chrome_dir = prof / "chrome"
chrome_dir.mkdir(parents=True, exist_ok=True)
(prof / "user.js").write_text({DARK_FIREFOX_PREFS!r}, encoding="utf-8")
(chrome_dir / "userChrome.css").write_text({DARK_USERCHROME_CSS!r}, encoding="utf-8")
(chrome_dir / "userContent.css").write_text({DARK_USERCONTENT_CSS!r}, encoding="utf-8")
before_res = subprocess.run(["wmctrl", "-l"], env=env, capture_output=True, text=True, check=False)
before_wids = {{ln.split()[0] for ln in (before_res.stdout or "").splitlines() if ln.strip()}}
proc = subprocess.Popen(
    ["firefox", "--kiosk", "--profile", {STAGE_PROFILE_DIR!r}, "--no-remote", "--new-instance", {stage_url!r}],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
if {freeze_hud!r}:
    pathlib.Path("/tmp/honeybot_weebo_active").write_text(str(proc.pid), encoding="utf-8")
for _ in range(90):
    time.sleep(0.2)
    res = subprocess.run(["wmctrl", "-l"], env=env, capture_output=True, text=True, check=False)
    for line in (res.stdout or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        wid = parts[0]
        if wid not in before_wids and ("Firefox" in line or "Pipulate" in line or "Optics" in line):
            subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,fullscreen,above,skip_taskbar,skip_pager"], env=env, check=False)
            subprocess.run(["wmctrl", "-i", "-a", wid], env=env, check=False)
            print("STAGE_WINDOW_PINNED=" + wid)
            raise SystemExit(0)
print("STAGE_WINDOW_LAUNCHED")
"""


def run_ytapp(
    action: str,
    subpath: str = "/",
    say_text: str = "",
    outro_text: str = "",
    dry_run: bool = False,
    freeze_hud: bool = True,
    pause_audio: bool = True,
    wait_for_deed: bool = False,
    wait_timeout: int = 180,
    mute_stage: bool = False,
    watch_once: bool = False,
    keep_tunnel: bool = False,
) -> int:
    if action == "say":
        return speak_on_honeybot(say_text, dry_run=dry_run)
    if action in ("daemon", "watch-daemon", "watch-start", "restart-daemon", "ensure-daemon", "watch-stop", "watch-status", "watch-log"):
        return _manage_ytbreaks_daemon(action, dry_run=dry_run)
    if action in ("watch-breaks", "watch"):
        if dry_run:
            print(f"🔭 [DRY RUN] Watching {HONEYBOT_HOST}:{OPTICS_SLOT_FILE} from LAN -> DMZ (once={watch_once}).")
            return 0
        print(f"🔭 Watching {HONEYBOT_HOST}:{OPTICS_SLOT_FILE} for DMZ-safe 911 LLM Optics station breaks...", flush=True)
        if not watch_once:
            warm_port = _resolve_target_port()
            if _ensure_local_server(warm_port, auto_start=True):
                _ensure_reverse_tunnel(warm_port)
        script_mtime = Path(__file__).stat().st_mtime
        claim_script = (
            "import json, pathlib, time\n"
            f"p = pathlib.Path({OPTICS_SLOT_FILE!r})\n"
            "if p.is_file():\n"
            "    d = json.loads(p.read_text(encoding='utf-8'))\n"
            "    if d.get('state') == 'waiting' and (time.time() - float(d.get('requested_at', 0))) < 45:\n"
            "        d['state'] = 'claimed'\n"
            "        p.write_text(json.dumps(d), encoding='utf-8')\n"
            "        print('CLAIMED')\n"
        )
        idle_polls = 0
        try:
            while True:
                if not watch_once and Path(__file__).stat().st_mtime != script_mtime:
                    print("🔄 [HOT-RELOAD] ytstage.py updated on disk — re-execing ytbreaks watcher...", flush=True)
                    os.execv(sys.executable, [sys.executable, *sys.argv])
                idle_polls += 1
                if not watch_once and idle_polls % 30 == 0:
                    wp = _resolve_target_port()
                    if _local_server_alive(wp) and not _tunnel_pids(wp):
                        _ensure_reverse_tunnel(wp)
                try:
                    chk = subprocess.run(
                        [
                            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                            "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=1",
                            HONEYBOT_HOST, "python3", "-",
                        ],
                        input=claim_script,
                        capture_output=True,
                        text=True,
                        timeout=8,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    continue
                if "CLAIMED" in (chk.stdout or ""):
                    target_port = _resolve_target_port()
                    subprocess.run(
                        [
                            "tmux",
                            "set-option",
                            "-t",
                            YTBREAKS_TMUX_SESSION,
                            "status-left",
                            f" 🎬 YTBREAKS OPTICS WATCHER ({REMOTE_TUNNEL_PORT}->{target_port}) ",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    print(
                        f"🎬 Claimed Honeybot OPTICS_SLOT! Ensuring FastHTML server on :{target_port} & launching stage..."
                    )
                    if _ensure_local_server(target_port, auto_start=True):
                        rc = run_ytapp(
                            action="start",
                            subpath="/optics_workflow?demo=1",
                            say_text=say_text,
                            outro_text=outro_text or DEFAULT_OPTICS_OUTRO_TEXT,
                            dry_run=False,
                            freeze_hud=freeze_hud,
                            pause_audio=pause_audio,
                            wait_for_deed=True,
                            wait_timeout=wait_timeout,
                            mute_stage=mute_stage,
                            keep_tunnel=not watch_once,
                        )
                        if watch_once:
                            return rc
                if watch_once:
                    return 0
                time.sleep(2.0)
        except KeyboardInterrupt:
            print("\n🛑 Stopped watching Honeybot station breaks.")
            return 0

    clean_path = "/" + (subpath or "").lstrip("/")
    stage_url = f"http://127.0.0.1:{REMOTE_TUNNEL_PORT}{clean_path}"

    if dry_run:
        target_port = _resolve_target_port()
        print(
            f"🎬 [DRY RUN] ytapp action={action} | local=127.0.0.1:{target_port} -> "
            f"{HONEYBOT_HOST}:{stage_url} | sentinel_pause={freeze_hud} | "
            f"pause_audio={pause_audio} | say={bool(say_text)}"
        )
        return 0

    if action == "status":
        entries = _tunnel_entries()
        pids = [pid for pid, _ in entries]
        tun_port = entries[0][1] if entries else _resolve_target_port()
        rem = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                HONEYBOT_HOST,
                (
                    f"pgrep -af '{STAGE_PROFILE_PGREP}' || echo 'NO_STAGE_BROWSER'; "
                    f"test -f {WEEBO_STAGE_PAUSE_FILE} && echo 'SENTINEL=ACTIVE' || echo 'SENTINEL=CLEAR'"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        watcher_on = (
            subprocess.run(
                ["tmux", "has-session", "-t", YTBREAKS_TMUX_SESSION],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
        print(
            f"📡 ytbreaks watcher (tmux)   : {'RUNNING (session: ' + YTBREAKS_TMUX_SESSION + ')' if watcher_on else 'STOPPED (start with `ytapp daemon` or `ytreboot`)'}"
        )
        print(
            f"📡 ytapp tunnel ({REMOTE_TUNNEL_PORT}->{tun_port}): {'RUNNING pid=' + ','.join(pids) if pids else 'STOPPED'}"
        )
        print(f"📺 Honeybot :10.0 stage      : {(rem.stdout or '').strip()}")
        return 0

    if action == "stop":
        stop_script = (
            "import json, pathlib, subprocess\n"
            f"sp = pathlib.Path({OPTICS_SLOT_FILE!r})\n"
            "if sp.is_file():\n"
            "    try:\n"
            "        sp.write_text(json.dumps({'state': 'done'}), encoding='utf-8')\n"
            "    except Exception:\n"
            "        pass\n"
            f"subprocess.run(['pkill', '-f', {STAGE_PROFILE_PGREP!r}], check=False)\n"
            + REMOTE_RESUME_SNIPPET
        )
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", HONEYBOT_HOST, "python3", "-"],
            input=stop_script,
            text=True,
            check=False,
        )
        _clear_stage_audio_bridge()
        if not keep_tunnel:
            for pid in _tunnel_pids():
                subprocess.run(["kill", pid], check=False)
        tun_note = "kept warm SSH tunnel" if keep_tunnel else "closed SSH tunnel"
        print(f"🛑 Dismissed Honeybot FastHTML stage window, cleared sentinel pause, resumed Storytime, & {tun_note}.")
        return 0

    # action == "start"
    target_port = _resolve_target_port()
    if not _ensure_local_server(target_port, auto_start=True):
        print(
            f"⚠️ Local Pipulate server is not answering on http://127.0.0.1:{target_port}. "
            "Start it with `stage start`, `pu`, or `nix develop` first."
        )
        return 1

    if not _ensure_reverse_tunnel(target_port):
        print(
            f"❌ Failed to establish verified SSH reverse tunnel ({REMOTE_TUNNEL_PORT}->{target_port}) to {HONEYBOT_HOST}."
        )
        return 1

    start_ts = time.time()
    _write_stage_audio_bridge(mute_stage=mute_stage, local_port=target_port)
    remote_launch = build_remote_firefox_launch(
        stage_url=stage_url, freeze_hud=freeze_hud, pause_audio=pause_audio
    )
    res = subprocess.run(
        ["ssh", HONEYBOT_HOST, "python3", "-"],
        input=remote_launch,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        _clear_stage_audio_bridge()
    if res.returncode == 0:
        print(f"🎬 Pipulate FastHTML Live Stage ON-AIR at {stage_url}")
        if say_text:
            speak_on_honeybot(say_text, dry_run=False)
        if wait_for_deed:
            try:
                print(f"⏳ Waiting up to {wait_timeout}s for Ghost Driver to seal optics_deed.zip...")
                deadline = time.time() + wait_timeout
                deed_sealed = None
                sift_spoken = bool(say_text)
                repo_root = Path(__file__).resolve().parents[1]
                candidate_roots = [STAGE_DIR, repo_root] if target_port == STAGE_PORT else [repo_root, STAGE_DIR]
                watch_roots = [
                    sub
                    for base in candidate_roots
                    for sub in (base / "browser_cache" / "mikelev.in", base / "browser_cache" / "looking_at")
                ]
                while time.time() < deadline:
                    if not sift_spoken and (time.time() - start_ts) >= 5.0:
                        sift_spoken = True
                        speak_on_honeybot(DEFAULT_OPTICS_SIFT_TEXT, dry_run=False)
                    for root in watch_roots:
                        if root.is_dir():
                            for zp in root.rglob("optics_deed.zip"):
                                try:
                                    if zp.stat().st_mtime > start_ts and zp.stat().st_size > 0:
                                        deed_sealed = zp
                                        break
                                except OSError:
                                    continue
                        if deed_sealed:
                            break
                    if deed_sealed:
                        break
                    time.sleep(1.0)
                if deed_sealed:
                    print(f"✅ Fresh Optics Deed sealed ({deed_sealed.stat().st_size:,} B). Holding 7s for gold button flash...")
                    time.sleep(7.0)
                    _wait_for_local_voice_idle(max_wait=20.0)
                    if outro_text:
                        speak_on_honeybot(outro_text, dry_run=False)
                else:
                    print("⚠️ Timed out waiting for fresh optics_deed.zip; releasing stage cleanly.")
            finally:
                run_ytapp("stop", dry_run=False, keep_tunnel=keep_tunnel)
        else:
            print("   • Speak live stage commentary : ytapp say \"Watch Ghost Driver audit RFC 9110!\"")
            print("   • Return stream to Observatory: ytapp stop")
    return res.returncode


def run_ytvim(action: str, say_text: str = "", dry_run: bool = False, pause_audio: bool = True) -> int:
    if action == "say":
        return speak_on_honeybot(say_text, dry_run=dry_run)

    if dry_run:
        print(
            f"🎬 [DRY RUN] ytvim action={action} | stream=Prime(script -q -f) -> "
            f"{HONEYBOT_HOST}:{VIM_ANSI_FIFO} (Alacritty Fullscreen :10.0, sentinel_pause=True)"
        )
        return 0

    if action == "status":
        rem = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                HONEYBOT_HOST,
                "pgrep -af '[H]ONEYBOT_LIVE_VIM' || echo 'NO_VIM_STAGE'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"📺 Honeybot :10.0 ytvim stage: {(rem.stdout or '').strip()}")
        return 0

    if action == "stop":
        stop_script = (
            "import pathlib, subprocess\n"
            "subprocess.run(['pkill', '-f', 'HONEYBOT_LIVE_VIM'], check=False)\n"
            f"pathlib.Path({VIM_ANSI_FIFO!r}).unlink(missing_ok=True)\n"
            + REMOTE_RESUME_SNIPPET
        )
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", HONEYBOT_HOST, "python3", "-"],
            input=stop_script,
            text=True,
            check=False,
        )
        print("🛑 Dismissed Honeybot Live Neovim stage window, cleared sentinel pause, & resumed Storytime.")
        return 0

    # action == "start"
    remote_prep = f"""
import os, pathlib, subprocess, time
{REMOTE_PAUSE_SNIPPET}
env = os.environ.copy()
extra = "/etc/profiles/per-user/mike/bin:/home/mike/.nix-profile/bin:/run/current-system/sw/bin:/usr/bin:/bin"
env["PATH"] = extra + ":" + env.get("PATH", "")
env["DISPLAY"] = ":10.0"
_pause_honeybot_stage(pause_audio={pause_audio!r})
subprocess.run(["pkill", "-f", "HONEYBOT_LIVE_VIM"], check=False)
p = pathlib.Path({VIM_ANSI_FIFO!r})
p.write_text("\\033[2J\\033[H🔴 LIVE TERMINAL / NEOVIM STREAM FROM PIPULATE PRIME...\\r\\n", encoding="utf-8")
proc = subprocess.Popen(
    [
        "alacritty",
        "--title", "HONEYBOT_LIVE_VIM",
        "-o", "window.startup_mode=\\"Fullscreen\\"",
        "-o", "font.size=16.0",
        "-e", "bash", "-c", "tput civis 2>/dev/null || true; tail -f -c +1 {VIM_ANSI_FIFO}"
    ],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
pathlib.Path("/tmp/honeybot_weebo_active").write_text(str(proc.pid), encoding="utf-8")
time.sleep(0.6)
subprocess.run(["wmctrl", "-r", "HONEYBOT_LIVE_VIM", "-b", "add,fullscreen,above"], env=env, check=False)
print("YTVIM_STAGE_READY")
"""
    prep = subprocess.run(
        ["ssh", HONEYBOT_HOST, "python3", "-"],
        input=remote_prep,
        text=True,
        check=False,
    )
    if prep.returncode != 0:
        print(f"❌ Failed to open Alacritty stage window on {HONEYBOT_HOST}.")
        return 1

    if say_text:
        speak_on_honeybot(say_text, dry_run=False)

    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║ 🔴 LIVE ON YOUTUBE: Your terminal is now mirrored on Honeybot :10.0! ║")
    print("║ • Open Neovim (`vim ...`) or run commands normally.                  ║")
    print("║ • Type `exit` (or Ctrl+D) at the shell prompt to leave the stage!    ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    try:
        ssh_consumer = subprocess.Popen(
            ["ssh", HONEYBOT_HOST, f"cat >> {VIM_ANSI_FIFO}"],
            stdin=subprocess.PIPE,
        )
        subprocess.run(["script", "-q", "-f", "/dev/stdout"], stdout=ssh_consumer.stdin, check=False)
        if ssh_consumer.stdin:
            ssh_consumer.stdin.close()
        ssh_consumer.wait(timeout=5)
    except KeyboardInterrupt:
        pass
    finally:
        run_ytvim("stop", dry_run=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Pipulate FastHTML App or Neovim onto Honeybot :10.0.")
    parser.add_argument("mode", choices=("app", "vim"), help="Stage mode: 'app' (FastHTML browser) or 'vim' (terminal/Neovim).")
    parser.add_argument("args", nargs="*", help="Action (start|stop|status|say) and optional URL path or 'optics' preset.")
    parser.add_argument("--optics-demo", action="store_true", help="Launch 911 LLM Optics with hands-free Ghost Driver (?demo=1).")
    parser.add_argument("--no-freeze", action="store_true", help="Do not set /tmp/honeybot_weebo_active sentinel while stage is active.")
    parser.add_argument("--keep-audio", action="store_true", help="Keep Honeybot Storytime background narration playing during stage overlay.")
    parser.add_argument("--mute-stage", action="store_true", help="Do not route Pipulate Prime voice_synthesis audio over SSH to Honeybot.")
    parser.add_argument("--say", type=str, default="", help="Optional scripted Piper TTS line spoken directly on Honeybot's audio bus.")
    parser.add_argument("--outro", type=str, default="", help="Optional closing Piper TTS line spoken after --wait detects deed seal.")
    parser.add_argument("--wait", action="store_true", help="Wait for Ghost Driver to seal a fresh optics_deed.zip, then auto-stop and release port 15001.")
    parser.add_argument("--wait-timeout", type=int, default=180, help="Max seconds to wait for Ghost Driver completion under --wait (default: 180).")
    parser.add_argument("--once", action="store_true", help="Check once and exit when running watch-breaks.")
    parser.add_argument("--dry-run", action="store_true", help="Verify stage command routing without side effects.")
    parsed = parser.parse_args()

    action = "start"
    subpath = "/"
    say_parts: list[str] = []
    if parsed.args and parsed.args[0].strip().lower() == "say":
        action = "say"
        say_parts = list(parsed.args[1:])
    else:
        for token in parsed.args:
            low = token.strip().lower()
            if low in (
                "start", "stop", "status", "kill", "watch-breaks", "watch",
                "daemon", "watch-daemon", "watch-start", "restart-daemon",
                "ensure-daemon", "watch-stop", "watch-status", "watch-log",
            ):
                action = "stop" if low == "kill" else ("watch-breaks" if low == "watch" else low)
            elif low in ("optics", "optics-demo", "911"):
                subpath = "/optics_workflow?demo=1"
            elif token.startswith("/"):
                subpath = token.strip()

    say_text = parsed.say or (" ".join(say_parts).strip() if say_parts else "")
    if parsed.optics_demo:
        subpath = "/optics_workflow?demo=1"

    if parsed.mode == "app":
        return run_ytapp(
            action=action,
            subpath=subpath,
            say_text=say_text,
            outro_text=parsed.outro,
            dry_run=parsed.dry_run,
            freeze_hud=not parsed.no_freeze,
            pause_audio=not parsed.keep_audio,
            wait_for_deed=parsed.wait,
            wait_timeout=parsed.wait_timeout,
            mute_stage=parsed.mute_stage,
            watch_once=parsed.once,
        )
    return run_ytvim(
        action=action,
        say_text=say_text,
        dry_run=parsed.dry_run,
        pause_audio=not parsed.keep_audio,
    )


if __name__ == "__main__":
    sys.exit(main())
