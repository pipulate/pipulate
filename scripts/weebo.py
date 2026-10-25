#!/usr/bin/env python3
"""
🤖 weebo.py -- Native-Resolution, Alpha-Transparent X11 Media Overlay Engine.

- Default asset is the Book of Proof Wax Seal (`assets/images/ambigram-209.png`).
- Preserves 1:1 native pixel resolution (never upscales small icons/seals; only
  downscales images that exceed max_w x max_h).
- Preserves PNG/WebP/GIF alpha transparency via mpv `--alpha=yes --background=none`
  (with optional `--matte` if a #111111 obsidian backing is ever desired).
- Enrolls explicit local file paths into `~/.local/share/pipulate/weebo/` (outside
  the Pipulate git repo) for instant shorthand recall on Pipulate Prime, while
  requiring `weeboh` (`--remote`) to deliberately push an asset out to Honeybot.
"""

import argparse
import os
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
DEFAULT_SEAL_ALIASES = frozenset({"", "seal", "wax", "ambigram", "ambigram-209", "default"})

LOCAL_WEEBO_DIR = Path(
    os.environ.get("PIPULATE_WEEBO_DIR", Path.home() / ".local" / "share" / "pipulate" / "weebo")
).expanduser()
HONEYBOT_WEEBO_DIR = Path("/home/mike/www/mikelev.in/assets/weebo")


def default_wax_seal_path():
    """Return the tracked Book of Proof Wax Seal path in the Pipulate repo."""
    repo_root = Path(__file__).resolve().parents[1]
    for cand in (
        repo_root / "assets" / "images" / "ambigram-209.png",
        repo_root / "ambigram-209.png",
    ):
        if cand.is_file():
            return cand.resolve()
    return None


def read_image_dimensions(path):
    """Read (width, height) from PNG/GIF/JPEG header bytes or PIL fallback."""
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
    return 512, 512


def has_alpha_channel(path):
    """Return True when path is an image containing an alpha/transparency channel."""
    if not path or not os.path.isfile(path):
        return False
    try:
        from PIL import Image
        with Image.open(path) as im:
            return ("A" in im.getbands()) or ("transparency" in im.info)
    except Exception:
        return str(path).lower().endswith((".png", ".webp", ".gif"))


def candidate_search_dirs():
    """Return dedicated Weebo library directories (never blog post hero folders)."""
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        LOCAL_WEEBO_DIR,
        repo_root / "assets" / "weebo",
        HONEYBOT_WEEBO_DIR,
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


def enroll_in_local_library(src_path):
    """Copy an explicit local file path into ~/.local/share/pipulate/weebo/ if not already there."""
    src = Path(src_path).resolve()
    if not src.is_file() or src.suffix.lower() not in SUPPORTED_EXTS:
        return src
    repo_root = Path(__file__).resolve().parents[1].resolve()
    seal = default_wax_seal_path()
    if seal and src == seal:
        return src
    if str(src).startswith(str(repo_root / "assets")):
        return src
    try:
        LOCAL_WEEBO_DIR.mkdir(parents=True, exist_ok=True)
        dest = LOCAL_WEEBO_DIR / src.name
        if dest.resolve() != src:
            if not dest.is_file() or src.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(src, dest)
                print(f"📦 Rolled into local Weebo library: {dest} (shorthand: `weebo {dest.stem}`)", file=sys.stderr)
    except Exception:
        pass
    return src


def list_shorthand_assets(limit=50):
    """Return list of (stem, Path, role) across the Wax Seal and local Weebo library."""
    items = []
    seen_stems = set()
    seal = default_wax_seal_path()
    if seal:
        items.append(("seal / ambigram (default)", seal))
        seen_stems.add(seal.stem.lower())
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


def resolve_media_target(raw_spec, default_duration=8.0, enroll=False):
    """Resolve 'shorthand[:seconds]' or '/path/to/file[:seconds]' into (path_str, duration, kind).

    Never falls back to unrelated blog hero images; returns '' if a named asset does not exist.
    """
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
    duration = max(0.5, min(600.0, duration))

    if raw_str.startswith(("http://", "https://", "file://")):
        return raw_str, duration, _classify_ext(raw_str)

    # 1. Explicit file path on disk (absolute, ~/..., or repo-relative)
    if raw_str:
        direct = Path(raw_str).expanduser()
        if direct.is_file():
            resolved_p = enroll_in_local_library(direct) if enroll else direct.resolve()
            return str(resolved_p), duration, _classify_ext(str(resolved_p))

        repo_root = Path(__file__).resolve().parents[1]
        rel_cand = repo_root / raw_str.lstrip("/")
        if rel_cand.is_file():
            resolved = str(rel_cand.resolve())
            return resolved, duration, _classify_ext(resolved)

    needle = raw_str.lower()
    needle_stem = Path(needle).stem if needle else ""

    # 2. Dedicated Weebo library lookup (exact filename or exact stem match first, then prefix)
    if needle:
        for d in candidate_search_dirs():
            for p in d.iterdir():
                if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                if p.name.lower() == needle or p.stem.lower() == needle_stem:
                    resolved = str(p.resolve())
                    return resolved, duration, _classify_ext(resolved)

        prefix_matches = []
        for d in candidate_search_dirs():
            for p in d.iterdir():
                if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                if p.stem.lower().startswith(needle_stem):
                    prefix_matches.append((-p.stat().st_mtime, p))
        if prefix_matches:
            prefix_matches.sort(key=lambda item: item[0])
            best = str(prefix_matches[0][1].resolve())
            return best, duration, _classify_ext(best)

    # 3. Default Book of Proof Wax Seal (only when bare/default alias is used)
    if needle in DEFAULT_SEAL_ALIASES:
        seal = default_wax_seal_path()
        if seal:
            return str(seal), duration, _classify_ext(str(seal))

    return "", duration, "IMAGE"


def compute_centered_geometry(img_w, img_h, max_w=1440, max_h=840, screen_w=1920, screen_h=1080):
    """Compute (win_w, win_h, pos_x, pos_y) at 1:1 native pixel size, downscaling only if > max_w x max_h."""
    scale = min(1.0, max_w / max(1, img_w), max_h / max(1, img_h))
    win_w = max(16, int(round(img_w * scale)))
    win_h = max(16, int(round(img_h * scale)))
    pos_x = max(0, (screen_w - win_w) // 2)
    pos_y = max(0, (screen_h - win_h) // 2)
    return win_w, win_h, pos_x, pos_y


def prepare_backbuffer(src_path, max_w=1440, max_h=840, matte=False, out_path=None):
    """Prepare image at native 1:1 resolution (or downscaled if oversized), preserving RGBA alpha by default."""
    if not src_path or src_path.startswith(("http://", "https://", "file://")) or not os.path.isfile(src_path):
        w, h, x, y = compute_centered_geometry(512, 512, max_w=max_w, max_h=max_h)
        return src_path, False, w, h, x, y

    kind = _classify_ext(src_path)
    img_w, img_h = read_image_dimensions(src_path)
    win_w, win_h, pos_x, pos_y = compute_centered_geometry(img_w, img_h, max_w=max_w, max_h=max_h)

    if kind != "IMAGE":
        return src_path, False, win_w, win_h, pos_x, pos_y

    needs_resize = (win_w, win_h) != (img_w, img_h)
    if not needs_resize and not matte:
        return src_path, False, win_w, win_h, pos_x, pos_y

    try:
        from PIL import Image
        with Image.open(src_path) as raw_im:
            rgba = raw_im.convert("RGBA")
            if needs_resize:
                rgba = rgba.resize((win_w, win_h), Image.Resampling.LANCZOS)
            dest = Path(out_path) if out_path else Path(f"/tmp/weebo_buf_{os.getpid()}_{int(time.time() * 1000)}.png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if matte:
                canvas = Image.new("RGB", (win_w, win_h), OBSIDIAN_RGB)
                canvas.paste(rgba, (0, 0), mask=rgba.split()[3])
                canvas.save(dest, "PNG")
            else:
                rgba.save(dest, "PNG")
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


def _mpv_alpha_flags():
    """Return the supported mpv CLI flag list for transparent alpha windows on this mpv version."""
    if not shutil.which("mpv"):
        return []
    for candidate in (["--alpha=yes"], ["--background=none"]):
        try:
            res = subprocess.run(
                ["mpv", "--no-config", *candidate, "--version"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0:
                return candidate
        except Exception:
            pass
    return []


def _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env):
    time.sleep(0.22)
    if shutil.which("wmctrl"):
        subprocess.run(
            ["wmctrl", "-r", MEDIA_OVERLAY_MARKER, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
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


def pop_weebo(spec, duration=8.0, mute=False, matte=False, display=None, dry_run=False):
    """Pop a self-terminating, native-size, alpha-transparent media overlay on X11 without stealing focus."""
    target, dur, kind = resolve_media_target(spec, default_duration=duration, enroll=(not dry_run))
    if not target:
        print(f"⚠️ Weebo asset not found: {spec!r} (run `weebol` to list enrolled assets, or pass a file path)", file=sys.stderr)
        return 1

    img_w, img_h = read_image_dimensions(target) if os.path.isfile(target) else (512, 512)
    alpha = has_alpha_channel(target) and not matte
    alpha_flags = _mpv_alpha_flags() if alpha else []
    buf_path, temp_created, win_w, win_h, pos_x, pos_y = prepare_backbuffer(target, matte=matte)
    geom_str = f"{win_w}x{win_h}+{pos_x}+{pos_y}"

    if dry_run:
        if temp_created and buf_path != target and os.path.isfile(buf_path):
            try:
                os.remove(buf_path)
            except OSError:
                pass
        print(
            f"WEEBO_DRY_RUN: kind={kind} | resolved={target} | "
            f"native_size={img_w}x{img_h} | alpha={alpha} | alpha_flags={alpha_flags} | "
            f"geom={geom_str} | duration={dur:.1f}s"
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
            base_cmd = [
                "mpv",
                "--no-config",
                f"--title={MEDIA_OVERLAY_MARKER}",
                "--no-border",
                "--ontop",
                f"--geometry={geom_str}",
                "--keep-open=no",
                "--msg-level=all=error",
            ]
            tail_cmd = []
            if kind == "IMAGE":
                tail_cmd.append(f"--image-display-duration={dur:.1f}")
            elif kind == "GIF":
                tail_cmd.extend(["--loop-file=inf", f"--length={dur:.1f}"])
            else:
                tail_cmd.append(f"--length={dur:.1f}")
                if mute:
                    tail_cmd.append("--mute=yes")
            tail_cmd.append(buf_path)

            cmd = [*base_cmd, *alpha_flags, *tail_cmd]
            t0 = time.time()
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env)
            proc.wait(timeout=dur + 2.0)
            if proc.returncode not in (0, None) and (time.time() - t0) < 1.0:
                err_txt = (proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else "").strip()
                if alpha_flags:
                    print(f"ℹ️ mpv rejected {alpha_flags} ({err_txt}); retrying with obsidian matte...", file=sys.stderr)
                    matte_buf, matte_tmp, win_w, win_h, pos_x, pos_y = prepare_backbuffer(target, matte=True)
                    retry_cmd = [*base_cmd, *tail_cmd[:-1], matte_buf]
                    proc = subprocess.Popen(retry_cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env)
                    proc.wait(timeout=dur + 2.0)
                    if matte_tmp and matte_buf != target and os.path.isfile(matte_buf):
                        try:
                            os.remove(matte_buf)
                        except OSError:
                            pass
                elif err_txt:
                    print(f"⚠️ mpv error (exit {proc.returncode}): {err_txt}", file=sys.stderr)
        elif kind == "IMAGE" and shutil.which("feh") and os.path.isfile(buf_path):
            cmd = [
                "feh",
                "--title", MEDIA_OVERLAY_MARKER,
                "--borderless",
                "--image-bg", "black",
                "--geometry", geom_str,
                buf_path,
            ]
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env)
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
        if temp_created and buf_path != target and os.path.isfile(buf_path):
            try:
                os.remove(buf_path)
            except OSError:
                pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="Operation Weebo: Native-resolution alpha-transparent X11 overlay.")
    parser.add_argument("spec", nargs="?", default="seal", help="Shorthand name, file path, duration, or 'list' (default: seal).")
    parser.add_argument("pos_duration", nargs="?", default=None, help="Optional duration in seconds as a second word (e.g. `weebo seal 4`).")
    parser.add_argument("-d", "--duration", type=float, default=None, help="Display duration in seconds (default: 8.0).")
    parser.add_argument("--matte", action="store_true", help="Composite transparent pixels over #111111 obsidian instead of transparent X11 alpha.")
    parser.add_argument("--mute", action="store_true", help="Mute audio on video clips.")
    parser.add_argument("--remote", action="store_true", help="Deliberately stage to Honeybot and pop on :10.0.")
    parser.add_argument("--list", action="store_true", help="List available shorthand media assets.")
    parser.add_argument("--dry-run", action="store_true", help="Verify resolution and native geometry without opening X11.")
    args = parser.parse_args()

    spec_arg = str(args.spec or "seal").strip()
    dur_val = args.duration if args.duration is not None else 8.0

    # Allow bare numeric first arg (`weebo 4` -> default seal for 4 seconds)
    try:
        dur_val = float(spec_arg)
        spec_arg = "seal"
    except ValueError:
        pass

    if args.pos_duration is not None and args.duration is None:
        try:
            dur_val = float(args.pos_duration)
        except ValueError:
            pass

    if args.list or spec_arg.lower() == "list":
        assets = list_shorthand_assets()
        print(f"🤖 Operation Weebo Library ({len(assets)} asset(s) — local dir: {LOCAL_WEEBO_DIR}):")
        for label, path in assets[:30]:
            w, h = read_image_dimensions(path)
            a_tag = "alpha" if has_alpha_channel(path) else "opaque"
            print(f"   • {label:<30} [{w}x{h} {a_tag}] -> {path}")
        return 0

    if args.remote:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "articles"))
        from common import send_honeybot_live_message
        if ":" not in spec_arg and dur_val != 8.0:
            spec_arg = f"{spec_arg}:{dur_val:g}"
        return send_honeybot_live_message("", media_path=spec_arg, dry_run=args.dry_run)

    return pop_weebo(spec_arg, duration=dur_val, mute=args.mute, matte=args.matte, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
