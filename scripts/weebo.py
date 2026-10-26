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


def probe_video_metadata(path):
    """Return (width, height, duration_sec) for a video file via ffprobe."""
    if not path or not os.path.isfile(path) or not shutil.which("ffprobe"):
        return 0, 0, 0.0
    try:
        import json as _json
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height:format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        data = _json.loads(res.stdout or "{}")
        streams = data.get("streams") or []
        w = int(streams[0].get("width") or 0) if streams else 0
        h = int(streams[0].get("height") or 0) if streams else 0
        dur = float((data.get("format") or {}).get("duration") or 0.0)
        return w, h, dur
    except Exception:
        return 0, 0, 0.0


def read_image_dimensions(path):
    """Read (width, height) from PNG/GIF/JPEG header bytes, PIL, or ffprobe fallback."""
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
    vw, vh, _ = probe_video_metadata(path)
    if vw > 0 and vh > 0:
        return vw, vh
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


def _finalize_media_duration(path_str, kind, explicit_dur):
    """Use explicit_dur if provided; otherwise use full natural duration for VIDEO or 8.0s for IMAGE/GIF."""
    if explicit_dur is not None:
        return max(0.5, min(600.0, float(explicit_dur)))
    if kind == "VIDEO" and path_str and os.path.isfile(path_str):
        _, _, vdur = probe_video_metadata(path_str)
        if vdur > 0:
            return max(1.0, min(600.0, float(vdur)))
        return 20.0
    return 8.0


def resolve_media_target(raw_spec, default_duration=None, enroll=False):
    """Resolve 'shorthand[:seconds]' or '/path/to/file[:seconds]' into (path_str, duration, kind).

    Never falls back to unrelated blog hero images; returns '' if a named asset does not exist.
    """
    explicit_dur = default_duration
    if isinstance(raw_spec, dict):
        raw_str = str(raw_spec.get("path") or raw_spec.get("url") or "").strip()
        if raw_spec.get("duration") is not None:
            explicit_dur = float(raw_spec["duration"])
    else:
        raw_str = str(raw_spec or "").strip()
        if ":" in raw_str and not raw_str.startswith(("http://", "https://", "file://")):
            head, tail = raw_str.rsplit(":", 1)
            try:
                explicit_dur = float(tail.strip())
                raw_str = head.strip()
            except ValueError:
                pass

    if raw_str.startswith(("http://", "https://", "file://")):
        kind = _classify_ext(raw_str)
        return raw_str, _finalize_media_duration(raw_str, kind, explicit_dur), kind

    # 1. Explicit file path on disk (absolute, ~/..., or repo-relative)
    if raw_str:
        direct = Path(raw_str).expanduser()
        if direct.is_file():
            resolved_p = enroll_in_local_library(direct) if enroll else direct.resolve()
            s_path = str(resolved_p)
            kind = _classify_ext(s_path)
            return s_path, _finalize_media_duration(s_path, kind, explicit_dur), kind

        repo_root = Path(__file__).resolve().parents[1]
        rel_cand = repo_root / raw_str.lstrip("/")
        if rel_cand.is_file():
            resolved = str(rel_cand.resolve())
            kind = _classify_ext(resolved)
            return resolved, _finalize_media_duration(resolved, kind, explicit_dur), kind

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
                    kind = _classify_ext(resolved)
                    return resolved, _finalize_media_duration(resolved, kind, explicit_dur), kind

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
            kind = _classify_ext(best)
            return best, _finalize_media_duration(best, kind, explicit_dur), kind

    # 3. Default Book of Proof Wax Seal (only when bare/default alias is used)
    if needle in DEFAULT_SEAL_ALIASES:
        seal = default_wax_seal_path()
        if seal:
            s_path = str(seal)
            kind = _classify_ext(s_path)
            return s_path, _finalize_media_duration(s_path, kind, explicit_dur), kind

    return "", _finalize_media_duration("", "IMAGE", explicit_dur), "IMAGE"


def get_screen_dimensions(env=None):
    """Query live XFCE/X11 desktop geometry (screen_w, screen_h, origin_x, origin_y)."""
    import re
    q_env = env if env is not None else os.environ.copy()
    if not q_env.get("DISPLAY"):
        q_env["DISPLAY"] = ":0"
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


def compute_centered_geometry(img_w, img_h, max_w=1440, max_h=840, screen_w=None, screen_h=None, env=None):
    """Align the center of the image (win_w/2, win_h/2) with the center of the XFCE desktop (screen_w/2, screen_h/2)."""
    ox, oy = 0, 0
    if screen_w is None or screen_h is None:
        screen_w, screen_h, ox, oy = get_screen_dimensions(env=env)
    eff_max_w = min(max_w, max(256, int(screen_w * 0.85)))
    eff_max_h = min(max_h, max(256, int(screen_h * 0.85)))
    scale = min(1.0, eff_max_w / max(1, img_w), eff_max_h / max(1, img_h))
    win_w = max(16, int(round(img_w * scale)))
    win_h = max(16, int(round(img_h * scale)))
    pos_x = max(0, (ox + (screen_w // 2)) - (win_w // 2))
    pos_y = max(0, (oy + (screen_h // 2)) - (win_h // 2))
    return win_w, win_h, pos_x, pos_y


def prepare_backbuffer(src_path, max_w=1440, max_h=840, matte=False, out_path=None, env=None):
    """Prepare image at native 1:1 resolution (or downscaled if oversized), preserving RGBA alpha by default."""
    if not src_path or src_path.startswith(("http://", "https://", "file://")) or not os.path.isfile(src_path):
        w, h, x, y = compute_centered_geometry(512, 512, max_w=max_w, max_h=max_h, env=env)
        return src_path, False, w, h, x, y

    kind = _classify_ext(src_path)
    img_w, img_h = read_image_dimensions(src_path)
    win_w, win_h, pos_x, pos_y = compute_centered_geometry(img_w, img_h, max_w=max_w, max_h=max_h, env=env)

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


def _build_1bit_alpha_mask(img_path, win_w, win_h, threshold=24):
    """Pack an image's alpha channel (> threshold) into X11 XBM 1-bit LSB-first row bytes."""
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
        return None


def _apply_x11_shape_mask(win_id, mask_bytes, win_w, win_h, env, pos_x=None, pos_y=None):
    """Apply a 1-bit cookie-cutter XShapeCombineMask and exact centered (pos_x, pos_y) to an X11 window ID."""
    if not win_id:
        return False
    try:
        import ctypes
        x11_path = _find_x11_lib("libX11.so.6")
        xext_path = _find_x11_lib("libXext.so.6")
        libX11 = ctypes.CDLL(x11_path)
        libXext = ctypes.CDLL(xext_path)
        libX11.XMoveResizeWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint
        ]

        libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        libX11.XOpenDisplay.restype = ctypes.c_void_p
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

        dpy_name = (env.get("DISPLAY") or ":0").encode("utf-8")
        dpy = libX11.XOpenDisplay(dpy_name)
        if not dpy:
            return False
        try:
            wid = int(str(win_id).strip(), 0)
            if pos_x is not None and pos_y is not None:
                libX11.XMoveResizeWindow(dpy, wid, int(pos_x), int(pos_y), int(win_w), int(win_h))
            if mask_bytes:
                bmap = libX11.XCreateBitmapFromData(dpy, wid, mask_bytes, int(win_w), int(win_h))
                if bmap:
                    # ShapeBounding = 0, ShapeClip = 2, ShapeSet = 0
                    libXext.XShapeCombineMask(dpy, wid, 0, 0, 0, bmap, 0)
                    libXext.XShapeCombineMask(dpy, wid, 2, 0, 0, bmap, 0)
                    libX11.XFreePixmap(dpy, bmap)
            libX11.XFlush(dpy)
            return True
        finally:
            libX11.XCloseDisplay(dpy)
    except Exception:
        return False


def _pop_with_qt(buf_path, kind, dur, pos_x, pos_y, win_w, win_h, alpha, env):
    """Pop a true cookie-cutter frameless overlay using PyQt6 setMask() + WA_TranslucentBackground."""
    import importlib.util
    if not importlib.util.find_spec("PyQt6") or kind not in ("IMAGE", "GIF"):
        return False
    qt_code = """
import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMovie, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel

path, kind, dur, x, y, w, h, use_alpha, title = (
    sys.argv[1], sys.argv[2], float(sys.argv[3]),
    int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]),
    sys.argv[8] == "1", sys.argv[9]
)
app = QApplication(sys.argv[:1])
lbl = QLabel()
lbl.setWindowTitle(title)
lbl.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowDoesNotAcceptFocus
)
lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
lbl.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
lbl.setGeometry(x, y, w, h)
if kind == "GIF":
    movie = QMovie(path)
    lbl.setMovie(movie)
    if use_alpha:
        def _upd():
            px = movie.currentPixmap()
            if not px.isNull() and not px.mask().isNull():
                lbl.setMask(px.mask())
        movie.frameChanged.connect(lambda _: _upd())
    movie.start()
else:
    px = QPixmap(path).scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    lbl.setPixmap(px)
    if use_alpha and not px.mask().isNull():
        lbl.setMask(px.mask())
lbl.show()
QTimer.singleShot(max(100, int(dur * 1000)), app.quit)
sys.exit(app.exec())
"""
    try:
        res = subprocess.run(
            [
                sys.executable, "-c", qt_code,
                str(buf_path), str(kind), str(dur),
                str(pos_x), str(pos_y), str(win_w), str(win_h),
                "1" if alpha else "0", MEDIA_OVERLAY_MARKER,
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=dur + 2.5,
            check=False,
        )
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        return True
    except Exception:
        return False


def _mpv_alpha_flags():
    """Return the supported mpv CLI flag list for transparent alpha windows on this mpv version."""
    if not shutil.which("mpv"):
        return []
    for candidate in (
        ["--gpu-context=x11egl", "--background=none"],
        ["--alpha=yes"],
        ["--background=none"],
    ):
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


def _find_overlay_window_id(env, attempts=8, delay=0.05):
    """Poll xdotool for the honeybot_media_overlay X11 window ID."""
    if not shutil.which("xdotool"):
        return ""
    for _ in range(attempts):
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
                return lines[-1]
        except Exception:
            pass
        time.sleep(delay)
    return ""


def _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env, mask_bytes=None):
    overlay_wid = _find_overlay_window_id(env)
    if not overlay_wid:
        time.sleep(0.20)
        overlay_wid = _find_overlay_window_id(env, attempts=3, delay=0.04)
    if overlay_wid:
        _apply_x11_shape_mask(overlay_wid, mask_bytes, win_w, win_h, env, pos_x=pos_x, pos_y=pos_y)
        if shutil.which("xdotool"):
            subprocess.run(
                [
                    "xdotool", "windowsize", str(overlay_wid), str(win_w), str(win_h),
                    "windowmove", str(overlay_wid), str(pos_x), str(pos_y),
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    if shutil.which("wmctrl"):
        target_flag = ["-i", "-r", str(overlay_wid)] if overlay_wid else ["-r", MEDIA_OVERLAY_MARKER]
        subprocess.run(
            ["wmctrl", *target_flag, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            ["wmctrl", *target_flag, "-b", "add,above"],
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


def pop_weebo(spec, duration=None, mute=False, matte=False, display=None, dry_run=False):
    """Pop a self-terminating, native-size, alpha-transparent media overlay on X11 without stealing focus."""
    target, dur, kind = resolve_media_target(spec, default_duration=duration, enroll=(not dry_run))
    if not target:
        print(f"⚠️ Weebo asset not found: {spec!r} (run `weebol` to list enrolled assets, or pass a file path)", file=sys.stderr)
        return 1

    q_env = os.environ.copy()
    q_env["DISPLAY"] = display if display else (q_env.get("DISPLAY") or ":0")
    scr_w, scr_h, scr_ox, scr_oy = get_screen_dimensions(env=q_env)
    img_w, img_h = read_image_dimensions(target) if os.path.isfile(target) else (512, 512)
    alpha = has_alpha_channel(target) and not matte
    alpha_flags = _mpv_alpha_flags() if alpha else []
    buf_path, temp_created, win_w, win_h, pos_x, pos_y = prepare_backbuffer(target, matte=matte, env=q_env)
    mask_bytes = _build_1bit_alpha_mask(buf_path, win_w, win_h) if (alpha and kind == "IMAGE") else None
    xshape_ok = bool(mask_bytes and os.path.isfile(_find_x11_lib("libXext.so.6")))
    geom_str = f"{win_w}x{win_h}+{pos_x}+{pos_y}"

    if dry_run:
        if temp_created and buf_path != target and os.path.isfile(buf_path):
            try:
                os.remove(buf_path)
            except OSError:
                pass
        print(
            f"WEEBO_DRY_RUN: kind={kind} | resolved={target} | "
            f"screen={scr_w}x{scr_h}+{scr_ox}+{scr_oy} | native_size={img_w}x{img_h} | "
            f"alpha={alpha} | xshape_cutout={xshape_ok} | "
            f"alpha_flags={alpha_flags} | geom={geom_str} | duration={dur:.1f}s"
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
        if _pop_with_qt(buf_path, kind, dur, pos_x, pos_y, win_w, win_h, alpha, env):
            if orig_win and shutil.which("xdotool"):
                subprocess.run(
                    ["xdotool", "windowactivate", orig_win],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            return 0
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
            _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env, mask_bytes=mask_bytes)
            proc.wait(timeout=dur + 2.0)
            if proc.returncode not in (0, None) and (time.time() - t0) < 1.0:
                err_txt = (proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else "").strip()
                if alpha_flags:
                    print(f"ℹ️ mpv rejected {alpha_flags} ({err_txt}); retrying with XShape cutout...", file=sys.stderr)
                    retry_cmd = [*base_cmd, *tail_cmd]
                    proc = subprocess.Popen(retry_cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env, mask_bytes=mask_bytes)
                    proc.wait(timeout=dur + 2.0)
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
            _pin_above_and_restore_focus(orig_win, pos_x, pos_y, win_w, win_h, env, mask_bytes=mask_bytes)
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


def print_weebo_cheatsheet():
    """Print the yt-style Operation Weebo muscle-memory cheat sheet."""
    bar = "=" * 72
    thin = "-" * 72
    seal = default_wax_seal_path()
    assets = list_shorthand_assets()
    print(f"\n{bar}")
    print("🤖 OPERATION WEEBO CHEAT SHEET (1:1 Native-Pixel Cookie-Cutter Overlay)")
    print(thin)
    print("PHASE 1: LOCAL POPUPS ON PIPULATE PRIME (Test & Enroll)")
    print("  1. weebo                        📋 Show this Operation Weebo cheat sheet")
    print("  2. weebo <seconds>              🔴 Pop the Book of Proof Wax Seal (e.g. `weebo 4`)")
    print("  3. weebo seal [sec]             🔴 Pop the default 209x209 Wax Seal (`wax` / `ambigram`)")
    print("  4. weebo /path/to/img.png [sec] 📦 Pop at 1:1 pixel size & roll into local library")
    print("  5. weebo <shorthand> [sec]      ⚡ Pop any enrolled asset by stem name (no path/ext)")
    print("  6. weebol                       📚 List the Wax Seal + all enrolled local assets")
    print(thin)
    print("PHASE 2: DELIBERATE REMOTE POPUPS ON HONEYBOT (:10.0 Broadcast Stage)")
    print("  7. weeboh <seconds>             📡 Pop the 209x209 Wax Seal on Honeybot :10.0 (e.g. `weeboh 4`)")
    print("  8. weeboh <name|path> [sec]     📡 Stage asset via scp -> ~/www/mikelev.in/assets/weebo/")
    print("                                     and pop live over narration without cutting voice")
    print("  9. ytsay -m <name> \"message\"    🎬 Preempt voice + pop Weebo graphic with spoken announcement")
    print(thin)
    print("PHASE 3: INLINE ARTICLE PLAYER-PIANO CUES (Markdown -> Score -> Stream)")
    print("  9. [[[weebo:seal]]]             📜 Pop Wax Seal for 8s at that paragraph boundary")
    print(" 10. [[[weebo:ambigram-454:6]]]   📜 Pop named asset for 6s during article narration")
    print(" 11. <!-- weebo: seal duration=5 --> HTML comment form (stripped from visible page)")
    print(thin)
    print(f"🔴 Default Wax Seal  : {seal or 'MISSING'}")
    print(f"📦 Local Library Dir : {LOCAL_WEEBO_DIR} ({len(assets)} asset(s) available — type `weebol`)")
    print(bar)
    return 0


def main():
    if len(sys.argv) == 1:
        return print_weebo_cheatsheet()

    parser = argparse.ArgumentParser(description="Operation Weebo: Native-resolution alpha-transparent X11 overlay.")
    parser.add_argument("spec", nargs="?", default="seal", help="Shorthand name, file path, duration, 'help', or 'list' (default: seal).")
    parser.add_argument("pos_duration", nargs="?", default=None, help="Optional duration in seconds as a second word (e.g. `weebo seal 4`).")
    parser.add_argument("-d", "--duration", type=float, default=None, help="Display duration in seconds (default: 8.0).")
    parser.add_argument("--matte", action="store_true", help="Composite transparent pixels over #111111 obsidian instead of transparent X11 alpha.")
    parser.add_argument("--mute", action="store_true", help="Mute audio on video clips.")
    parser.add_argument("--remote", action="store_true", help="Deliberately stage to Honeybot and pop on :10.0.")
    parser.add_argument("--list", action="store_true", help="List available shorthand media assets.")
    parser.add_argument("--dry-run", action="store_true", help="Verify resolution and native geometry without opening X11.")
    args = parser.parse_args()

    spec_arg = str(args.spec or "seal").strip()
    if spec_arg.lower() == "help":
        return print_weebo_cheatsheet()
    dur_val = args.duration

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
        from common import HONEYBOT_SSH_HOST, send_honeybot_live_message
        import re as _re
        target, dur, _ = resolve_media_target(spec_arg, default_duration=dur_val, enroll=(not args.dry_run))
        remote_target = spec_arg
        local_p = Path(target).resolve() if (target and os.path.isfile(target)) else None
        if local_p is not None:
            safe_fname = _re.sub(r"[^A-Za-z0-9._-]", "_", local_p.name)
            remote_target = f"/home/mike/www/mikelev.in/assets/weebo/{safe_fname}"
        if args.dry_run:
            w_dim, h_dim = read_image_dimensions(target) if (target and os.path.isfile(target)) else (512, 512)
            print(
                f"WEEBO_REMOTE_DRY_RUN: host={HONEYBOT_SSH_HOST} | staged={remote_target} | "
                f"native_size={w_dim}x{h_dim} | duration={dur:.1f}s | mode=direct_proc_env_verified"
            )
            return 0
        import json as _json
        stage_cache_file = Path("/tmp/pipulate_weebo_staged.json")
        try:
            stage_cache = _json.loads(stage_cache_file.read_text(encoding="utf-8")) if stage_cache_file.is_file() else {}
        except Exception:
            stage_cache = {}
        repo_stream = Path(__file__).resolve().parents[1] / "remotes" / "honeybot" / "scripts" / "stream.py"
        if repo_stream.is_file():
            st_stat = repo_stream.stat()
            st_sig = [st_stat.st_size, st_stat.st_mtime_ns]
            if stage_cache.get("__stream_py__") != st_sig:
                if subprocess.run(
                    ["scp", "-q", str(repo_stream), f"{HONEYBOT_SSH_HOST}:/home/mike/www/mikelev.in/scripts/stream.py"],
                    check=False,
                ).returncode == 0:
                    stage_cache["__stream_py__"] = st_sig
        if local_p is not None:
            lp_stat = local_p.stat()
            lp_sig = [lp_stat.st_size, lp_stat.st_mtime_ns]
            if stage_cache.get(remote_target) != lp_sig:
                subprocess.run(
                    ["ssh", HONEYBOT_SSH_HOST, "mkdir", "-p", "/home/mike/www/mikelev.in/assets/weebo"],
                    check=False,
                )
                scp_res = subprocess.run(
                    ["scp", "-q", str(local_p), f"{HONEYBOT_SSH_HOST}:{remote_target}"],
                    check=False,
                )
                if scp_res.returncode == 0:
                    stage_cache[remote_target] = lp_sig
                    print(f"🖼️  Staged local media to Honeybot: {local_p.name} -> {remote_target}")
        try:
            stage_cache_file.write_text(_json.dumps(stage_cache), encoding="utf-8")
        except Exception:
            pass
        remote_launcher = r'''
import os, pathlib, subprocess, sys, time
target, dur = sys.argv[1], sys.argv[2]
sys.path.insert(0, "/home/mike/www/mikelev.in/scripts")
import stream
env = stream._hydrate_honeybot_x11_env()
py_exe = sys.executable
for p in sorted(pathlib.Path("/proc").glob("[0-9]*/cmdline")):
    try:
        raw = p.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
        if "stream.py" in raw and "--conjure-media" not in raw:
            exe_cand = os.path.realpath(str(p.parent / "exe"))
            if os.path.isfile(exe_cand):
                py_exe = exe_cand
                break
    except Exception:
        pass
log_f = open("/tmp/honeybot_weebo.log", "w", encoding="utf-8")
proc = subprocess.Popen(
    [py_exe, "/home/mike/www/mikelev.in/scripts/stream.py", "--conjure-media", target, dur],
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=log_f,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
win_line = ""
for _ in range(70):
    time.sleep(0.04)
    r = subprocess.run(["wmctrl", "-lG"], env=env, capture_output=True, text=True, check=False)
    for ln in (r.stdout or "").splitlines():
        if "honeybot_media_overlay" in ln:
            win_line = ln.strip()
            break
    if win_line or proc.poll() is not None:
        break
if win_line:
    print(f"LIVE_X11_WINDOW: {win_line}")
    sys.exit(0)
if proc.poll() is None:
    try:
        proc.terminate()
    except Exception:
        pass
log_f.flush()
err = pathlib.Path("/tmp/honeybot_weebo.log").read_text(encoding="utf-8", errors="replace").strip()
print(f"WEEBO_LAUNCH_ERR: poll={proc.poll()} log={err!r}")
sys.exit(1)
'''
        res = subprocess.run(
            ["ssh", HONEYBOT_SSH_HOST, "python3", "-", remote_target, f"{dur:.1f}"],
            input=remote_launcher,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (res.stdout or "").strip()
        if res.returncode == 0 and "LIVE_X11_WINDOW:" in out:
            print(f"📡 Popped centered Weebo overlay on Honeybot :10.0: [{Path(remote_target).name} ({dur:g}s)]")
            print(f"   ↳ {out}")
            return 0
        print(f"⚠️ Direct conjure diagnostic: {out} {(res.stderr or '').strip()}", file=sys.stderr)
        return 1

    return pop_weebo(spec_arg, duration=dur_val, mute=args.mute, matte=args.matte, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
