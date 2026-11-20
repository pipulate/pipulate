import html
import os
import re
import sys
import time
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None


def _safe_load_frontmatter(fm_raw: str) -> dict:
    """Parse YAML frontmatter via CSafeLoader/safe_load, with stdlib scalar fallback if PyYAML is absent."""
    if yaml is not None:
        try:
            loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
            data = yaml.load(fm_raw, Loader=loader)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    out, img_path, in_img = {}, "", False
    for ln in (fm_raw or "").splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if in_img and ln.startswith((" ", "\t")):
            m_sub = re.match(r"^\s+path:\s*(.+?)\s*$", ln)
            if m_sub:
                img_path = m_sub.group(1).strip("'\"")
            continue
        in_img = False
        m_kv = re.match(r"^([A-Za-z0-9_]+):\s*(.*?)\s*$", ln)
        if not m_kv:
            continue
        k, v = m_kv.group(1), m_kv.group(2).strip("'\"")
        if k == "image" and not m_kv.group(2):
            in_img = True
        elif v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        elif re.match(r"^-?\d+$", v):
            out[k] = int(v)
        else:
            out[k] = v
    if img_path:
        out["image"] = {"path": img_path}
    return out

# Path to your Jekyll posts on the Honeybot (with local workstation fallback for probes)
_HONEYBOT_POSTS_DIR = Path("/home/mike/www/mikelev.in/_posts")
_LOCAL_POSTS_DIR = Path.home() / "repos" / "trimnoir" / "_posts"
POSTS_DIR = _HONEYBOT_POSTS_DIR if _HONEYBOT_POSTS_DIR.is_dir() else _LOCAL_POSTS_DIR
BASE_URL = "https://mikelev.in"

# ... existing imports ...

# Global cache to track state (preserved across importlib.reload)
_last_scan_time = globals().get("_last_scan_time", 0)
_last_file_count = globals().get("_last_file_count", 0)

# The breaking-news bell. The post-receive hook writes a fresh epoch timestamp here
# on every push, which lets us retry "read the newest article" even when the article
# content itself did not change (e.g. an --allow-empty re-push).
TRIGGER_FILE = Path("/home/mike/www/mikelev.in/.reading_trigger")
_last_trigger = globals().get("_last_trigger", None)

# The deploy stand-by bell. The post-receive hook writes a fresh epoch timestamp
# here at the START of a deploy (before the long build), so the stream can announce
# "stand by" and HOLD narration instead of thrashing through the whole build.
STANDBY_FILE = Path("/home/mike/www/mikelev.in/.deploy_standby")
_last_standby = globals().get("_last_standby", "__UNINIT__")


def check_standby():
    """Fires once when a new deploy BEGINS (the standby bell changes).

    Lets the stream gracefully announce incoming updates and pause narration
    before the multi-second Jekyll build + dye pass would otherwise thrash the
    Piper TTS engine."""
    global _last_standby
    try:
        current = STANDBY_FILE.read_text().strip()
    except FileNotFoundError:
        current = None
    if _last_standby == "__UNINIT__":
        _last_standby = current
        return False
    if current is not None and current != _last_standby:
        _last_standby = current
        return True
    return False


# The Live Operator Break-In ("Max Headroom" channel).
# Dropped over SSH from Pipulate Prime as JSON or plain text; unlinked immediately
# on read so a one-shot live audience greeting never replays on future restarts.
LIVE_MESSAGE_FILE = Path("/home/mike/www/mikelev.in/.live_message")


def check_live_message():
    """Read and consume a one-shot live operator message if present."""
    if not LIVE_MESSAGE_FILE.exists():
        return None
    try:
        raw = LIVE_MESSAGE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    finally:
        try:
            LIVE_MESSAGE_FILE.unlink(missing_ok=True)
        except OSError:
            pass
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            import json
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    lines = raw.splitlines()
    if lines and lines[0].upper().startswith("CARD:"):
        card_label = lines[0][5:].strip() or "LIVE\\nMESSAGE"
        say_text = " ".join(line.strip() for line in lines[1:] if line.strip())
        return {"card": card_label, "say": say_text}
    return {"card": "LIVE\\nMESSAGE", "say": " ".join(line.strip() for line in lines if line.strip())}

def trigger_is_fresh(max_age_seconds=900):
    """True if the breaking-news bell (.reading_trigger) was rung within the last
    max_age_seconds. Reads the file's mtime, so it is process-boundary safe: it
    works for a freshly-restarted stream that has no in-memory history and cannot
    lean on check_for_updates()'s first-run baseline absorption.

    Failure-mode-safe in both directions. A miss (stale/absent trigger, or a
    publish whose [4/4] restart lands outside the window) returns False and the
    caller falls back to the normal cold-start preamble -- no breakage. A generous
    window only risks leading with the newest article after a near-publish crash,
    which is an acceptable cold-start opening anyway."""
    try:
        return (time.time() - TRIGGER_FILE.stat().st_mtime) <= max_age_seconds
    except (FileNotFoundError, OSError):
        return False


JUKEBOX_REQUEST_FILE = Path("/home/mike/www/mikelev.in/.jukebox_request")
_DATED_JB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.(?:md|markdown)$")
_SORT_ORDER_RE = re.compile(r"^\s*sort_order:\s*['\"]?(-?\d+)['\"]?", re.MULTILINE)
_ARTICLE_ID_RE = re.compile(r"^article_id\s*:\s*['\"]?([1-9]\d*)['\"]?\s*(?:#.*)?$")
_jb_catalog_cache = globals().get("_jb_catalog_cache", {})
if "id_map" not in _jb_catalog_cache:
    _jb_catalog_cache = {"sig": None, "paths": [], "id_map": {}, "index_map": {}}
ABSTRACTS_SUBDIR = "_abstracts"
_PARENT_BACKFILL_KEYS = ("permalink", "sort_order", "image", "article_id", "storytime_featured", "storytime_order", "ticker_tag")
_TICKER_STOPWORDS = frozenset({
    "THE", "A", "AN", "AND", "OR", "BUT", "FOR", "NOR", "ON", "AT", "TO", "FROM",
    "BY", "WITH", "IN", "OF", "INTO", "OVER", "AFTER", "UNDER", "HOW", "WHY", "WHAT",
    "WHEN", "WHERE", "WHO", "YOUR", "OUR", "MY", "THIS", "THAT", "IS", "ARE", "WAS",
    "WERE", "BE", "IT", "ITS", "AS", "VS", "VIA", "KILL", "KILLING", "KILLS", "RETIRE",
    "RETIRING", "AUTOMATED", "BUILDING", "MAKING", "USING", "TURNING",
})


def resolve_ticker_tag(fm: dict, raw_title: str = "", slug: str = "", max_chars: int = 18) -> str:
    """Resolve a <=18-char 1-2 word uppercase LED ticker topic tag from YAML `ticker_tag` or slug/title."""
    explicit = str((fm or {}).get("ticker_tag") or "").strip().upper()
    explicit = re.sub(r"[^A-Z0-9 ./+&:#!?'-]+", " ", explicit)
    explicit = " ".join(explicit.split())
    if explicit:
        return explicit[:max_chars].rstrip()
    src = (slug or "").split("/")[-1].replace("-", " ") or raw_title
    toks = [t.upper() for t in re.findall(r"[A-Za-z0-9]+", src) if t.upper() not in _TICKER_STOPWORDS]
    if not toks:
        return "STORY-TIME"
    if len(toks) >= 2 and len(f"{toks[0]} {toks[1]}") <= max_chars:
        return f"{toks[0]} {toks[1]}"
    return toks[0][:max_chars]

def _read_frontmatter_dict(filepath: Path) -> dict:
    """Stream YAML frontmatter up to closing `---` without reading the post body."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            if fh.readline().strip() == "---":
                lines = []
                for ln in fh:
                    if ln.strip() == "---":
                        return _safe_load_frontmatter("".join(lines))
                    lines.append(ln)
    except OSError:
        pass
    return {}

def resolve_storytime_dir(posts_dir: Path | None = None) -> Path:
    """Return `POSTS_DIR / '_abstracts'` when it holds >=1 Storytime-eligible dated `.md` file, else `POSTS_DIR`."""
    base = Path(posts_dir) if posts_dir is not None else POSTS_DIR
    abs_dir = base / ABSTRACTS_SUBDIR
    try:
        if abs_dir.is_dir() and any(
            e.is_file() and _DATED_JB_RE.match(e.name) and _is_storytime_enabled(_read_frontmatter_dict(Path(e.path)))
            for e in os.scandir(abs_dir)
        ):
            return abs_dir
    except OSError:
        pass
    return base

def _with_parent_frontmatter(filepath: Path, fm: dict, posts_dir: Path | None = None) -> dict:
    base = Path(posts_dir) if posts_dir is not None else POSTS_DIR
    pfm = _read_frontmatter_dict(base / filepath.name) if filepath.parent != base else {}
    return {**fm, **{k: pfm[k] for k in _PARENT_BACKFILL_KEYS if k in pfm and fm.get(k) in (None, "")}} if pfm else fm

def _resolve_canonical_slug(fm: dict, filename: str) -> str:
    perm = str(fm.get("permalink") or "").strip("/")
    if not perm and fm.get("source_url"):
        perm = urlparse(str(fm["source_url"]).strip()).path.strip("/")
    return perm or filename[11:].rsplit(".", 1)[0]


JUKEBOX_RESERVED_IDS = frozenset({911})


def get_jukebox_catalog(posts_dir: Path | None = None):
    """Return O(1)-cached Norma-abstract Jukebox catalog ({'paths', 'id_map', 'index_map', 'playable_ids'})."""
    base = Path(posts_dir) if posts_dir is not None else POSTS_DIR
    abs_dir = base / ABSTRACTS_SUBDIR
    active_key = str(abs_dir)
    if not abs_dir.is_dir():
        return {"paths": [], "id_map": {}, "index_map": {}, "playable_ids": []}
    try:
        dir_mtime = abs_dir.stat().st_mtime_ns
        if (_jb_catalog_cache.get("sig") or (None,))[0] == active_key and _jb_catalog_cache.get("dir_mtime") == dir_mtime and "playable_ids" in _jb_catalog_cache:
            return _jb_catalog_cache
        dated = [Path(e.path) for e in os.scandir(abs_dir) if e.is_file() and _DATED_JB_RE.match(e.name)]
        sig = (active_key, dir_mtime, len(dated))
    except OSError:
        return {"paths": [], "id_map": {}, "index_map": {}, "playable_ids": []}
    if _jb_catalog_cache.get("sig") == sig and "playable_ids" in _jb_catalog_cache:
        _jb_catalog_cache["dir_mtime"] = dir_mtime
        return _jb_catalog_cache
    keyed = []
    fm_by_path = {}
    for p in dated:
        fm = _with_parent_frontmatter(p, _read_frontmatter_dict(p), posts_dir=base)
        if not _is_storytime_enabled(fm):
            continue
        raw_so = str(fm.get("sort_order") or "").strip()
        s_ord = int(raw_so) if raw_so.lstrip("-").isdigit() else 0
        raw_aid = str(fm.get("article_id") or "").split("#", 1)[0].strip()
        aid = int(raw_aid) if raw_aid.isdigit() and int(raw_aid) > 0 else None
        if aid is None or aid in JUKEBOX_RESERVED_IDS:
            continue
        fm_by_path[p] = fm
        keyed.append(((p.name[:10], s_ord, p.name), aid, p))
    keyed.sort(key=lambda item: item[0])
    paths, id_map, idx_map, meta_map = [], {}, {}, {}
    for _, aid, p in keyed:
        if aid not in id_map:
            paths.append(p)
            id_map[aid] = p
            idx_map[p.name] = aid
            fm_p = fm_by_path.get(p) or {}
            slug_p = _resolve_canonical_slug(fm_p, p.name)
            rtitle_p = str(fm_p.get("title") or slug_p.replace("-", " "))
            meta_map[aid] = {
                "jukebox_index": aid,
                "date": p.name[:10],
                "filename": p.name,
                "slug": slug_p,
                "raw_title": rtitle_p,
                "spoken_title": _apply_tts_pronunciations(rtitle_p),
                "ticker_tag": resolve_ticker_tag(fm_p, raw_title=rtitle_p, slug=slug_p),
                "short_url": f"MikeLev.in/{aid}",
            }
    seen_ids = set()
    playable_ids = [
        aid for _, aid, _ in reversed(keyed)
        if aid in id_map and not (aid in seen_ids or seen_ids.add(aid))
    ]
    _jb_catalog_cache.update({
        "dir_mtime": dir_mtime,
        "sig": sig,
        "paths": paths,
        "id_map": id_map,
        "index_map": idx_map,
        "meta_map": meta_map,
        "playable_ids": playable_ids,
    })
    return _jb_catalog_cache


def get_jukebox_playable_ids(posts_dir: Path | None = None) -> list[int]:
    """Return newest-first list of playable Norma-converted Story IDs (excluding reserved 911)."""
    return list(get_jukebox_catalog(posts_dir=posts_dir).get("playable_ids") or [])


def get_jukebox_menu_entries(limit: int = 12, posts_dir: Path | None = None) -> list[dict]:
    """Return newest-first O(1)-cached metadata dicts for playable Norma Story-Time episodes."""
    cat = get_jukebox_catalog(posts_dir=posts_dir)
    meta_map = cat.get("meta_map") or {}
    ids = cat.get("playable_ids") or []
    return [dict(meta_map[aid]) for aid in ids[: max(1, int(limit))] if aid in meta_map]


def get_article_by_jukebox_index(jb_idx: int):
    """Load a single dated post by its permanent 1-based chronological Jukebox index (1..N)."""
    id_map = get_jukebox_catalog().get("id_map") or {}
    idx = int(jb_idx or 0)
    filepath = id_map.get(idx)
    if filepath is None or not filepath.is_file():
        return None
    post_date = datetime.strptime(filepath.name[:10], "%Y-%m-%d").date()
    raw_text = filepath.read_text(encoding="utf-8")
    fm, body = {}, raw_text
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            fm = _safe_load_frontmatter(parts[1])
            body = parts[2]
    fm = _with_parent_frontmatter(filepath, fm)
    slug = _resolve_canonical_slug(fm, filepath.name)
    fm_img = fm.get("image")
    img_path = str(fm_img.get("path") or "").strip() if isinstance(fm_img, dict) else (fm_img.strip() if isinstance(fm_img, str) else "")
    raw_title = str(fm.get("title") or slug.replace("-", " "))
    return {
        "id": f"#{idx}: {raw_title} ({post_date})",
        "slug": slug,
        "filename": filepath.name,
        "jukebox_index": idx,
        "ticker_tag": resolve_ticker_tag(fm, raw_title=raw_title, slug=slug),
        "raw_title": raw_title,
        "date": post_date,
        "title": _apply_tts_pronunciations(raw_title),
        "url": f"{BASE_URL}/{slug}/",
        "image": img_path,
        "content": clean_markdown(body, label=filepath.name, census=False),
    }


def check_jukebox_request():
    """Read and consume a one-shot .jukebox_request {'index': N} if present."""
    if not JUKEBOX_REQUEST_FILE.exists():
        return None
    try:
        raw = JUKEBOX_REQUEST_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    finally:
        JUKEBOX_REQUEST_FILE.unlink(missing_ok=True)
    try:
        import json
        val = json.loads(raw).get("index") if raw.startswith("{") else int(raw)
        return int(val) if int(val) > 0 else None
    except Exception:
        return None


def has_pending_update():
    """Non-consuming peek: True when .jukebox_request, .deploy_standby, or .reading_trigger changed."""
    if JUKEBOX_REQUEST_FILE.exists():
        return True
    try:
        cur_standby = STANDBY_FILE.read_text().strip()
    except FileNotFoundError:
        cur_standby = None
    if _last_standby != "__UNINIT__" and cur_standby is not None and cur_standby != _last_standby:
        return True
    if _last_scan_time == 0:
        return False
    try:
        cur_trig = TRIGGER_FILE.read_text().strip()
    except FileNotFoundError:
        cur_trig = None
    if cur_trig is not None and cur_trig != _last_trigger:
        return True
    return False


def check_for_updates():
    """
    Checks if the _posts directory has changed since the last playlist generation.
    Returns True if updates are detected.
    """
    global _last_scan_time, _last_file_count, _last_trigger
    
    try:
        # Get directory stats
        active_dir = resolve_storytime_dir()
        stat = active_dir.stat()
        current_mtime = stat.st_mtime

        # Also check file count (sometimes mtime on dir doesn't update on all FS)
        current_files = list(active_dir.glob("*.md")) + list(active_dir.glob("*.markdown"))
        current_count = len(current_files)

        # Read the breaking-news bell rung by the post-receive hook on every push.
        current_trigger = None
        try:
            current_trigger = TRIGGER_FILE.read_text().strip()
        except FileNotFoundError:
            current_trigger = None
        
        # First run logic
        if _last_scan_time == 0:
            _last_scan_time = current_mtime
            _last_file_count = current_count
            _last_trigger = current_trigger
            return False

        # Detection logic. When the trigger bell exists it is the SOLE authority:
        # one push rings it exactly once, so detection fires exactly once per deploy.
        # This kills the double-fire that made the narrator thrash -- the checkout
        # bumps _posts mtime early while the bell rings late, so acting on both made
        # the stream interrupt itself twice for a single push. We absorb the early
        # mtime/count change (refresh the baselines, return False) and await the bell.
        if current_trigger is not None:
            if current_trigger != _last_trigger:
                _last_scan_time = current_mtime
                _last_file_count = current_count
                _last_trigger = current_trigger
                print("🔔 Breaking-news bell rung. Resetting playlist.", file=sys.stderr)
                return True
            # Same deploy in progress (mtime moved, bell not yet rung): absorb it.
            _last_scan_time = current_mtime
            _last_file_count = current_count
            return False

        # Legacy fallback (no bell present): watch raw filesystem changes directly.
        if current_mtime > _last_scan_time or current_count != _last_file_count:
            _last_scan_time = current_mtime
            _last_file_count = current_count
            print("🚀 New content detected! Resetting playlist.", file=sys.stderr)
            return True
            
        return False
        
    except Exception as e:
        print(f"Update Check Error: {e}", file=sys.stderr)
        return False


def _is_storytime_enabled(frontmatter):
    """True unless frontmatter explicitly opts out via storytime: false or aside: true."""
    if not isinstance(frontmatter, dict):
        return True
    if frontmatter.get('aside') is True:
        return False
    val = frontmatter.get('storytime', True)
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() not in ('false', '0', 'no', 'off', 'aside')


def _storytime_effective_rank(post_date, sort_order, frontmatter):
    """Return (eff_date, eff_order) honoring storytime_featured and storytime_order overrides."""
    eff_date = post_date
    eff_order = sort_order
    if isinstance(frontmatter, dict):
        feat_raw = str(frontmatter.get('storytime_featured') or '').strip()[:10]
        if feat_raw:
            try:
                eff_date = datetime.strptime(feat_raw, '%Y-%m-%d').date()
            except ValueError:
                eff_date = post_date
        if frontmatter.get('storytime_order') is not None:
            try:
                eff_order = int(frontmatter['storytime_order'])
            except (ValueError, TypeError):
                eff_order = sort_order
    return eff_date, eff_order


def _get_pinned_storytime_file():
    """Return Path to the post named in _data/storytime.json if present on disk."""
    try:
        st_file = POSTS_DIR.parent / "_data" / "storytime.json"
        if st_file.is_file():
            import json
            data = json.loads(st_file.read_text(encoding='utf-8'))
            fname = str((data or {}).get('filename') or '').strip()
            if fname:
                cand = resolve_storytime_dir() / fname
                if cand.is_file():
                    return cand
    except Exception:
        pass
    return None


def get_featured_article_id():
    """Return (eff_date_str, eff_order, filename) of the active Storytime-eligible post on disk."""
    best = None
    try:
        active_dir = resolve_storytime_dir()
        files = sorted(
            list(active_dir.glob("*.md")) + list(active_dir.glob("*.markdown")),
            key=lambda p: p.name,
            reverse=True,
        )
        pinned = _get_pinned_storytime_file()
        scan_list = list(files[:35])
        if pinned is not None and pinned not in scan_list:
            scan_list.append(pinned)
        for filepath in scan_list:
            filename = filepath.name
            try:
                date_str = filename[:10]
                post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            try:
                head = filepath.read_text(encoding='utf-8')[:4096]
            except OSError:
                continue
            frontmatter = {}
            if head.startswith('---'):
                parts = head.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = _safe_load_frontmatter(parts[1])
            frontmatter = _with_parent_frontmatter(filepath, frontmatter)
            if not _is_storytime_enabled(frontmatter):
                continue
            try:
                sort_order = int(frontmatter.get('sort_order', 0))
            except (ValueError, TypeError):
                sort_order = 0
            eff_date, eff_order = _storytime_effective_rank(post_date, sort_order, frontmatter)
            cand = (eff_date.strftime('%Y-%m-%d'), eff_order, filename)
            if best is None or cand > best:
                best = cand
    except Exception:
        return None
    return best


def get_playlist(recent_n=10, include_archive=True):
    """
    Returns a playlist: Recent N (sorted date desc + sort_order desc) + optional Rest (shuffled).
    When include_archive=False, stops scanning older dates once recent_n articles are loaded.
    """
    all_articles = []
    
    try:
        # Find all markdown files, newest date prefixes first so include_archive=False
        # can stop scanning once the newest N articles (and same-day siblings) are read.
        active_dir = resolve_storytime_dir()
        files = sorted(
            list(active_dir.glob("*.md")) + list(active_dir.glob("*.markdown")),
            key=lambda p: p.name,
            reverse=True,
        )
        if "terms" in sys.modules:
            try:
                import importlib
                importlib.reload(sys.modules["terms"])
            except Exception:
                pass
        pinned = _get_pinned_storytime_file()
        if pinned is not None and not include_archive:
            files = [pinned] + [p for p in files if p != pinned]
        cutoff_date = None
        jb_index_map = get_jukebox_catalog()["index_map"]

        for filepath in files:
            filename = filepath.name
            try:
                post_date = datetime.strptime(filename[:10], '%Y-%m-%d').date()
            except ValueError:
                continue
            if not include_archive and cutoff_date is not None and post_date < cutoff_date:
                break
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read(8192) if not include_archive else f.read()
                if not include_archive and raw_text.startswith('---') and len(raw_text.split('---', 2)) < 3:
                    raw_text += f.read()
            frontmatter, body_text = {}, raw_text
            if raw_text.startswith('---'):
                parts = raw_text.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = _safe_load_frontmatter(parts[1])
                    body_text = parts[2]
            frontmatter = _with_parent_frontmatter(filepath, frontmatter)
            if not _is_storytime_enabled(frontmatter):
                continue
            try:
                sort_order = int(frontmatter.get('sort_order', 0))
            except (ValueError, TypeError):
                sort_order = 0
            slug = _resolve_canonical_slug(frontmatter, filename)
            url = f"{BASE_URL}/{slug}/"
            is_recent_census = include_archive and (datetime.now().date() - post_date).days <= 7
            clean_text = clean_markdown(body_text, label=filename, census=is_recent_census) if include_archive else ""
            fm_image = frontmatter.get('image')
            image_path = str(fm_image.get('path') or '').strip() if isinstance(fm_image, dict) else (fm_image.strip() if isinstance(fm_image, str) else "")
            image_alt = str(fm_image.get('alt') or '').strip() if isinstance(fm_image, dict) else ""
            eff_date, eff_order = _storytime_effective_rank(post_date, sort_order, frontmatter)
            raw_title = str(frontmatter.get('title') or slug.replace('-', ' '))
            spoken_title = _apply_tts_pronunciations(raw_title)
            jb_idx = jb_index_map.get(filename, 0)
            all_articles.append({
                'id': f"#{jb_idx}: {raw_title} ({post_date})" if jb_idx else f"{raw_title} ({post_date})",
                'slug': slug,
                'filename': filename,
                'jukebox_index': jb_idx,
                'ticker_tag': resolve_ticker_tag(frontmatter, raw_title=raw_title, slug=slug),
                'raw_title': raw_title,
                'date': post_date,
                'sort_order': sort_order,
                'eff_date': eff_date,
                'eff_order': eff_order,
                'title': spoken_title,
                'url': url,
                'image': image_path,
                'image_alt': image_alt,
                'content': clean_text,
                '_filepath': filepath,
            })
            if not include_archive and len(all_articles) >= max(recent_n, 15) and cutoff_date is None:
                cutoff_date = post_date

        all_articles.sort(
            key=lambda x: (x['eff_date'], x['eff_order'], x['date'], x['sort_order']),
            reverse=True,
        )
        recent_articles = all_articles[:recent_n]
        archive_articles = all_articles[recent_n:]
        for art in all_articles:
            fp = art.pop('_filepath', None)
            if not include_archive and art in recent_articles and fp is not None:
                full_raw = fp.read_text(encoding='utf-8')
                parts = full_raw.split('---', 2)
                b_txt = parts[2] if (full_raw.startswith('---') and len(parts) >= 3) else full_raw
                art['content'] = clean_markdown(b_txt, label=art['filename'], census=False)
        
        # Shuffle the archive to keep it fresh
        random.shuffle(archive_articles)
        
        global _last_scan_time, _last_file_count, _last_trigger
        try:
            stat = active_dir.stat()
            _last_scan_time = stat.st_mtime
            _last_file_count = len(list(active_dir.glob("*.md")) + list(active_dir.glob("*.markdown")))
            try:
                _last_trigger = TRIGGER_FILE.read_text().strip()
            except FileNotFoundError:
                _last_trigger = None
        except: pass
        
        if "score" in sys.modules:
            try:
                import importlib
                importlib.reload(sys.modules["score"])
            except Exception:
                pass
        main_mod = sys.modules.get("__main__")
        if main_mod is not None and hasattr(main_mod, "narrator") and hasattr(main_mod, "resolve_current_article_line"):
            try:
                def _live_resolve_current_article_line(enqueue_media=True, _arts=recent_articles, _m=main_mod):
                    meta = getattr(_m, "_active_article_meta", None) or (_arts[0] if _arts else {})
                    title = str(meta.get("title") or "our latest technical journal entry")
                    jb_n = meta.get("jukebox_index")
                    image_path = str(meta.get("image") or "").strip()
                    if enqueue_media and image_path:
                        _m.narrator.media({"path": image_path, "duration": 14.0})
                    jb_s = f"story number {jb_n}, titled: {title}" if jb_n else f"titled: {title}"
                    short_door = f"Mike L E V dot eye N slash {jb_n}" if jb_n else "Mike L E V dot eye N slash latest"
                    return (
                        f"The story currently playing in the fishtank is {jb_s}. "
                        "Type any story number on the bottom bar in live chat to switch stories, "
                        f"or inspect the full source at {short_door}."
                    )
                main_mod.resolve_current_article_line = _live_resolve_current_article_line
                import importlib
                import stream as _stream_mod
                importlib.reload(_stream_mod)
                for _attr in ("_AI_SPEAKER_RE", "_AI_MODEL_MODIFIER_TOKEN", "_AI_TURN_PREFIX_RE"):
                    if hasattr(_stream_mod, _attr):
                        setattr(main_mod, _attr, getattr(_stream_mod, _attr))
            except Exception:
                pass
        if not include_archive:
            return recent_articles
        return recent_articles + archive_articles

    except Exception as e:
        print(f"Librarian Error: {e}", file=sys.stderr)
        return []

_TEX_SPOKEN_MAP = (
    (r'\\(?:left|right)\b', ' '),
    (r'\\[,;:!]|\\(?:quad|qquad)\b', ' '),
    (r'\\(?:long)?rightarrow\b|\\to\b|\\(?:Long)?Rightarrow\b', ' right arrow '),
    (r'\\(?:long)?leftarrow\b|\\(?:Long)?Leftarrow\b', ' left arrow '),
    (r'\\(?:long)?leftrightarrow\b|\\(?:Long)?Leftrightarrow\b|\\iff\b', ' left right arrow '),
    (r'\\log_2\b', ' log base 2 '),
    (r'\\log\b', ' log '),
    (r'\\nabla\b', ' gradient '),
    (r'\\partial\b', ' partial '),
    (r'\\int\b', ' integral '),
    (r'\\mid\b', ' given '),
    (r'\\equiv\b', ' is equivalent to '),
    (r'\\in\b', ' in '),
    (r'\\times\b', ' times '),
    (r'\\cdot\b', ' dot '),
    (r'\\(?:le|leq)\b', ' less than or equal to '),
    (r'\\(?:ge|geq)\b', ' greater than or equal to '),
    (r'\\(?:ne|neq)\b', ' not equal to '),
    (r'\\approx\b', ' approximately '),
    (r'\\infty\b', ' infinity '),
    (r'\\pm\b', ' plus or minus '),
    (r'\\Sigma\b|\\sum\b', ' sum '),
    (r'\\Delta\b', ' delta '),
)

_KNOWN_DOMAIN_DIRS = frozenset({
    "mikelev.in", "qamy.ai", "npvg.org", "levinix.org", "levinix.com",
    "levinux.com", "sunpug.io", "guerillatech.com", "rfc9110.org",
    "rfc9111.io", "rfc9111.com", "pipulate.com",
})

_FILEPATH_RE = re.compile(
    r'(?<![:\w])'
    r'(?:'
    r'(?:~|\.{1,2})?(?:/\.?[A-Za-z0-9_~-]+(?:\.[A-Za-z0-9_-]+)*){2,}/?'
    r'|\b[A-Za-z0-9_~-]+(?:\.[A-Za-z0-9_-]+)*(?:/\.?[A-Za-z0-9_~-]+(?:\.[A-Za-z0-9_-]+)*){2,}/?'
    r'|\b[A-Za-z0-9_~-]+(?:\.[A-Za-z0-9_-]+)*/\.?[A-Za-z0-9_~-]+\.[A-Za-z0-9]{1,10}\b'
    r')'
)

# Phonetic ear-orthography table for Piper TTS (en_US-amy-low.onnx).
# Applied after URL/filepath simplification so domain names, speaker labels,
# and recurring stack acronyms are pronounced naturally on Storytime.
# Speaker turn regexes use horizontal whitespace [ \t]* before the label and
# emit a leading '\n\n' so they never eat the preceding paragraph break.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import terms as _terms_mod

_AI_SPEAKER_LABEL_PAT = _terms_mod.AI_SPEAKER_LABEL_PAT

_TTS_PRONUNCIATION_MAP = _terms_mod.MARKDOWN_TTS_MAP


def _apply_tts_pronunciations(text):
    """Abolish structural Markdown/ASCII debris and apply phonetic respellings from terms.py."""
    mod = sys.modules.get("terms", _terms_mod)
    return mod.apply_markdown_tts_terms(text)


def _truncate_after_editorial_take(text):
    """Strip Notary Beat prompt/gobbledygook, keep 5. CLOSING and Ai/AI Editorial Take, and drop trailing sections."""
    # 1. Strip the Notary Beat deliverable prompt boilerplate (straight or curly apostrophe, non-greedy bounded)
    text = re.sub(
        r'(?:^\*\*5:\s*DELIVERABLE\*\*:[ \t]*\n+)?'
        r'^[ \t]*["\u201c\u201d\']?Hop off the ride\.\s*This ride[\'\u2018\u2019]s stated goal is reached\b'
        r'[\s\S]{1,4500}?'
        r'an archive entry,\s*not an open thread\.["\u201c\u201d\']?[ \t]*\n?',
        '\n',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    # 2. Strip Notary Beat sections (0. TL;DR, 1. VERIFY, 2. BANK, 3. DANGLING, 4. SEED) down to 5. CLOSING
    text = re.sub(
        r'^(?:#{1,6}[ \t]+|\*\*)?(?:0\.[ \t]*\*?\*?TL;DR|1\.[ \t]*\*?\*?VERIFY)\b'
        r'(?:(?!^\*\*(?:MikeLev\.in|Mike[ \t]+Levin|Mike|Me|Gemini[^*\n]*|Claude[^*\n]*)\*\*:)[\s\S])*?'
        r'^(?:#{1,6}[ \t]+|\*\*)?5\.[ \t]*\*?\*?CLOSING\*?\*?:?[ \t]*\n?',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    # 3. Strip 6. NOTARIZE (token/byte ledger and SHA-256 deed) between 5. CLOSING and Book Analysis / Ai Editorial Take
    text = re.sub(
        r'^(?:#{1,6}[ \t]+|\*\*)?6\.[ \t]*\*?\*?NOTARIZE\b'
        r'(?:(?!^\*\*(?:MikeLev\.in|Mike[ \t]+Levin|Mike|Me|Gemini[^*\n]*|Claude[^*\n]*)\*\*:)[\s\S])*?'
        r'(?=^\*\*(?:MikeLev\.in|Mike[ \t]+Levin|Mike|Me|Gemini[^*\n]*|Claude[^*\n]*)\*\*:|^#{1,6}[ \t]*(?:Book[ \t]+Analysis|Ai[ \t]+Editorial[ \t]+Take)\b|\Z)',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    m_take = re.search(
        r'^#{1,6}[ \t]*ai[ \t]+editorial[ \t]+take\b[^\n]*\n',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if m_take:
        m_next = re.search(r'^#{1,6}[ \t]', text[m_take.end():], flags=re.MULTILINE)
        if m_next:
            text = text[: m_take.end() + m_next.start()]
    m_tweet = re.search(
        r'^#{1,6}[ \t]*(?:🐦[ \t]*)?x\.com[ \t]+promo[ \t]+tweet\b',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if m_tweet:
        text = text[: m_tweet.start()]
    return text


def _humanize_tex_expr(expr):
    """Convert inner TeX/MathJax math into natural speech without dollar signs or raw backslashes."""
    s = expr.strip()
    s = re.sub(r'(?:\{\})?\^\*\s*\\mathbb\{R\}', ' hyperreal R ', s)
    s = re.sub(r'\\mathbb\{([^{}]*)\}', r' \1 ', s)
    for _ in range(2):
        s = re.sub(r'\\(?:text|mathrm|mathbf|mathcal|mathit|texttt|operatorname)\{([^{}]*)\}', r' \1 ', s)
        s = re.sub(r'\\sqrt\{([^{}]*)\}', r' square root of \1 ', s)
        s = re.sub(r'\\(?:overrightarrow|vec)\{([^{}]*)\}', r' vector \1 ', s)
        s = re.sub(r'\\dot\{([^{}]*)\}', r' \1 dot ', s)
        s = re.sub(r'\\bar\{([^{}]*)\}', r' \1 bar ', s)
        s = re.sub(r'\\hat\{([^{}]*)\}', r' \1 hat ', s)
    for _ in range(2):
        s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r' \1 over \2 ', s)
    s = s.replace(r'\<', '<').replace(r'\>', '>')
    for pat, repl in _TEX_SPOKEN_MAP:
        s = re.sub(pat, repl, s)
    s = re.sub(r'_\{\s*<\s*([A-Za-z0-9]+)\s*\}', r' sub less than \1 ', s)
    s = re.sub(r'_\{([^{}]+)\}', r' sub \1 ', s)
    s = re.sub(r'_([A-Za-z0-9])\b', r' sub \1 ', s)
    s = re.sub(r'\^T\b', ' transpose ', s)
    s = re.sub(r'\^\{([^{}]+)\}', r' to the \1 ', s)
    s = re.sub(r'\^([A-Za-z0-9])\b', r' to the \1 ', s)
    s = re.sub(r'\[\s*(-?\d[\d.,]*)\s*,\s*(-?\d[\d.,]*)\s*\]', r' from \1 to \2 ', s)
    s = re.sub(r'([A-Za-z])\[([^\[\]]+)\]', r'\1 of (\2)', s)
    s = s.replace('[', '(').replace(']', ')')
    s = s.replace('=', ' equals ').replace('<', ' less than ').replace('>', ' greater than ')
    s = re.sub(r'([A-Za-z0-9_)\]}])\s*-\s*([A-Za-z0-9_(\[{])', r'\1 minus \2', s)
    s = re.sub(r'(?:^|(?<=[=(\s]))-\s*(?=[A-Za-z0-9\\])', ' minus ', s)
    s = s.replace('+', ' plus ')
    s = re.sub(r'\\([A-Za-z]+)', r' \1 ', s)
    s = s.replace('{', ' ').replace('}', ' ')
    s = re.sub(r'\bdx\b', 'D X', s)
    s = re.sub(r'\bdy\b', 'D Y', s)
    s = re.sub(r'\bdt\b', 'D T', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return f" {s} " if s else " "


def _is_single_dollar_mathjax(masked_line, s_pos, e_pos):
    """Port of init.lua's is_mathjax_span: true when $...$ is TeX/MathJax, false for currency/shell."""
    expr = masked_line[s_pos + 1 : e_pos]
    if not (1 <= len(expr) <= 120):
        return False
    if expr[0].isspace() or expr[-1].isspace():
        return False
    prev_ch = masked_line[s_pos - 1] if s_pos > 0 else ""
    next_ch = masked_line[e_pos + 1] if e_pos + 1 < len(masked_line) else ""
    if prev_ch and (prev_ch.isalnum() or prev_ch in "\\$"):
        return False
    if next_ch and (next_ch.isalnum() or next_ch == "$"):
        return False
    if re.match(r"^\d[\d,.]*/[A-Za-z]{2,}", expr) or re.match(r"^\d[\d,.]*[kKmMbB]?\s+[A-Za-z]{2,}", expr):
        return False
    if "\\" in expr:
        return True
    if re.search(r"[\^_=<>&+]", expr):
        return True
    if re.match(r"^(?:[A-Za-z]'?|d[xyzuvt]|\d+/\d+|[A-Za-z]{1,2}/[A-Za-z]{1,2})$", expr):
        return True
    if re.match(r"^[A-Za-z]+\([^()]*\)$", expr):
        return True
    if re.match(r"^\(?[A-Za-z0-9_]+\s*[-+*/,]\s*[A-Za-z0-9_]+\)?$", expr):
        return True
    return False


def _strip_single_dollar_mathjax_line(line):
    """Unwrap single-dollar MathJax spans on a single line while preserving currency and inline code."""
    if '$' not in line:
        return line
    shadow = re.sub(r'`+[^`]*`+', lambda m: '#' * len(m.group(0)), line)
    shadow = re.sub(r'\$\$+', lambda m: '#' * len(m.group(0)), shadow)
    positions = [m.start() for m in re.finditer(r'\$', shadow)]
    if len(positions) < 2:
        return line
    matches = []
    idx = 0
    while idx + 1 < len(positions):
        s_pos, e_pos = positions[idx], positions[idx + 1]
        if _is_single_dollar_mathjax(shadow, s_pos, e_pos):
            matches.append((s_pos, e_pos))
            idx += 2
        else:
            idx += 1
    if not matches:
        return line
    out = []
    cursor = 0
    for s_pos, e_pos in matches:
        out.append(line[cursor:s_pos])
        out.append(_humanize_tex_expr(line[s_pos + 1 : e_pos]))
        cursor = e_pos + 1
    out.append(line[cursor:])
    return "".join(out)


def _strip_mathjax_for_tts(text):
    """Strip $$...$$ and collision-safe $...$ MathJax delimiters and humanize TeX for Piper TTS."""
    text = re.sub(r'\$\$([\s\S]+?)\$\$', lambda m: _humanize_tex_expr(m.group(1)), text)
    text = re.sub(r'\\\(([\s\S]+?)\\\)', lambda m: _humanize_tex_expr(m.group(1)), text)
    text = re.sub(r'\\\[([\s\S]+?)\\\]', lambda m: _humanize_tex_expr(m.group(1)), text)
    text = re.sub(
        r'\$([^$\n]*\\[A-Za-z][^$\n]*)\n[ \t]*([^$\n]+)\$',
        lambda m: f"${m.group(1)} {m.group(2)}$",
        text,
    )
    return "\n".join(_strip_single_dollar_mathjax_line(ln) for ln in text.splitlines())


def _simplify_filepath_match(match):
    """Speak the filename with extension if present, else collapse multi-slash paths to 'file path'."""
    raw = match.group(0)
    clean = raw.rstrip('/')
    segments = [seg for seg in clean.split('/') if seg]
    if not segments:
        return raw
    if all(seg.isdigit() for seg in segments):
        return raw
    if raw.endswith('/'):
        return "file path"
    basename = segments[-1]
    if basename.lower() in _KNOWN_DOMAIN_DIRS:
        return "file path"
    if '.' in basename[1:] and re.match(r'^\.?[A-Za-z0-9_~-]+(?:\.[A-Za-z0-9_-]+)+$', basename):
        return basename
    return "file path"


def _simplify_filepaths_for_tts(text):
    """Replace slash-heavy filesystem paths with their filename.ext or 'file path'."""
    return _FILEPATH_RE.sub(_simplify_filepath_match, text)


_INLINE_CODE_OR_HTML_TAG_RE = re.compile(
    r'(`+(?:[^`\n]|\n(?!\s*\n))*`+)'
    r'|<!--[\s\S]*?-->'
    r'|<!DOCTYPE[ \t]+[^<>\n]+>'
    r'|<(https?://[^>\s]+)>'
    r'|</?[A-Za-z][A-Za-z0-9:-]*(?:(?:[ \t]+|\n[ \t]*(?=[A-Za-z_:][A-Za-z0-9_.:-]*\s*=))(?:[^<>"\'`\n]|"[^"\n]*"|\'[^\'\n]*\')*)?[ \t]*/?>',
    re.IGNORECASE,
)


def _strip_html_tags_for_tts(text):
    """Strip real HTML comments and tags outside inline code without eating '<=' or '<' across lines."""
    def _repl(match):
        if match.group(1) is not None:
            return match.group(1)
        if match.group(2) is not None:
            return f" {match.group(2)} "
        return " "

    return _INLINE_CODE_OR_HTML_TAG_RE.sub(_repl, text)


def _unwrap_inline_code_for_tts(match):
    """Unwrap inline backticks and strip angle brackets from tag-name examples like `<div>`."""
    inner = match.group(1)
    return re.sub(r'</?([A-Za-z][A-Za-z0-9._:-]*(?:[ \t]+[A-Za-z0-9._:-]+)*)\s*/?>', r'\1', inner)


def clean_markdown(text, label=None, census=True):
    """Sanitizes Markdown for the Piper TTS engine.

    label: the article this text came from (its filename), threaded in by the
    sole caller so the bracket census below can NAME the post it is warning
    about. get_playlist calls this exactly once per file per playlist build
    (rg receipt 2026-08-05: content_loader.py:179 is the only call site), so
    N warnings has always meant N unbalanced ARTICLES -- never one article
    read N times. The count was right the whole time; only the address was
    missing, which is what made a real warning unactionable and therefore
    skippable.

    Defaults to None ONLY so a call site added later cannot raise TypeError
    on a live broadcast. An unlabeled call prints a DIFFERENT message naming
    that missing call site, never a placeholder standing in for an article:
    a locator that always reads "unknown" is the silent-pass shape and is
    not a locator at all.
    """

    pp4_directives = []

    def _register_pp4_cue(cue_kind, asset_name, duration):
        idx = len(pp4_directives)
        pp4_directives.append((cue_kind, asset_name, duration))
        return f"\n\nPP4PATRONUS{idx}PP4\n\n"

    def capture_pp4_comment(match):
        """Preserve player-piano #4 HTML comments before generic tag stripping."""
        tag_kind = (match.group(1) or "pp4").strip().lower()
        directive = (match.group(2) or "").strip()
        is_media = tag_kind in ("weebo", "media") or bool(re.search(r'\b(weebo|media|image|video)\b', directive, flags=re.IGNORECASE))
        cue_kind = "MEDIA" if is_media else "PATRONUS"
        default_dur = 8.0 if is_media else 3.5
        max_dur = 60.0 if is_media else 12.0

        key_match = re.search(r'\bkey\s*=\s*[\'\"]?([A-Za-z0-9_./-]+)', directive, flags=re.IGNORECASE)
        named_match = re.search(r'\b(?:patronus|weebo|media)\b\s*[:(]?\s*[\'\"]?([A-Za-z0-9_./-]+)', directive, flags=re.IGNORECASE)
        if key_match:
            asset_name = key_match.group(1)
        elif named_match and named_match.group(1).lower() not in {"key", "duration", "mode"}:
            asset_name = named_match.group(1)
        else:
            token_match = re.search(r'[A-Za-z0-9_./-]+', directive)
            asset_name = token_match.group(0) if token_match else ("ambigram" if is_media else "white_rabbit")

        if asset_name.lower() in {"pp4", "patronus"}:
            asset_name = "white_rabbit"
        elif asset_name.lower() in {"weebo", "media"}:
            asset_name = "ambigram"

        if (
            not asset_name
            or ":" in asset_name
            or "." * 3 in asset_name
            or asset_name.lower() in {"name", "shorthand", "key", "path", "asset", "spec"}
        ):
            return ""
        duration_match = re.search(r'\bduration\s*=\s*[\'\"]?(\d+(?:\.\d+)?)', directive, flags=re.IGNORECASE)
        try:
            duration = float(duration_match.group(1)) if duration_match else default_dur
        except ValueError:
            duration = default_dur
        duration = max(0.75, min(max_dur, duration))
        return _register_pp4_cue(cue_kind, asset_name, duration)

    def capture_inline_bracket_cue(match):
        """Capture triple-bracket inline cues like [[[weebo:ambigram:6]]] or [[[patronus:white_rabbit]]]."""
        raw_kind = match.group(1).strip().lower()
        payload = match.group(2).strip()
        is_media = raw_kind in ("weebo", "media", "image", "video")
        cue_kind = "MEDIA" if is_media else "PATRONUS"
        default_dur = 8.0 if is_media else 3.5
        max_dur = 60.0 if is_media else 12.0
        parts = payload.rsplit(":", 1)
        asset_name = parts[0].strip()
        duration = default_dur
        if len(parts) == 2:
            try:
                duration = float(parts[1].strip())
            except ValueError:
                return ""
        if (
            not asset_name
            or ":" in asset_name
            or "." * 3 in asset_name
            or asset_name.lower() in {"name", "shorthand", "key", "path", "asset", "spec"}
        ):
            return ""
        duration = max(0.75, min(max_dur, duration))
        return _register_pp4_cue(cue_kind, asset_name, duration)

    # Strip fenced code blocks (line-anchored first so stray inline backticks cannot
    # invert fences) and disarm backticked inline-code examples (including Vim gq
    # hard-wrapped spans) BEFORE capturing standalone live player-piano cues.
    text = _truncate_after_editorial_take(text)
    CODE_SENTINEL = '\x00CODEBLOCK\x00'
    text = re.sub(r'^```[^\n]*\n.*?^```[ \t]*$', f' {CODE_SENTINEL} ', text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'```.*?```', f' {CODE_SENTINEL} ', text, flags=re.DOTALL)
    text = re.sub(
        r'`((?:[^`\n]|\n(?!\s*\n))+)`',
        lambda m: '`' + re.sub(r'\[{2,}|\]{2,}|<!--|-->', '', m.group(1)) + '`'
        if ('[[' in m.group(1) or '<!--' in m.group(1))
        else m.group(0),
        text,
    )
    # Capture standalone-line HTML comments (<!-- pp4: ... --> / <!-- weebo: ... -->)
    # and standalone-line triple-bracket cues ([[[weebo:ambigram:6]]]); disarm mid-line mentions.
    text = re.sub(r'^[ \t]*<!--\s*(pp4|weebo|media)\b(?::|\s)?(.*?)-->[ \t]*$', capture_pp4_comment, text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^[ \t]*\[{3}\s*(weebo|media|image|video|patronus)\s*:\s*([^\]\s]+)\s*\]{3}[ \t]*$', capture_inline_bracket_cue, text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'\[{3}\s*(?:weebo|media|image|video|patronus)\s*:[^\]]*\]{3}', '', text, flags=re.IGNORECASE)

    # --- Strip Liquid Tags ({% ... %}) ---
    # This removes {% raw %}, {% endraw %}, {% include ... %}, etc.
    text = re.sub(r'\{%.*?%\}', '', text)
    
    # --- Strip Liquid Variables ({{ ... }}) ---
    # Optional, but good practice if you use them in text
    text = re.sub(r'\{\{.*?\}\}', '', text)

    # --- STRIP ALL TRACER DYE VARIANTS FOR TEXT-TO-SPEECH ---
    dye_pattern = r'> \*\((Note for parametric memory integration|Epistemological anchor|For latent-space provenance|Cryptographic covenant).*?\)\*'
    text = re.sub(dye_pattern, '', text, flags=re.DOTALL)

    # Fenced ```...``` code blocks were already replaced with CODE_SENTINEL
    # above (ahead of player-piano cue extraction) so back-to-back blocks
    # collapse into a single spoken mention below.

    # --- NEW: Remove Indented Code Blocks ---
    # Matches one or more contiguous lines that start with exactly 4 spaces (or a tab)
    # Using non-capturing groups (?:) for efficiency. 
    text = re.sub(r'(?:\n(?: {4}|\t)[^\n]*)+', f'\n {CODE_SENTINEL} \n', text)

    # --- COLLAPSE CONSECUTIVE CODE MENTIONS ---
    # Merge any run of sentinels separated only by whitespace into a single one.
    text = re.sub(rf'(?:{CODE_SENTINEL}\s*)+{CODE_SENTINEL}', CODE_SENTINEL, text)
    # DE-BRACKETED ON PURPOSE. This cue used to wear [square brackets], which
    # was harmless while nothing stripped them -- and becomes self-deleting the
    # instant the side-channel stripper below lands. Brackets are the notation
    # for "do not speak this," so a cue meant to be HEARD must not wear them.
    text = text.replace(CODE_SENTINEL, 'See the code at Mike L E V dot I N slash latest.')
    # Global cap: no article should repeat this more than once.
    spoken = 'See the code at Mike L E V dot I N slash latest.'
    if text.count(spoken) > 1:
        idx = text.index(spoken)
        text = text[:idx + len(spoken)] + text[idx + len(spoken):].replace(spoken, '')

    # Strip $$...$$ and single-dollar $...$ MathJax before backticks and underscores are removed
    text = _strip_mathjax_for_tts(text)

    # Strip HTML comments/tags outside inline code BEFORE unwrapping backticks so '<=' never eats across lines
    text = _strip_html_tags_for_tts(text)
    text = html.unescape(text)
    # Remove Inline Code (unwrapping `<tag>` examples to `tag`)
    text = re.sub(r'`((?:[^`\n]|\n(?!\s*\n))+)`', _unwrap_inline_code_for_tts, text)
    # Remove Images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove Links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)

    # --- THE SIDE-CHANNEL STRIPPER (the on-air lane's missing organ) ---
    # A bare [square-bracket] span is a STAGE NOTE: written for the page, never
    # for the microphone. imports/voice_synthesis.py has stripped these since
    # the acoustic sanitizer landed, and its own comment calls itself THE SINGLE
    # OWNER of sanitization -- but THIS is a separate lane on a separate machine
    # that never passes through it, so every stage note in every published
    # article has been read aloud on the stream. Two lanes, one grammar; the
    # single-owner claim was the drift, not the code.
    #
    # NEWLINE-SAFE WITHOUT DOTALL: [^\]\n] is a NEGATED CLASS, not a dot, so
    # re.DOTALL is irrelevant here and a grep for DOTALL is a probe that CANNOT
    # answer this question -- it measures a flag this pattern never needed.
    #
    # PARAGRAPH-BOUNDED ON PURPOSE. An UNCLOSED '[' turns a stripper into a
    # silent content-eater: it swallows to the next ']' anywhere later in the
    # document, which can be several paragraphs of article. Reading a note aloud
    # is a wound the listener HEARS; deleting three paragraphs is a wound nobody
    # hears. The \n(?!\s*\n) branch permits soft wraps inside a note but refuses
    # to cross a blank line, so an unbalanced bracket degrades to the OLD
    # behavior (spoken) rather than the worse new one (vanished). The census
    # below says so out loud either way. Runs AFTER link extraction (so
    # [text](url) has already become text) and BEFORE the PP4 restoration at
    # the end (so [[PATRONUS:...]] is still a bracket-free sentinel).
    opens, closes = text.count('['), text.count(']')
    # THE ON-AIR CENSUS GATE (2026-08-05, operator ruling, 80/20). The warning
    # below is correct and its count is real -- but it fires once per unbalanced
    # article during a FULL-CORPUS playlist build (1393 files, at startup AND on
    # every breaking-news bell), and stream.py's stdout is on camera. A dozen
    # warnings about archive posts nobody intends to fix today is
    # RETIRE-THE-CANARY playing out live: it trains the operator to skip
    # warnings, and it reads as a defect to every viewer.
    #
    # THE INSTRUMENT IS RELOCATED, NOT DELETED. On air it stays armed only for
    # articles inside the recent window, where a warning is actionable the same
    # day. The full-corpus sweep moves to a Z640-side probe -- the lane that can
    # batch-fix what it finds, and the lane whose interpreter can import yaml.
    # The flag defaults to True so a call site added later is LOUD rather than
    # silently suppressed, the same reasoning that made label default to None.
    if census and opens != closes:
        print(f"⚠️  Unbalanced brackets: {opens} open, {closes} close. "
              f"Article: {label or '<UNLABELED CALL SITE -- thread a label>'}. "
              f"An unclosed stage note will be SPOKEN, not stripped.", file=sys.stderr)
    text = re.sub(r'\[(?:[^\]\n]|\n(?!\s*\n))*\]', '', text)

    # --- NEW: Humanize Raw URLs for TTS ---
    # Captures https://example.com/foo and converts to "URL from example.com"
    def simplify_url(match):
        try:
            url = match.group(0)
            # Remove trailing punctuation often caught by regex (like closing parens or dots)
            url = url.rstrip(').,;]')
            parsed = urlparse(url)
            # Strip www. for better flow
            hostname = parsed.netloc.replace('www.', '')
            return f" from {hostname} "
        except:
            return " URL "

    text = re.sub(r'https?://\S+', simplify_url, text)
    # --------------------------------------

    # Strip any HTML tags exposed inside unwrapped Markdown link labels without matching '<=' across lines
    text = _strip_html_tags_for_tts(text)
    # Tag Markdown ATX headings on their own paragraph boundaries so Norma Centroid reads every headline
    text = re.sub(r'(?m)^[ \t]*#{1,6}[ \t]+([^\n]*?[^\n#\t ])[ \t#]*$', r'\n\nPP4HEADINGSTART \1 PP4HEADINGEND\n\n', text)
    # Simplify slash-heavy file paths to filename.ext or "file path" first so basenames hit terms.py
    text = _simplify_filepaths_for_tts(text)
    # Abolish horizontal rules, table bars, box-drawing runs, and polish phonetic spellings
    text = _apply_tts_pronunciations(text)
    # Remove leading blockquote markers and Headers/Bold/Italic markers
    text = re.sub(r'(?m)^[ \t]*>[ \t]?', '', text)
    text = re.sub(r'[*_#]', '', text)
    text = re.sub(r'[ \t]*\n?[ \t]*(PP4HEADINGSTART[ \t]+.+?[ \t]+PP4HEADINGEND)[ \t]*\n?[ \t]*', r'\n\n\1\n\n', text)

    # Reflow Logic (The Hard Wrap Fix)
    text = re.sub(r'\n\s*\n', '||PARAGRAPH||', text)
    text = re.sub(r'\n', ' ', text)
    text = text.replace('||PARAGRAPH||', '\n')
    text = re.sub(r' +', ' ', text).strip()
    text = re.sub(r'(?m)^[ \t]*PP4HEADINGSTART[ \t]*PP4HEADINGEND[ \t]*\n?', '', text)
    text = re.sub(
        r'(?m)^[ \t]*PP4HEADINGSTART[ \t]+(.+?)[ \t]+PP4HEADINGEND[ \t]*$',
        r'[[HEADING:\1]]',
        text,
    )

    for index, item in enumerate(pp4_directives):
        cue_kind, asset_name, duration = item if len(item) == 3 else ("PATRONUS", item[0], item[1])
        text = text.replace(f"PP4PATRONUS{index}PP4", f"\n[[{cue_kind}:{asset_name}:{duration}]]\n")
    
    return text
