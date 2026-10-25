#!/usr/bin/env python3
"""
🤖 weebo.py -- Double-Buffered, Self-Terminating Media Overlay Engine.

Resolves shorthand asset names (e.g. 'ambigram', 'ai-seo-software') across local
and blog image libraries, pre-composites transparent PNGs onto a #111111
obsidian back-buffer so alpha channels never render a checkerboard, and pops a
frameless, topmost X11 overlay via mpv that owns its own teardown without
stealing keyboard focus from the active terminal.
"""

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

MEDIA_OVERLAY_MARKER = "honeybot_media_overlay"
OBSIDIAN_RGB = (17, 17, 17)
SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm", ".mkv", ".mov")
VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")


def read_image_dimensions(path):
    """Read (width, height) from PNG/GIF/JPEG header bytes using stdlib only."""
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
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        pass
    return 1440, 810


def candidate_search_dirs():
    """Return ordered list of existing directories searched for shorthand media keys."""
    repo_root = Path(__file__).resolve().parents[1]
    home = Path.home()
    candidates = [
        repo_root / "assets" / "weebo",
        repo_root / "assets" / "images",
        home / "repos" / "trimnoir" / "assets" / "weebo",
        home / "repos" / "trimnoir" / "assets" / "images",
        home / "www" / "mikelev.in" / "assets" / "weebo",
        home / "www" / "mikelev.in" / "_site" / "assets" / "images",
        home / "www" / "mikelev.in" / "assets" / "images",
        Path("/tmp/honeybot_media"),
    ]
    seen = set()
    dirs = []
    for d in candidates:
        if d.is_dir():
            real = str(d.resolve())
            if real not in seen:
                seen.add(real)
                dirs.append(d)
    return dirs


def list_shorthand_assets(limit=40):
    """Return list of (stem, Path) across all candidate media directories."""
    items = []
    seen_stems = set()
    for d in candidate_search_dirs():
        files = sorted(
            (p for p in d.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in files:
            key = p.stem.lower()
            if key not in seen_stems:
                seen_stems.add(key)
                items.append((p.stem, p))
                if len(items) >= limit:
                    return items
    return items


def _classify_ext(path_or_url):
    ext = os.path.splitext(str(path_or_url).split("?", 1)[0])[1].lower()
    if ext in VIDEO_EXTS:
        return "VIDEO"
    if ext == ".gif":
        return "GIF"
    return "IMAGE"


def resolve_media_target(raw_spec, default_duration=8.0):
    """Resolve 'shorthand[:seconds]' or '/path/to/file[:seconds]' into (path_str, duration, kind)."""
    if isinstance(raw_spec, dict):
        raw_str = str(raw_spec.get("path") or raw_spec.get("url") or "").strip()
        duration = float(raw_spec.get("duration", default_duration))
    else:
        raw_str = str(raw_spec or "").strip()
        duration = float(default_duration)
        if ":" in raw_str and not raw_str.startswith(("http://", "https://", "file://")):
            head, tail = raw_str.rsplit(":", 1)
            try:
                duration = float(tail.strip())
                raw_str = head.strip()
            except ValueError:
                pass
    duration = max(1.0, min(600.0, duration))
    if not raw_str:
        return "", duration, "IMAGE"
    if raw_str.startswith(("http://", "https://", "file://")):
        return raw_str, duration, _classify_ext(raw_str)

    direct = Path(raw_str).expanduser()
    if direct.is_file():
        resolved = str(direct.resolve())
        return resolved, duration, _classify_ext(resolved)

    repo_root = Path(__file__).resolve().parents[1]
    rel_cand = repo_root / raw_str.lstrip("/")
    if rel_cand.is_file():
        resolved = str(rel_cand.resolve())
        return resolved, duration, _classify_ext(resolved)

    needle = raw_str.lower()
    needle_stem = Path(needle).stem

    # Pass 1: exact filename or exact stem match
    for d in candidate_search_dirs():
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
                continue
            if p.name.lower() == needle or p.stem.lower() == needle_stem:
                resolved = str(p.resolve())
                return resolved, duration, _classify_ext(resolved)

    # Pass 2: prefix or substring stem match (prefer PNG/GIF/MP4 and newest file)
    matches = []
    for d in candidate_search_dirs():
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
                continue
            stem_l = p.stem.lower()
            if stem_l.startswith(needle_stem) or needle_stem in stem_l:
                ext_rank = 0 if p.suffix.lower() in (".png", ".gif", ".mp4") else 1
                prefix_rank = 0 if stem_l.startswith(needle_stem) else 1
                matches.append((prefix_rank, ext_rank, -p.stat().st_mtime, p))
    if matches:
        matches.sort(key=lambda item: item[:3])
        best = str(matches[0][3].resolve())
        return best, duration, _classify_ext(best)

    return "", duration, "IMAGE"


def compute_centered_geometry(img_w, img_h, max_w=1440, max_h=840, screen_w=1920, screen_h=1080):
    """Compute (win_w, win_h, pos_x, pos_y) centered on screen while preserving aspect ratio."""
    scale = min(max_w / max(1, img_w), max_h / max(1, img_h))
    win_w = max(256, int(round(img_w * scale)))
    win_h = max(256, int(round(img_h * scale)))
    pos_x = max(0, (screen_w - win_w) // 2)
    pos_y = max(0, (screen_h - win_h) // 2)
    return win_w, win_h, pos_x, pos_y


def prepare_backbuffer(src_path, max_w=1440, max_h=840, out_path=None):
    """Pre-composite a still image onto a #111111 obsidian canvas in a back-buffer PNG."""
    if not src_path or src_path.startswith(("http://", "https://", "file://")) or not os.path.isfile(src_path):
        w, h, x, y = compute_centered_geometry(1440, 810, max_w=max_w, max_h=max_h)
        return src_path, False, w, h, x, y

    kind = _classify_ext(src_path)
    img_w, img_h = read_image_dimensions(src_path)
    win_w, win_h, pos_x, pos_y = compute_centered_geometry(img_w, img_h, max_w=max_w, max_h=max_h)

    if kind != "IMAGE":
        return src_path, False, win_w, win_h, pos_x, pos_y

    try:
        from PIL import Image
        with Image.open(src_path) as raw_im:
            rgba = raw_im.convert("RGBA")
            if (win_w, win_h) != rgba.size:
                rgba = rgba.resize((win_w, win_h), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (win_w, win_h), OBSIDIAN_RGB)
            canvas.paste(rgba, (0, 0), mask=rgba.split()[3])
            dest = Path(out_path) if out_path else Path(f"/tmp/weebo_buf_{os.getpid()}_{int(time.time() * 1000)}.png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(dest, "PNG")
            return str(dest), True, win_w, win_h, pos_x, pos_y
    except Exception:
        return src_path, False, win_w, win_h, pos_x, pos_y


def _get_active_window_id(env):
    if not shutil.which("xdotool"):
        return ""
    try:
        res = subprocess.run(
            ["xdotool", "getactivewindow"],
            env=env,
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        return (res.stdout or "").strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def _pin_above_and_restore_focus(orig_win, env):
    time.sleep(0.25)
    if shutil.which("wmctrl"):
        subprocess.run(
            ["wmctrl", "-r", MEDIA_OVERLAY_MARKER, "-b", "add,above"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if orig_win and shutil.which("xdotool"):
        subprocess.run(
            ["xdotool", "windowactivate", orig_win],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def pop_weebo(spec, duration=8.0, mute=False, display=None, dry_run=False):
    """Pop a self-terminating, double-buffered media overlay on X11 without stealing focus."""
    target, dur, kind = resolve_media_target(spec, default_duration=duration)
    if not target:
        print(f"⚠️ Weebo could not resolve media asset: {spec!r}", file=sys.stderr)
        return 1

    buf_path, composited, win_w, win_h, pos_x, pos_y = prepare_backbuffer(target)
    geom_str = f"{win_w}x{win_h}+{pos_x}+{pos_y}"

    if dry_run:
        if composited and buf_path != target and os.path.isfile(buf_path):
            try:
                os.remove(buf_path)
            except OSError:
                pass
        print(
            f"WEEBO_DRY_RUN: kind={kind} | resolved={target} | "
            f"composited={composited} | geom={geom_str} | duration={dur:.1f}s"
        )
        return 0

    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    else:
        env["DISPLAY"] = env.get("DISPLAY") or ":0"

    orig_win = _get_active_window_id(env)
    proc = None
    try:
        if shutil.which("mpv"):
            cmd = [
                "mpv",
                f"--title={MEDIA_OVERLAY_MARKER}",
                "--no-border",
                "--ontop",
                f"--geometry={geom_str}",
                "--keep-open=no",
                "--really-quiet",
            ]
            if kind == "IMAGE":
                cmd.append(f"--image-display-duration={dur:.1f}")
            elif kind == "GIF":
                cmd.extend(["--loop-file=inf", f"--length={dur:.1f}"])
            else:
                cmd.append(f"--length={dur:.1f}")
                if mute:
                    cmd.append("--mute=yes")
            cmd.append(buf_path)
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _pin_above_and_restore_focus(orig_win, env)
            proc.wait(timeout=dur + 2.0)
        elif kind == "IMAGE" and shutil.which("feh") and os.path.isfile(buf_path):
            cmd = [
                "feh",
                "--title", MEDIA_OVERLAY_MARKER,
                "--borderless",
                "--image-bg", "black",
                "--auto-zoom",
                "--scale-down",
                "--geometry", geom_str,
                buf_path,
            ]
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _pin_above_and_restore_focus(orig_win, env)
            proc.wait(timeout=dur)
        else:
            print("⚠️ Neither mpv nor feh found on PATH.", file=sys.stderr)
            return 1
    except subprocess.TimeoutExpired:
        pass
    except KeyboardInterrupt:
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
        if composited and buf_path != target and os.path.isfile(buf_path):
            try:
                os.remove(buf_path)
            except OSError:
                pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="Operation Weebo: Double-buffered X11 media overlay.")
    parser.add_argument("spec", nargs="?", default="ambigram", help="Shorthand asset name, path, or 'list' (default: ambigram).")
    parser.add_argument("-d", "--duration", type=float, default=8.0, help="Display duration in seconds (default: 8.0).")
    parser.add_argument("--mute", action="store_true", help="Mute audio on video clips.")
    parser.add_argument("--remote", action="store_true", help="Stage and pop on Honeybot (:10.0) via ytsay/ytmedia.")
    parser.add_argument("--list", action="store_true", help="List available shorthand media assets.")
    parser.add_argument("--dry-run", action="store_true", help="Verify resolution and back-buffer geometry without opening X11.")
    args = parser.parse_args()

    if args.list or str(args.spec).strip().lower() == "list":
        assets = list_shorthand_assets()
        print(f"🤖 Operation Weebo Shorthand Library ({len(assets)} asset(s) found):")
        for stem, path in assets[:25]:
            print(f"   • {stem:<32} -> {path}")
        return 0

    if args.remote:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "articles"))
        from common import send_honeybot_live_message
        spec_str = str(args.spec).strip()
        if ":" not in spec_str and args.duration != 8.0:
            spec_str = f"{spec_str}:{args.duration:g}"
        return send_honeybot_live_message("", media_path=spec_str, dry_run=args.dry_run)

    return pop_weebo(args.spec, duration=args.duration, mute=args.mute, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
