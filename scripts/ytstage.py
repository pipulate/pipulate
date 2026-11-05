#!/usr/bin/env python3
"""
ytstage.py — LAN-to-DMZ Live Stage Projector for Honeybot (:10.0 OBS Broadcast).

Commands (via flake.nix wrappers `ytapp` and `ytvim`):
  • ytapp [start] [/path] [--say "Intro"]  Project local Pipulate FastHTML app (localhost:5001)
                                           onto Honeybot :10.0 via SSH reverse tunnel (15001).
  • ytapp status                           Check reverse tunnel & Honeybot Firefox stage window.
  • ytapp stop                             Dismiss Firefox stage window & close reverse tunnel.
  • ytvim [start]                          Pop fullscreen Alacritty stage window on Honeybot :10.0
                                           and stream local terminal/Neovim session live.
  • ytvim status                           Check Honeybot Alacritty stage window status.
  • ytvim stop                             Dismiss Alacritty stage window on Honeybot.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

HONEYBOT_HOST = os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")
LOCAL_PORT = int(os.environ.get("PIPULATE_PORT", "5001"))
REMOTE_TUNNEL_PORT = 15001
STAGE_PROFILE_DIR = "/tmp/honeybot_ytapp_profile"
VIM_ANSI_FIFO = "/tmp/ytvim.ansi"


def _local_server_alive(port: int = LOCAL_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as resp:
            return resp.status < 500
    except Exception:
        return False


def _tunnel_pids() -> list[str]:
    pattern = f"{REMOTE_TUNNEL_PORT}:127[.]0[.]0[.]1:{LOCAL_PORT}"
    res = subprocess.run(
        ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
    )
    return [p.strip() for p in (res.stdout or "").splitlines() if p.strip()]


def run_ytapp(
    action: str,
    subpath: str = "/",
    say_text: str = "",
    dry_run: bool = False,
    freeze_hud: bool = True,
) -> int:
    clean_path = "/" + (subpath or "").lstrip("/")
    stage_url = f"http://127.0.0.1:{REMOTE_TUNNEL_PORT}{clean_path}"

    if dry_run:
        print(
            f"🎬 [DRY RUN] ytapp action={action} | local=127.0.0.1:{LOCAL_PORT} -> "
            f"{HONEYBOT_HOST}:{stage_url} | freeze_hud={freeze_hud} | say={bool(say_text)}"
        )
        return 0

    if action == "status":
        pids = _tunnel_pids()
        rem = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                HONEYBOT_HOST,
                f"pgrep -af '{STAGE_PROFILE_DIR}' || echo 'NO_STAGE_BROWSER'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        print(
            f"📡 ytapp tunnel (15001->5001): {'RUNNING pid=' + ','.join(pids) if pids else 'STOPPED'}"
        )
        print(f"📺 Honeybot :10.0 stage      : {(rem.stdout or '').strip()}")
        return 0

    if action == "stop":
        subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                HONEYBOT_HOST,
                f"pkill -f '{STAGE_PROFILE_DIR}' 2>/dev/null || true; pkill -CONT -f 'logs[.]py' 2>/dev/null || true",
            ],
            check=False,
        )
        for pid in _tunnel_pids():
            subprocess.run(["kill", pid], check=False)
        print("🛑 Dismissed Honeybot FastHTML stage window, resumed logs.py (SIGCONT), & closed SSH reverse tunnel.")
        return 0

    # action == "start"
    if not _local_server_alive(LOCAL_PORT):
        print(
            f"⚠️ Local Pipulate server is not answering on http://127.0.0.1:{LOCAL_PORT}. "
            "Start it with `pu` or `nix develop` first."
        )
        return 1

    if say_text:
        repo_root = Path(__file__).resolve().parent.parent
        common_py = repo_root / "scripts" / "articles" / "common.py"
        if common_py.is_file():
            subprocess.run(
                [
                    sys.executable,
                    str(common_py),
                    "--broadcast",
                    "say",
                    "-c",
                    "PIPULATE\nLIVE DEMO",
                    say_text,
                ],
                check=False,
            )

    if not _tunnel_pids():
        tun = subprocess.run(
            [
                "ssh",
                "-f",
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-o",
                "ServerAliveInterval=30",
                "-R",
                f"{REMOTE_TUNNEL_PORT}:127.0.0.1:{LOCAL_PORT}",
                HONEYBOT_HOST,
            ],
            check=False,
        )
        if tun.returncode != 0:
            print(f"❌ Failed to open SSH reverse tunnel to {HONEYBOT_HOST}.")
            return 1

    remote_launch = f"""
import os, subprocess, time
env = os.environ.copy()
env["DISPLAY"] = ":10.0"
if {freeze_hud}:
    subprocess.run(["pkill", "-STOP", "-f", "logs[.]py"], check=False)
subprocess.run(["pkill", "-f", "{STAGE_PROFILE_DIR}"], check=False)
subprocess.run(["mkdir", "-p", "{STAGE_PROFILE_DIR}"], check=False)
subprocess.Popen(
    ["firefox", "--profile", "{STAGE_PROFILE_DIR}", "--new-window", "{stage_url}"],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
for _ in range(20):
    time.sleep(0.4)
    res = subprocess.run(["wmctrl", "-l"], env=env, capture_output=True, text=True)
    for line in (res.stdout or "").splitlines():
        if "Mozilla Firefox" in line or "Pipulate" in line:
            wid = line.split()[0]
            subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,fullscreen,above"], env=env, check=False)
            subprocess.run(["wmctrl", "-i", "-a", wid], env=env, check=False)
            print("STAGE_WINDOW_PINNED=" + wid)
            raise SystemExit(0)
print("STAGE_WINDOW_LAUNCHED")
"""
    res = subprocess.run(
        ["ssh", HONEYBOT_HOST, "python3", "-"],
        input=remote_launch,
        text=True,
        check=False,
    )
    if res.returncode == 0:
        print(f"🎬 Pipulate FastHTML Live Stage ON-AIR at {stage_url}")
        print("   • Drive it in your local browser at http://localhost:5001 (or run Ghost Driver: Ctrl+Alt+D)")
        print("   • Return stream to Observatory HUD: ytapp stop")
    return res.returncode


def run_ytvim(action: str, dry_run: bool = False) -> int:
    if dry_run:
        print(
            f"🎬 [DRY RUN] ytvim action={action} | stream=Prime(script -q -f) -> "
            f"{HONEYBOT_HOST}:{VIM_ANSI_FIFO} (Alacritty Fullscreen :10.0)"
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
                "pgrep -af 'HONEYBOT_LIVE_VIM' || echo 'NO_VIM_STAGE'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"📺 Honeybot :10.0 ytvim stage: {(rem.stdout or '').strip()}")
        return 0

    if action == "stop":
        subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                HONEYBOT_HOST,
                f"pkill -f 'HONEYBOT_LIVE_VIM' 2>/dev/null || true; pkill -CONT -f 'logs[.]py' 2>/dev/null || true; rm -f {VIM_ANSI_FIFO}",
            ],
            check=False,
        )
        print("🛑 Dismissed Honeybot Live Neovim stage window & resumed logs.py (SIGCONT).")
        return 0

    # action == "start"
    remote_prep = f"""
import os, pathlib, subprocess, time
env = os.environ.copy()
env["DISPLAY"] = ":10.0"
subprocess.run(["pkill", "-STOP", "-f", "logs[.]py"], check=False)
subprocess.run(["pkill", "-f", "HONEYBOT_LIVE_VIM"], check=False)
p = pathlib.Path("{VIM_ANSI_FIFO}")
p.write_text("\\033[2J\\033[H🔴 LIVE TERMINAL / NEOVIM STREAM FROM PIPULATE PRIME...\\r\\n", encoding="utf-8")
subprocess.Popen(
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
    parser.add_argument("args", nargs="*", help="Action (start|stop|status) and optional URL path or 'optics' preset.")
    parser.add_argument("--optics-demo", action="store_true", help="Launch 911 LLM Optics with hands-free Ghost Driver (?demo=1).")
    parser.add_argument("--no-freeze", action="store_true", help="Do not pause Honeybot logs.py with SIGSTOP while stage is active.")
    parser.add_argument("--say", type=str, default="", help="Optional Piper TTS announcement before opening stage.")
    parser.add_argument("--dry-run", action="store_true", help="Verify stage command routing without side effects.")
    parsed = parser.parse_args()

    action = "start"
    subpath = "/"
    for token in parsed.args:
        low = token.strip().lower()
        if low in ("start", "stop", "status", "kill"):
            action = "stop" if low == "kill" else low
        elif low in ("optics", "optics-demo", "911"):
            subpath = "/optics_workflow?demo=1"
        elif token.startswith("/"):
            subpath = token.strip()

    if parsed.optics_demo:
        subpath = "/optics_workflow?demo=1"

    if parsed.mode == "app":
        return run_ytapp(
            action=action,
            subpath=subpath,
            say_text=parsed.say,
            dry_run=parsed.dry_run,
            freeze_hud=not parsed.no_freeze,
        )
    return run_ytvim(action=action, dry_run=parsed.dry_run)


if __name__ == "__main__":
    sys.exit(main())
