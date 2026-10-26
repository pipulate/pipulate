import json
import os
import re
import argparse
import getpass
from datetime import datetime
from pathlib import Path
import sys

# Standard Config Location
CONFIG_DIR = Path.home() / ".config" / "pipulate"
TARGETS_FILE = Path(os.environ.get("PIPULATE_BLOGS_CONFIG", CONFIG_DIR / "blogs.json")).expanduser()
KEYS_FILE = CONFIG_DIR / "keys.json"
LAST_PUBLISHED_FILE = CONFIG_DIR / "last_published.json"

# YouTube Live Summon Thresholds (ytwatch)
# Minimum simultaneous viewers required to ring the bell + send an ntfy push
# (2 = viewer + their trusted advisor; lone 1-viewer drive-bys stay silent unless they comment)
YT_VIEWER_ALERT_MIN = int(os.environ.get("PIPULATE_YT_VIEWER_MIN", "3"))
YT_VIEWER_ALERT_DWELL = int(os.environ.get("PIPULATE_YT_VIEWER_DWELL", "60"))  # Seconds viewers must stay >= min before alerting
YT_VIEWER_ALERT_COOLDOWN = int(os.environ.get("PIPULATE_YT_VIEWER_COOLDOWN", "300"))  # Seconds between any two viewer alerts

DEFAULT_POSTS_DIR = Path(
    os.environ.get("PIPULATE_DEFAULT_POSTS_DIR", Path.home() / "repos" / "trimnoir" / "_posts")
).expanduser()
BRAIN_POSTS_DIR = Path(
    os.environ.get("PIPULATE_BRAIN_DIR", Path.home() / ".local" / "share" / "pipulate" / "brain" / "_posts")
).expanduser()


def resolve_default_posts_dir() -> str:
    """Return primary _posts checkout if present, else hydrated 2nd Brain _posts."""
    if DEFAULT_POSTS_DIR.is_dir():
        return str(DEFAULT_POSTS_DIR)
    if BRAIN_POSTS_DIR.is_dir():
        return str(BRAIN_POSTS_DIR)
    return str(DEFAULT_POSTS_DIR)


DEFAULT_TARGETS = {
    "1": {
        "name": "MikeLev.in (2nd Brain)",
        "path": resolve_default_posts_dir(),
        "base_url": "https://mikelev.in",
        "permalink_prefix": "futureproof"
    }
}

def load_targets():
    """Loads targets from JSON or returns defaults."""
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                targets = json.load(f)
            t1 = targets.get("1")
            if isinstance(t1, dict):
                p1 = Path(t1.get("path", "")).expanduser()
                if not p1.is_dir() and BRAIN_POSTS_DIR.is_dir() and "shadow-publishing" not in str(p1):
                    t1["path"] = str(BRAIN_POSTS_DIR)
            return targets
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.")
    return {
        "1": {
            "name": "MikeLev.in (2nd Brain)",
            "path": resolve_default_posts_dir(),
            "base_url": "https://mikelev.in",
            "permalink_prefix": "futureproof",
        }
    }


def canonical_target(spec):
    """argparse `type=` for -t: one key or alias in, the canonical key out.

    THE NAME IS THE KEY (2026-09-27). Every publishing script reads -t
    through add_standard_arguments below, so this one callable is where
    `-t grim` becomes `-t 2` for all of them at once, before any script
    looks a target up, records a marker under it, or hands it to the next
    script in a pipeline. The resolver is lsa.parse_target_spec, the same
    one `posts` and `rgx` read, so a name means the same thing in every
    lane; a spec naming several blogs is refused here, because a publish
    is one blog at a time and the many-blog spelling belongs to the
    readers. argparse applies a type to a string default too, so the
    default "1" passes through this as well. Raises ArgumentTypeError so
    argparse prints the roster the resolver already spells (2=grim ...).
    """
    import lsa
    targets = load_targets()
    try:
        keys = lsa.parse_target_spec(str(spec), targets)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))
    if len(keys) != 1:
        raise argparse.ArgumentTypeError(
            f"-t names one blog here (got {spec!r} -> {', '.join(keys)}); "
            "posts and rgx take the many-blog spelling")
    return keys[0]


def record_last_published(target_key, file_path, target_name=None):
    """Record the article articleizer.py just wrote, keyed by target.

    confluenceizer.py --latest reads this to sync ONLY the freshly published
    file instead of sweeping the whole directory. Keying by target means a
    public-side publish (target 1) never shadows a private-side one (target 4).
    """
    target_key = str(target_key)
    data = {}
    if LAST_PUBLISHED_FILE.exists():
        try:
            with open(LAST_PUBLISHED_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data[target_key] = {
        "path": str(Path(file_path).resolve()),
        "name": target_name,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LAST_PUBLISHED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_last_published(target_key):
    """Return the recorded path for a target, or None if absent/stale/invalid."""
    target_key = str(target_key)
    if not LAST_PUBLISHED_FILE.exists():
        return None
    try:
        with open(LAST_PUBLISHED_FILE, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    entry = data.get(target_key) if isinstance(data, dict) else None
    if not entry:
        return None
    path = entry.get("path") if isinstance(entry, dict) else entry
    if path and Path(path).is_file():
        return path
    return None


def load_keys_dict():
    """Loads the entire keys dictionary from keys.json."""
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Error: {KEYS_FILE} is corrupt.")
            sys.exit(1)
    return {}

def get_api_key(key_name=None):
    """Gets a specific named API key, falling back to 'default' or prompt."""
    key_name = key_name or "default"
    keys_dict = load_keys_dict()

    if key_name in keys_dict:
        return keys_dict[key_name]

    # Interactive fallback
    print(f"⚠️ API Key '{key_name}' not found in {KEYS_FILE}.")
    new_key = getpass.getpass(f"Enter the API key for '{key_name}' (any provider; --model names which): ").strip()

    if new_key:
        save = input(f"Save key '{key_name}' to config? (y/n): ").lower()
        if save == 'y':
            keys_dict[key_name] = new_key
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(KEYS_FILE, 'w') as f:
                json.dump(keys_dict, f, indent=2)
            KEYS_FILE.chmod(0o600)
            print(f"✅ Key '{key_name}' saved.")
        return new_key
    else:
        print("❌ No key provided. Exiting.")
        sys.exit(1)

def add_target_argument(parser):
    """Legacy helper - redirects to add_standard_arguments for backwards compatibility."""
    add_standard_arguments(parser)


def get_target_path(cli_args=None):
    """
    Determines the active project path.
    Priority:
    1. CLI Argument (--target)
    2. Default (Target "1")
    3. Interactive Selection (Fallback)
    """
    targets = load_targets()
    
    # If args provided and key exists, use it
    if cli_args and getattr(cli_args, 'target', None):
        key = str(cli_args.target)
        if key in targets:
            # Polish: Tell the user if it was explicit or defaulted
            if '-t' in sys.argv or '--target' in sys.argv:
                print(f"🎯 Target set via CLI: {targets[key]['name']}")
            else:
                print(f"🎯 Default target auto-selected: {targets[key]['name']}")
            return Path(targets[key]['path']).expanduser()
        else:
            print(f"❌ Invalid target key: {key}")
            sys.exit(1)

    # Interactive Mode (Fallback if cli_args is completely missing)
    print("\nSelect Target Repo:")
    for k, v in targets.items():
        print(f"  [{k}] {v['name']} ({v['path']})")
    
    choice = input("Enter choice (default 1): ").strip() or "1"
    
    if choice in targets:
        path = Path(targets[choice]['path']).expanduser()
        print(f"✅ Active Target: {targets[choice]['name']}")
        return path
    else:
        print("❌ Invalid selection.")
        sys.exit(1)

def add_standard_arguments(parser):
    """Unified API for all scripts."""
    # CRITICAL FIX: Inject default="1" here
    parser.add_argument('-t', '--target', type=canonical_target, default="1",
                        help="Target key or alias from blogs.json: 1 or article, 2 or grim (default: '1')")
    parser.add_argument('-k', '--key', type=str, help="API key alias from keys.json (e.g., 'pipulate')")


# ----------------------------------------------------------------------------
# Frontmatter stamping -- the 1-to-1 ledger (Jekyll post <-> Google Doc)
# ----------------------------------------------------------------------------
GDOC_URL_KEY = "gdoc_url"


def gdoc_share_url(file_id):
    """Canonical anyone-with-link share URL for a Google Doc file id."""
    return f"https://docs.google.com/document/d/{file_id}/edit?usp=sharing"


def gdoc_id_from_frontmatter(metadata):
    """Extract the Doc file id from a post's gdoc_url, or None if unstamped."""
    url = str((metadata or {}).get(GDOC_URL_KEY) or "").strip()
    match = re.search(r"/document/d/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


def stamp_frontmatter_value(md_path, key, value, preserve_mtime=True):
    """Surgically upsert one single-line `key: value` in a post's YAML block.

    Deliberately NOT a parse->mutate->dump round-trip: pushing 1,200+ posts
    through a YAML dumper would churn quoting, folding, and key order across
    the whole corpus. This touches exactly one line inside the leading
    `--- ... ---` block, leaves every other byte alone, and (by default)
    restores the file's mtime so a bookkeeping stamp never masquerades as a
    content edit to mtime-based freshness logic.

    Returns one of: "ADDED", "UPDATED", "UNCHANGED", "NO_FRONTMATTER".
    """
    path = Path(md_path)
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    if not lines or lines[0].strip() != "---":
        return "NO_FRONTMATTER"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return "NO_FRONTMATTER"

    new_line = f"{key}: {value}"
    key_re = re.compile(rf"^{re.escape(key)}\s*:")
    for i in range(1, end):
        if key_re.match(lines[i]):
            if lines[i] == new_line:
                return "UNCHANGED"
            lines[i] = new_line
            _write_text_preserving_mtime(path, "\n".join(lines), preserve_mtime)
            return "UPDATED"

    lines.insert(end, new_line)
    _write_text_preserving_mtime(path, "\n".join(lines), preserve_mtime)
    return "ADDED"


def _write_text_preserving_mtime(path, text, preserve_mtime):
    st = path.stat() if preserve_mtime else None
    path.write_text(text, encoding="utf-8")
    if st is not None:
        os.utime(path, (st.st_atime, st.st_mtime))


# ----------------------------------------------------------------------------
# Go-Go-Gadget Broadcast Kit (X.com Promo Tweet + YouTube Live Cut-and-Roll)
# ----------------------------------------------------------------------------
YT_TITLE_LIMIT = 100
CONTACT_EMAIL = "miklevin@gmail.com"


def _yt_sanitize(text):
    """YouTube rejects '<' and '>' in both titles and descriptions."""
    return (text or "").replace("<", "[").replace(">", "]")


def format_youtube_title(title):
    """Build a <=100-char YouTube Live title from the article title."""
    clean = " ".join(_yt_sanitize(title).split())
    if not clean:
        return "LIVE: Honeybot AI Observatory"
    prefixed = f"LIVE: {clean}"
    if len(prefixed) <= YT_TITLE_LIMIT:
        return prefixed
    if len(clean) <= YT_TITLE_LIMIT:
        return clean
    cut = clean[: YT_TITLE_LIMIT - 3]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


_DATED_POST_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")


def _post_sort_key(md_path):
    """Sort dated posts by (YYYY-MM-DD, frontmatter sort_order, mtime)."""
    date_part = md_path.name[:10]
    sort_order = 0
    try:
        head = md_path.read_text(encoding="utf-8")[:2048]
        if head.startswith("---"):
            m = re.search(r"^sort_order:\s*(\d+)", head, re.MULTILINE)
            if m:
                sort_order = int(m.group(1))
    except Exception:
        pass
    try:
        mtime = md_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (date_part, sort_order, mtime, md_path.name)


def _latest_post_for_target(target_key="1", slug_match=None):
    """Resolve the newest dated markdown post for target_key (or matching slug_match)."""
    targets = load_targets()
    tcfg = targets.get(str(target_key), targets.get("1", DEFAULT_TARGETS["1"]))
    posts_dir = Path(tcfg["path"]).expanduser()
    dated = [
        p for p in (posts_dir.glob("*.md") if posts_dir.is_dir() else [])
        if _DATED_POST_RE.match(p.name)
    ]
    if slug_match:
        needle = slug_match.lower().strip()
        dated = [p for p in dated if needle in p.name.lower()]
        if not dated:
            return None, tcfg
        dated.sort(key=_post_sort_key)
        return dated[-1], tcfg
    if not dated:
        return None, tcfg
    max_date = max(p.name[:10] for p in dated)
    recorded = get_last_published(target_key)
    if recorded and Path(recorded).is_file():
        rec_path = Path(recorded)
        if _DATED_POST_RE.match(rec_path.name) and rec_path.name[:10] >= max_date:
            return rec_path, tcfg
    same_day = [p for p in dated if p.name[:10] == max_date]
    same_day.sort(key=_post_sort_key)
    return same_day[-1], tcfg


def get_broadcast_kit(target_key="1", slug_match=None):
    """Extract {path, title, canonical_url, tweet, yt_title, yt_description} from the latest post."""
    import yaml
    post_path, tcfg = _latest_post_for_target(target_key, slug_match=slug_match)
    if not post_path or not post_path.is_file():
        return None
    raw = post_path.read_text(encoding="utf-8")
    fm = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except Exception:
                fm = {}
            body = parts[2]
    title = str(fm.get("title") or post_path.stem)
    base_url = (tcfg.get("base_url") or "https://mikelev.in").rstrip("/")
    permalink = str(fm.get("permalink") or "")
    canonical_url = str(fm.get("canonical_url") or (f"{base_url}{permalink}" if permalink else base_url))
    meta_desc = str(fm.get("meta_description") or fm.get("excerpt") or "").strip()
    imprint = str(fm.get("description") or "").strip()
    editorial_match = re.search(
        r"###\s*Ai Editorial Take\s*\n(.*?)(?=\n#{2,3}\s|\Z)",
        body,
        re.DOTALL | re.IGNORECASE,
    )
    ai_take = editorial_match.group(1).strip() if editorial_match else ""
    tweet_match = re.search(
        r"###\s*🐦\s*X\.com Promo Tweet\s*\n```[a-zA-Z0-9]*\n(.*?)\n```",
        body,
        re.DOTALL,
    )
    def _defang_prose_domains(text):
        cleaned = re.sub(r"\b[Xx]\.com\b", "X (Twitter)", text or "")
        return re.sub(
            r"(?<!/)\b([A-Za-z0-9_-]+)\.(com|org|net|io|ai|eu|dev|sh|py|md|nix)\b",
            "\\1.\u2060\\2",
            cleaned,
        )
    if tweet_match:
        raw_tweet = tweet_match.group(1).strip()
    else:
        raw_tweet = f"{title}\n\n{canonical_url}"
    url_token = "__CANONICAL_ARTICLE_URL__"
    tweet_masked = raw_tweet.replace(canonical_url, url_token) if canonical_url else raw_tweet
    tweet = _defang_prose_domains(tweet_masked).replace(url_token, canonical_url)
    if canonical_url in tweet and f"{canonical_url}?" not in tweet:
        tweet = tweet.replace(canonical_url, f"{canonical_url}?src=x")
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", post_path.stem)
    hero_match = re.search(
        r"###\s*🎨\s*Hero Banner Image Prompt\s*\n```[a-zA-Z0-9]*\n(.*?)\n```",
        body,
        re.DOTALL,
    )
    if hero_match:
        hero_prompt = hero_match.group(1).strip()
    else:
        hero_prompt = (
            f"Wide 16:9 full-bleed widescreen cinematic illustration for '{title}', "
            "vertically centered focal metaphor, dark obsidian-slate (#111111) environment "
            "extending continuously to all four edges, high-contrast cyan and warm brass lighting, "
            "graphic-novel ink-and-wash precision. Full-bleed edge-to-edge composition filling "
            "100% of the canvas with no borders, no frames, no matting, no margins, and no text overlays."
        )
    yaml_match = re.search(
        r"###\s*🖼️\s*YAML Frontmatter Image Override\s*\n```[a-zA-Z0-9]*\n(.*?)\n```",
        body,
        re.DOTALL,
    )
    if yaml_match:
        hero_yaml = yaml_match.group(1).strip()
    else:
        safe_alt = title.replace('"', '\\"')
        hero_yaml = f'image:\n  path: /assets/images/{slug}.jpeg\n  alt: "{safe_alt}"'
    repo_root = post_path.parent.parent
    fm_img = fm.get("image")
    fm_img_rel = ""
    if isinstance(fm_img, dict):
        fm_img_rel = str(fm_img.get("path") or "").strip()
    elif isinstance(fm_img, str):
        fm_img_rel = fm_img.strip()
    if fm_img_rel:
        hero_img_dest = str(repo_root / fm_img_rel.lstrip("/"))
    else:
        hero_img_dest = str(repo_root / "assets" / "images" / f"{slug}.jpeg")
    tags = " ".join(re.findall(r"#[A-Za-z0-9_]+", tweet))
    yt_title = format_youtube_title(title)
    desc_parts = [
        f"📖 Read the full article: {canonical_url}?src=youtube",
        f"💸 Spending $10,000/mo+ on HTML pre-render? RFC 9110/9111/9421 Consulting: {base_url}/?src=youtube#consulting (Email: {CONTACT_EMAIL} with [RFC9111] in subject)",
        f"🧪 Test RFC 9110 in your terminal: curl -sI -H \"Accept: text/markdown\" {canonical_url}?src=rfc9110",
        "",
        f"🎙️ Now reading live on the Web Bot AI Observatory: \"{title}\"",
    ]
    if meta_desc:
        desc_parts.extend(["", meta_desc])
    if ai_take:
        desc_parts.extend(["", "🤖 AI Editorial Take:", ai_take])
    elif imprint and imprint != meta_desc:
        desc_parts.extend(["", imprint])
    desc_parts.extend([
        "",
        "---",
        "🔭 About this 24/7 Home-Hosted NixOS Broadcast:",
        "You are watching real-time Nginx access logs and AI crawler telemetry from mikelev.in.",
        "• Agents sending 'Accept: text/markdown' (RFC 9110) receive clean raw Markdown.",
        "• Agents executing JavaScript trigger the DOM trapdoor sensor.",
        "• Zero-Agent Airlock: Deterministic NixOS + Piper TTS player piano (chat reaches a human, never an LLM shell).",
        f"• Ephemeral Broadcast: Continuous streams over 12h are not archived by YouTube. Permanent text & code: {base_url}/latest",
        f"• AI Context Manifest: {base_url}/llms.txt",
        "• Doors: https://sunpug.io | https://qamy.ai | https://npvg.org | https://levinix.org | https://guerillatech.com | https://rfc9110.org | https://rfc9111.io | https://pipulate.com",
    ])
    if tags:
        desc_parts.extend(["", tags])
    yt_description = _yt_sanitize("\n".join(desc_parts).strip())
    li_imprint = _defang_prose_domains(imprint)
    li_meta = _defang_prose_domains(meta_desc)
    li_parts = [
        f"🚀 {title}",
        "",
        f"📖 Full article & code receipts: {canonical_url}?src=linkedin",
    ]
    if li_imprint:
        li_parts.extend(["", li_imprint])
    elif li_meta:
        li_parts.extend(["", li_meta])
    if li_meta and li_imprint and li_meta != li_imprint:
        li_parts.extend(["", f"TL;DR: {li_meta}"])
    li_parts.extend([
        "",
        f"🧪 Test RFC 9110 in your terminal: curl -sI -H \"Accept: text/markdown\" {canonical_url}?src=rfc9110",
        f"💸 Spending \x2410,000/mo+ on HTML pre-render? {base_url}/?src=linkedin#consulting",
    ])
    if tags:
        li_parts.extend(["", tags])
    linkedin_post = "\n".join(li_parts).strip()
    preview_port = tcfg.get("preview_port", 4001)
    preview_url = f"http://localhost:{preview_port}{permalink}"
    return {
        "path": str(post_path),
        "slug": slug,
        "title": title,
        "base_url": base_url,
        "canonical_url": canonical_url,
        "preview_url": preview_url,
        "tweet": tweet,
        "linkedin": linkedin_post,
        "hero_prompt": hero_prompt,
        "hero_yaml": hero_yaml,
        "hero_img_dest": hero_img_dest,
        "yt_title": yt_title,
        "yt_description": yt_description,
    }


def _copy_to_clipboard(text):
    """Copy text to OS clipboard when interactive; detach xclip so pipes never hang."""
    if not sys.stdout.isatty():
        return False
    import subprocess
    cmd = ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"]
    try:
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


def ensure_indexnow_key_file(target_key="1"):
    """Ensure a 32-hex IndexNow key is in ~/.config/pipulate/.env and materialized in the target site root."""
    import secrets
    targets = load_targets()
    tcfg = targets.get(str(target_key), targets.get("1", DEFAULT_TARGETS["1"]))
    base_url = str(tcfg.get("base_url") or "").strip().rstrip("/")
    if not base_url.startswith("https://"):
        return "", None
    key = _get_vault_var("PIPULATE_INDEXNOW_KEY").strip()
    if not re.match(r"^[a-fA-F0-9]{16,64}$", key):
        key = secrets.token_hex(16)
        _save_vault_var("PIPULATE_INDEXNOW_KEY", key)
    posts_dir = Path(tcfg["path"]).expanduser()
    repo_root = posts_dir.parent
    key_file = repo_root / f"{key}.txt"
    if repo_root.is_dir():
        existing = key_file.read_text(encoding="utf-8").strip() if key_file.is_file() else ""
        if existing != key:
            key_file.write_text(key + "\n", encoding="utf-8")
            print(f"🔑 Materialized IndexNow verification file: {repo_root}/{key[:8]}....txt")
        if (repo_root / ".git").exists():
            import subprocess
            subprocess.run(
                ["git", "-C", str(repo_root), "add", "--", key_file.name],
                capture_output=True,
                text=True,
                check=False,
            )
    return key, key_file


def drop_pebble_pings(target_key="1", slug_match=None, dry_run=False):
    """Fire non-blocking Wayback Machine + IndexNow pebble-drop pings for the latest post."""
    import threading
    import urllib.error
    import urllib.parse
    import urllib.request
    kit = get_broadcast_kit(target_key, slug_match=slug_match)
    if not kit:
        print("⚠️ No published post found for pebble-drop pings.")
        return 1
    canonical_url = kit["canonical_url"]
    base_url = kit.get("base_url") or "https://mikelev.in"
    parsed_host = urllib.parse.urlparse(canonical_url).netloc or "mikelev.in"
    key, key_file = ensure_indexnow_key_file(target_key)
    key_loc = f"{base_url}/{key}.txt" if key else ""
    url_list = [
        canonical_url,
        f"{canonical_url.rstrip('/')}/index.md",
        f"{base_url}/llms.txt",
        f"{base_url}/sitemap.xml",
    ]
    wb_save_url = f"https://web.archive.org/save/{canonical_url}"
    feed_url = f"{base_url}/feed.xml"
    websub_hub = "https://pubsubhubbub.appspot.com/"
    if dry_run:
        masked_key = f"{key[:8]}..." if key else "NONE"
        masked_file = f"{key_file.parent}/{key[:8]}....txt" if key_file and key else str(key_file)
        print(f"🪨 [DRY RUN] Pebble-Drop Wire Pings ({Path(kit['path']).name}):")
        print(f"   • Wayback Save : GET {wb_save_url}")
        print(f"   • IndexNow POST: https://api.indexnow.org/indexnow (host={parsed_host}, key={masked_key}, urls={len(url_list)})")
        print(f"   • WebSub Hub   : POST {websub_hub} (hub.mode=publish, hub.url={feed_url})")
        print(f"   • Key File     : {masked_file} (exists={bool(key_file and key_file.is_file())})")
        return 0
    results = {}

    def _ping_wayback():
        req = urllib.request.Request(
            wb_save_url,
            headers={"User-Agent": f"pipulate-pebble/1.0 (+{base_url})"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                status = getattr(resp, "status", 200)
                results["wayback"] = f"✅ HTTP {status} (snapshot recorded -> https://web.archive.org/web/*/{canonical_url})"
        except urllib.error.HTTPError as exc:
            if exc.code in (200, 201, 202, 301, 302):
                results["wayback"] = f"✅ HTTP {exc.code} (snapshot recorded -> https://web.archive.org/web/*/{canonical_url})"
            else:
                results["wayback"] = f"ℹ️  HTTP {exc.code} ({exc.reason})"
        except Exception:
            results["wayback"] = f"⏳ Dispatched (archiving in background -> https://web.archive.org/web/*/{canonical_url})"

    def _ping_indexnow():
        if not key:
            results["indexnow"] = "⏭️  Skipped (non-HTTPS target)"
            return
        payload = {
            "host": parsed_host,
            "key": key,
            "keyLocation": key_loc,
            "urlList": url_list,
        }
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": f"pipulate-pebble/1.0 (+{base_url})",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                status = getattr(resp, "status", 200)
                results["indexnow"] = f"✅ HTTP {status} ({len(url_list)} URLs -> Bing / IndexNow)"
        except urllib.error.HTTPError as exc:
            if exc.code in (200, 202):
                results["indexnow"] = f"✅ HTTP {exc.code} ({len(url_list)} URLs -> Bing / IndexNow)"
            else:
                results["indexnow"] = f"ℹ️  HTTP {exc.code} ({exc.reason})"
        except Exception as exc:
            results["indexnow"] = f"⚠️ {exc}"

    def _ping_websub():
        if not base_url.startswith("https://"):
            results["websub"] = "⏭️  Skipped (non-HTTPS target)"
            return
        form_body = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": feed_url,
        }).encode("utf-8")
        req = urllib.request.Request(
            websub_hub,
            data=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": f"pipulate-pebble/1.0 (+{base_url})",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                status = getattr(resp, "status", 204)
                results["websub"] = f"✅ HTTP {status} (published {feed_url} -> WebSub / PubSubHubbub)"
        except urllib.error.HTTPError as exc:
            if exc.code in (200, 202, 204):
                results["websub"] = f"✅ HTTP {exc.code} (published {feed_url} -> WebSub / PubSubHubbub)"
            else:
                results["websub"] = f"ℹ️  HTTP {exc.code} ({exc.reason})"
        except Exception as exc:
            results["websub"] = f"⚠️ {exc}"

    t_wb = threading.Thread(target=_ping_wayback, daemon=True)
    t_in = threading.Thread(target=_ping_indexnow, daemon=True)
    t_ws = threading.Thread(target=_ping_websub, daemon=True)
    t_wb.start()
    t_in.start()
    t_ws.start()
    t_in.join(timeout=6.5)
    t_ws.join(timeout=6.5)
    t_wb.join(timeout=6.5)
    print(f"🪨 Pebble-Drop Wire Pings ({canonical_url}):")
    print(f"   • IndexNow (Bing/Yandex/Yep): {results.get('indexnow', '⏳ Dispatched')}")
    print(f"   • WebSub (PubSubHubbub Hub) : {results.get('websub', '⏳ Dispatched')}")
    print(f"   • Wayback Machine (Archive) : {results.get('wayback', f'⏳ Dispatched -> https://web.archive.org/web/*/{canonical_url}')}")
    print(f"   • GSC URL Inspection        : https://search.google.com/search-console/inspect?resource_id=sc-domain:{parsed_host}")
    print("   • Verify Reciprocal Receipts: ytpebble verify")
    return 0


def verify_pebble_receipts(target_key="1", slug_match=None):
    """Verify reciprocal wire receipts on Honeybot and Archive.org for the latest post."""
    import subprocess
    import urllib.parse
    import urllib.request
    kit = get_broadcast_kit(target_key, slug_match=slug_match)
    if not kit:
        print("⚠️ No published post found to verify.")
        return 1
    canonical_url = kit["canonical_url"]
    base_url = kit.get("base_url") or "https://mikelev.in"
    slug = kit["slug"]
    key, key_file = ensure_indexnow_key_file(target_key)
    print(f"🔎 Verifying Reciprocal Pebble-Drop Receipts for: {canonical_url}")

    # 1. Verify IndexNow Key File on Live Origin
    if key:
        key_url = f"{base_url}/{key}.txt"
        masked_url = f"{base_url}/{key[:8]}....txt"
        try:
            req = urllib.request.Request(key_url, headers={"User-Agent": "pipulate-verify/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                if resp.status == 200 and body == key:
                    print(f"   1. IndexNow Key File : ✅ LIVE on origin ({masked_url} -> HTTP 200, key match)")
                else:
                    print(f"   1. IndexNow Key File : ⚠️ HTTP {resp.status} at {masked_url} (body match={body == key})")
        except Exception as exc:
            print(f"   1. IndexNow Key File : ⚠️ Not yet reachable at {masked_url} ({exc}) — run `publish` to deploy")
    else:
        print("   1. IndexNow Key File : ⏭️  No key configured")

    # 2. Verify Wayback Machine Snapshot via CDX API (avoids /save/ 429 rate limits)
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx?"
        + urllib.parse.urlencode({"url": canonical_url, "output": "json", "limit": "5"})
    )
    try:
        req = urllib.request.Request(cdx_url, headers={"User-Agent": f"pipulate-verify/1.0 (+{base_url})"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(rows, list) and len(rows) > 1:
            last = rows[-1]
            ts = str(last[1]) if len(last) > 1 else ""
            status = str(last[4]) if len(last) > 4 else "200"
            snap_url = f"https://web.archive.org/web/{ts}/{canonical_url}"
            print(f"   2. Wayback CDX Ledger: ✅ ARCHIVED ({len(rows) - 1} snapshot(s), newest={ts}, status={status})")
            print(f"      ↳ Snapshot URL    : {snap_url}")
        else:
            print(f"   2. Wayback CDX Ledger: ⏳ Pending indexing (queue active -> https://web.archive.org/web/*/{canonical_url})")
    except Exception as exc:
        print(f"   2. Wayback CDX Ledger: ℹ️  CDX query deferred ({exc})")

    # 3. Verify Reciprocal Wire Hits in Honeybot /var/log/nginx/access.log
    remote_py = f"""
import re, pathlib
slug = {slug!r}
key_prefix = {(key[:16] if key else '')!r}
log_p = pathlib.Path("/var/log/nginx/access.log")
total = 0
md_served = 0
dyes = {{"a+href": 0, "link+rel": 0, "llms.txt": 0, "youtube": 0, "linkedin": 0, "x": 0, "rfc9110": 0}}
bots = set()
key_hits = 0
feed_hits = 0
yt_refs = 0
if log_p.is_file():
    sz = log_p.stat().st_size
    with open(log_p, "r", encoding="utf-8", errors="replace") as f:
        if sz > 25_000_000:
            f.seek(sz - 25_000_000)
            f.readline()
        for line in f:
            if key_prefix and key_prefix in line:
                key_hits += 1
            if "/feed.xml" in line:
                feed_hits += 1
                if "feedfetcher-google" in line.lower():
                    bots.add("FeedFetcher-Google")
            if slug not in line:
                continue
            total += 1
            if "MarkdownServed:1" in line:
                md_served += 1
            for d in dyes:
                if f"src={{d}}" in line:
                    dyes[d] += 1
            if "youtube.com" in line:
                yt_refs += 1
            for tok in ("Applebot", "bingbot", "IndexNow", "archive.org", "wayback", "CorpusBot", "AHC", "OAI-SearchBot", "GPTBot", "Claude", "ExaSearchBot", "ExaUser", "DuckAssistBot", "Googlebot", "FeedFetcher-Google"):
                if tok.lower() in line.lower():
                    bots.add(tok)
print(f"TOTAL={{total}}|MD={{md_served}}|KEY_HITS={{key_hits}}|FEED_HITS={{feed_hits}}|YT_REFS={{yt_refs}}|A_HREF={{dyes['a+href']}}|LINK_REL={{dyes['link+rel']}}|LLMS={{dyes['llms.txt']}}|S_YT={{dyes['youtube']}}|S_LI={{dyes['linkedin']}}|S_X={{dyes['x']}}|S_RFC={{dyes['rfc9110']}}|BOTS={{','.join(sorted(bots)) or 'none'}}")
"""
    try:
        res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", HONEYBOT_SSH_HOST, "python3", "-"],
            input=remote_py,
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (res.stdout or "").strip()
        if res.returncode == 0 and "TOTAL=" in out:
            kv = dict(item.split("=", 1) for item in out.split("|") if "=" in item)
            print(
                f"   3. Honeybot Wire Log : ✅ {kv.get('TOTAL', 0)} total hits on slug | "
                f"RFC 9110 MarkdownServed={kv.get('MD', 0)} | YouTube referrals={kv.get('YT_REFS', 0)} | "
                f"IndexNow key fetches={kv.get('KEY_HITS', 0)} | WebSub /feed.xml fetches={kv.get('FEED_HITS', 0)}"
            )
            print(
                f"      ↳ Tracer-Dye Doors: ?src=a+href ({kv.get('A_HREF', 0)}) · "
                f"?src=link+rel ({kv.get('LINK_REL', 0)}) · ?src=llms.txt ({kv.get('LLMS', 0)})"
            )
            print(
                f"      ↳ Social & Canary : ?src=youtube ({kv.get('S_YT', 0)}) · "
                f"?src=linkedin ({kv.get('S_LI', 0)}) · ?src=x ({kv.get('S_X', 0)}) · "
                f"?src=rfc9110 ({kv.get('S_RFC', 0)})"
            )
            print(f"      ↳ Crawlers Seen   : {kv.get('BOTS', 'none')}")
        else:
            print("   3. Honeybot Wire Log : ⚠️ Could not read remote access.log")
    except Exception as exc:
        print(f"   3. Honeybot Wire Log : ⚠️ SSH check failed ({exc})")
    return 0


YT_STUDIO_THUMB_PATH = Path.home() / "Downloads" / "yt_thumb_latest.jpg"


def _ensure_yt_studio_thumbnail(hero_img_path):
    """If hero_img_path exists on disk, generate a 1280x720 (16:9) YouTube Studio thumbnail at ~/Downloads/yt_thumb_latest.jpg."""
    src = Path(hero_img_path) if hero_img_path else None
    if not src or not src.is_file():
        return None
    try:
        from PIL import Image
        YT_STUDIO_THUMB_PATH.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGBA")
        bg = Image.new("RGB", im.size, (17, 17, 17))
        bg.paste(im, mask=im.split()[3])
        target_w, target_h = 1280, 720
        src_w, src_h = bg.size
        scale = max(target_w / max(1, src_w), target_h / max(1, src_h))
        new_w = max(target_w, int(round(src_w * scale)))
        new_h = max(target_h, int(round(src_h * scale)))
        resized = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        canvas = resized.crop((left, top, left + target_w, top + target_h))
        canvas.save(YT_STUDIO_THUMB_PATH, "JPEG", quality=88, optimize=True, progressive=True)
        return str(YT_STUDIO_THUMB_PATH)
    except Exception:
        return None


def print_broadcast_kit(target_key="1", mode="card", slug_match=None):
    """Print or copy the broadcast kit (mode: help | card | hero | yaml | tweet | linkedin | title | desc)."""
    bar = "=" * 72
    thin = "-" * 72
    kit = get_broadcast_kit(target_key, slug_match=slug_match)
    if mode == "help":
        print(f"\n{bar}")
        print("🚲 GO-GO-GADGET BROADCAST BICYCLE (Step-by-Step Muscle Memory)")
        print(thin)
        print("PHASE 1: ARTICLEIZE & HERO BANNER TLC (Before `publish`)")
        print("  1. article          Sanitize clipboard + generate Jekyll post & prompts")
        print("  2. ythero           📋 Copy AI Hero Banner Prompt -> generate 16:9 image")
        print("  3. ytyaml           📋 Copy YAML `image:` override -> paste into post")
        print("                      frontmatter while moving **TL;DR**: to top in vim")
        print(thin)
        print("PHASE 2: PUBLISH, WIRE PINGS & SOCIAL PROMO (Ship to Honeybot)")
        print("  4. preview          Run knowledge graph, hubs, llms.txt & post_nav")
        print("  5. publish \"msg\"    Commit + push trimnoir, sync GDocs & auto-ping wire")
        print("  6. tweet            📋 Copy X.com Promo Tweet (canonical URL + tags)")
        print("  7. linkedin         📋 Copy LinkedIn Promo Post (imprint + TL;DR + URL)")
        print("  8. ytpebble         🪨 Re-run Wayback + IndexNow wire pings (--dry-run)")
        print(thin)
        print("PHASE 3: YOUTUBE LIVE CUT-AND-ROLL (Slice VOD Episode on Honeybot)")
        print("  9. ytroll stop       ⏹️  Stop OBS first so the old VOD keeps its title/thumb")
        print(" 10. yttitle / ytdesc  📋 Copy Title & Desc -> YT Studio (+ upload yt_thumb_latest.jpg)")
        print(" 11. ytroll start      ▶️  Start OBS stream + ring .reading_trigger (or `ytbell`)")
        print(thin)
        print("PHASE 4: LIVE OBSERVATORY & AUDIENCE INTERACTION (While Streaming)")
        print(" 12. ytstatus          📡 Check Honeybot OBS PID, port 4455 & timecode")
        print(" 13. ytwatch           👀 Check live viewers & chat (`ytwatch start|log|status|stop`)")
        print("     ytlog             📺 Watch live notification stream (`q` or `Ctrl+b d` to exit)")
        print(" 14. ytsay \"text\"      🎙️ Break in LIVE on-air (`-c \"CARD\"` `-p white_rabbit` `-m IMG`)")
        print(" 15. ytapp / ytvim     🖥️ Project local FastHTML (:5001) or live Vim onto stream")
        print("     ytmedia <path>    🖼️ Pop up an image or video on Honeybot :10.0 (`ytsay -m`)")
        print(" 16. ytping \"text\"     📲 Send ntfy.sh push notification to your phone")
        print(" 17. yttop [N]          📊 Keyless YouTube channel top videos & streams radar")
        print(" 18. ytoutro            🔊 Hear deploy-standby outro locally (`ytoutro edit|sync|reboot`)")
        print("     ytreboot           🔄 Sync Honeybot scripts + restart stream.py watchdog child")
        print(" 19. ytcard             📇 Reprint the full Broadcast Kit for the latest post")
        if kit:
            print(thin)
            print(f"📄 Latest Post:   {Path(kit['path']).name}")
            print(f"🖼️  Target Image:  {kit['hero_img_dest']}")
            print(f"✏️  Edit Command:  vim {kit['path']}")
        print(bar)
        return 0
    if not kit:
        print("⚠️ No published post found for broadcast kit.")
        return 1
    if mode == "hero":
        copied = _copy_to_clipboard(kit["hero_prompt"])
        yt_thumb = _ensure_yt_studio_thumbnail(kit["hero_img_dest"])
        print(kit["hero_prompt"])
        print(f"\n{'📋 Copied Hero Banner Image Prompt to clipboard!' if copied else 'ℹ️  (Non-TTY: printed only)'}")
        print(f"🖼️  Save/resize 1200x630 (<500 KB) to: {kit['hero_img_dest']}")
        if yt_thumb:
            print(f"📺 Ready 1280x720 (16:9) YouTube Studio Thumbnail: {yt_thumb}")
        print("👉 Next step: type `ytyaml` to copy the YAML frontmatter block.")
        return 0
    if mode == "yaml":
        copied = _copy_to_clipboard(kit["hero_yaml"])
        print(kit["hero_yaml"])
        print(f"\n{'📋 Copied YAML Frontmatter Image Override to clipboard!' if copied else 'ℹ️  (Non-TTY: printed only)'}")
        print(f"✏️  Paste into frontmatter: vim {kit['path']}")
        return 0
    if mode == "tweet":
        copied = _copy_to_clipboard(kit["tweet"])
        print(kit["tweet"])
        print(f"\n{'📋 Copied X.com Promo Tweet to clipboard!' if copied else 'ℹ️  (Non-TTY: printed only)'}")
        return 0
    if mode == "linkedin":
        copied = _copy_to_clipboard(kit["linkedin"])
        print(kit["linkedin"])
        print(f"\n{'📋 Copied LinkedIn Promo Post to clipboard!' if copied else 'ℹ️  (Non-TTY: printed only)'}")
        return 0
    if mode == "title":
        copied = _copy_to_clipboard(kit["yt_title"])
        print(kit["yt_title"])
        print(f"\n{'📋 Copied YouTube Live Title' if copied else 'ℹ️  YouTube Live Title'} ({len(kit['yt_title'])}/{YT_TITLE_LIMIT} chars)")
        return 0
    if mode == "desc":
        copied = _copy_to_clipboard(kit["yt_description"])
        print(kit["yt_description"])
        print(f"\n{'📋 Copied YouTube Live Description to clipboard!' if copied else 'ℹ️  (Non-TTY: printed only)'}")
        return 0
    print(f"\n{bar}")
    print(f"📡 GO-GO-GADGET BROADCAST KIT ({Path(kit['path']).name})")
    print(thin)
    print("🎨 HERO BANNER PROMPT (type `ythero` to copy):")
    print(kit["hero_prompt"])
    print(thin)
    print("🖼️  YAML FRONTMATTER OVERRIDE (type `ytyaml` to copy):")
    print(kit["hero_yaml"])
    print(thin)
    print("🐦 X.COM PROMO TWEET (type `tweet` to copy):")
    print(kit["tweet"])
    print(thin)
    print("💼 LINKEDIN PROMO POST (type `linkedin` to copy):")
    print(kit["linkedin"])
    print(thin)
    print(f"📺 YOUTUBE LIVE TITLE [{len(kit['yt_title'])}/{YT_TITLE_LIMIT} chars] (type `yttitle` to copy):")
    print(kit["yt_title"])
    print(thin)
    print("📝 YOUTUBE LIVE DESCRIPTION (type `ytdesc` to copy):")
    print(kit["yt_description"])
    print(thin)
    yt_thumb = _ensure_yt_studio_thumbnail(kit["hero_img_dest"])
    if yt_thumb:
        print(thin)
        print(f"📺 YT STUDIO THUMBNAIL (1280x720 16:9): {yt_thumb} (Checklist: Upload thumb + Enable DVR)")
    print("🎛️  Quick Words:  yt (help) | ythero | ytyaml | tweet | linkedin | ytpebble | yttitle | ytdesc | ytcard | yttop | ytoutro | ytreboot | ytsay | ytwatch | ytping | ytroll | ytbell | ytstatus")
    print(thin)
    print(f"🔗 Preview URL:   {kit['preview_url']}")
    print(f"✏️  Edit Command:  vim {kit['path']}")
    print(bar)
    return 0


HONEYBOT_SSH_HOST = os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot")

_HONEYBOT_OBS_HELPER = r'''
import base64, hashlib, json, os, pathlib, socket, struct, subprocess, sys, time

mode = sys.argv[1] if len(sys.argv) > 1 else "status"
cfg_path = pathlib.Path.home() / ".config/obs-studio/plugin_config/obs-websocket/config.json"
trig_path = pathlib.Path.home() / "www/mikelev.in/.reading_trigger"

def load_ws_cfg():
    if cfg_path.is_file():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def ws_recv_json(sock):
    hdr = sock.recv(2)
    if len(hdr) < 2:
        raise RuntimeError("EOF reading WS header")
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", sock.recv(8))[0]
    masked = bool(hdr[1] & 0x80)
    mask_key = sock.recv(4) if masked else b""
    payload = bytearray()
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            break
        payload.extend(chunk)
    if masked:
        payload = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return json.loads(payload.decode("utf-8", errors="replace"))

def ws_send_json(sock, obj):
    raw = json.dumps(obj).encode("utf-8")
    mask_key = os.urandom(4)
    header = bytearray([0x81])
    n = len(raw)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack(">H", n))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack(">Q", n))
    header.extend(mask_key)
    masked = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(raw))
    sock.sendall(header + masked)

def obs_ws_request(req_type):
    cfg = load_ws_cfg()
    port = int(cfg.get("server_port") or 4455)
    password = str(cfg.get("server_password") or "")
    sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    try:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET / HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(1024)
            if not chunk:
                raise RuntimeError("WS handshake failed")
            resp += chunk
        hello = ws_recv_json(sock)
        auth_info = (hello.get("d") or {}).get("authentication")
        ident = {"rpcVersion": 1}
        if auth_info:
            salt = auth_info.get("salt", "")
            challenge = auth_info.get("challenge", "")
            sec_hash = hashlib.sha256((password + salt).encode("utf-8")).digest()
            sec_b64 = base64.b64encode(sec_hash).decode("ascii")
            auth_hash = hashlib.sha256((sec_b64 + challenge).encode("utf-8")).digest()
            ident["authentication"] = base64.b64encode(auth_hash).decode("ascii")
        ws_send_json(sock, {"op": 1, "d": ident})
        identified = ws_recv_json(sock)
        if identified.get("op") != 2:
            raise RuntimeError(f"WS auth/identify rejected: {identified}")
        ws_send_json(sock, {"op": 6, "d": {"requestType": req_type, "requestId": "pip-1"}})
        while True:
            msg = ws_recv_json(sock)
            if msg.get("op") == 7 and (msg.get("d") or {}).get("requestId") == "pip-1":
                return msg.get("d") or {}
    finally:
        sock.close()

def lower_obs_window():
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":10.0")
    subprocess.run(
        ["wmctrl", "-x", "-r", "obs.obs", "-b", "add,below"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

def ring_bell():
    ts = str(int(time.time()))
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    trig_path.write_text(ts + "\n", encoding="utf-8")
    print(f"🔔 Rang Honeybot .reading_trigger={ts} ({trig_path})")

def get_obs_pid():
    for p in sorted(pathlib.Path("/proc").glob("[0-9]*/cmdline")):
        try:
            raw = p.read_bytes()
            if not raw:
                continue
            arg0 = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            if os.path.basename(arg0) in ("obs", ".obs-wrapped"):
                return p.parent.name
        except Exception:
            continue
    return ""

if mode == "bell":
    ring_bell()
    sys.exit(0)

if mode == "enable-ws":
    pid = get_obs_pid()
    saved_env = {}
    if pid and pathlib.Path(f"/proc/{pid}/environ").is_file():
        raw_env = pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\x00")
        for item in raw_env:
            if b"=" in item:
                k, v = item.split(b"=", 1)
                ks = k.decode("utf-8", errors="ignore")
                if ks in ("DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER", "PIPEWIRE_RUNTIME_DIR", "HOME", "USER", "PATH", "XAUTHORITY"):
                    saved_env[ks] = v.decode("utf-8", errors="ignore")
    if pid:
        print(f"🛑 Closing OBS (pid={pid}) cleanly to persist server_enabled=True...")
        subprocess.run(["kill", "-TERM", pid], check=False)
        for _ in range(30):
            if not get_obs_pid():
                break
            time.sleep(0.5)
        if get_obs_pid():
            subprocess.run(["kill", "-KILL", pid], check=False)
            for _ in range(10):
                if not get_obs_pid():
                    break
                time.sleep(0.5)
    sentinel_dir = pathlib.Path.home() / ".config/obs-studio/.sentinel"
    if sentinel_dir.is_dir():
        for sf in sentinel_dir.glob("*"):
            try:
                sf.unlink()
            except Exception:
                pass
    elif sentinel_dir.is_file():
        try:
            sentinel_dir.unlink()
        except Exception:
            pass
    cfg = load_ws_cfg()
    cfg["server_enabled"] = True
    cfg.setdefault("server_port", 4455)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"✅ Enabled obs-websocket in {cfg_path} (port={cfg['server_port']})")
    launch_env = os.environ.copy()
    launch_env.update(saved_env)
    launch_env.setdefault("DISPLAY", ":10.0")
    launch_env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    subprocess.Popen(
        ["obs", "--startstreaming", "--disable-shutdown-check"],
        env=launch_env,
        cwd=str(pathlib.Path.home()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(20):
        time.sleep(1.0)
        try:
            st = obs_ws_request("GetStreamStatus")
            if not (st.get("requestStatus") or {}).get("result"):
                continue
            resp = st.get("responseData") or {}
            lower_obs_window()
            print(f"✅ OBS relaunched, lowered behind stream & WebSocket 4455 LIVE: outputActive={resp.get('outputActive')}")
            sys.exit(0)
        except Exception:
            pass
    print("⚠️ OBS launched, but port 4455 did not answer within 20s.")
    sys.exit(1)

if mode == "status":
    pid = get_obs_pid()
    cfg = load_ws_cfg()
    trig = trig_path.read_text(encoding="utf-8").strip() if trig_path.is_file() else "absent"
    print(f"📡 Honeybot OBS: pid={pid or 'NONE'} | ws_enabled={cfg.get('server_enabled')} | port={cfg.get('server_port', 4455)} | trigger={trig}")
    if cfg.get("server_enabled"):
        try:
            st = obs_ws_request("GetStreamStatus")
            resp = st.get("responseData") or {}
            print(f"🎥 Stream Status: outputActive={resp.get('outputActive')} | timecode={resp.get('outputTimecode')}")
        except Exception as e:
            print(f"⚠️ WebSocket 4455 unreachable: {e}")
    else:
        print("ℹ️  obs-websocket is currently disabled. Run `ytroll enable-ws` once to activate remote control.")
    sys.exit(0)

cfg = load_ws_cfg()
if not cfg.get("server_enabled"):
    print("⚠️ obs-websocket is disabled on Honeybot. Run `ytroll enable-ws` once to enable port 4455.")
    sys.exit(1)

if mode in ("stop", "roll"):
    res = obs_ws_request("StopStream")
    print(f"⏹️  OBS StopStream sent (status={res.get('requestStatus', {}).get('code')})")
    for _ in range(15):
        time.sleep(0.5)
        st = (obs_ws_request("GetStreamStatus").get("responseData") or {})
        if not st.get("outputActive"):
            print("✅ OBS stream stopped cleanly.")
            break

if mode == "roll":
    print("⏳ Waiting 4s for YouTube RTMP session boundary...")
    time.sleep(4.0)

if mode in ("start", "roll"):
    lower_obs_window()
    res = obs_ws_request("StartStream")
    print(f"▶️  OBS StartStream sent (status={res.get('requestStatus', {}).get('code')})")
    for _ in range(15):
        time.sleep(0.5)
        st = (obs_ws_request("GetStreamStatus").get("responseData") or {})
        if st.get("outputActive"):
            print(f"✅ OBS stream LIVE (timecode={st.get('outputTimecode')}).")
            break
    ring_bell()
'''


def run_honeybot_obs(mode="status"):
    """Execute remote OBS WebSocket / bell control on Honeybot over SSH."""
    import subprocess
    res = subprocess.run(
        ["ssh", HONEYBOT_SSH_HOST, "python3", "-", mode],
        input=_HONEYBOT_OBS_HELPER,
        text=True,
    )
    return res.returncode


def _read_from_clipboard():
    """Read text from the OS clipboard for `ytsay --clip`."""
    import subprocess
    cmd = ["pbpaste"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard", "-o"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""


_HONEYBOT_LIVE_MSG_HELPER = r'''
import base64, pathlib, sys

raw = base64.b64decode(sys.argv[1].encode("ascii")).decode("utf-8")
p = pathlib.Path.home() / "www/mikelev.in/.live_message"
p.parent.mkdir(parents=True, exist_ok=True)
tmp = p.with_suffix(".tmp")
tmp.write_text(raw, encoding="utf-8")
tmp.replace(p)
print(f"📡 Live break-in queued on Honeybot: {p}")
'''


def send_honeybot_live_message(
    say_text,
    card_label=None,
    patronus_key=None,
    media_path=None,
    window_spec=None,
    pre_pause=3.0,
    linger=2.5,
    dry_run=False,
):
    """Send a one-shot live operator break-in (.live_message) to Honeybot over SSH."""
    import base64
    import subprocess
    import time
    raw_lines = [ln.strip() for ln in (say_text or "").splitlines() if ln.strip()]
    cli_card = card_label is not None
    cli_patronus = patronus_key is not None
    cli_media = media_path is not None
    cli_window = window_spec is not None
    while raw_lines:
        head_upper = raw_lines[0].upper()
        if head_upper.startswith("CARD:") and not cli_card:
            val = raw_lines.pop(0)[5:].strip()
            if val:
                card_label = f"{card_label}\n{val}" if card_label else val
        elif head_upper.startswith("PATRONUS:") and not cli_patronus:
            patronus_key = raw_lines.pop(0)[9:].strip()
        elif head_upper.startswith(("MEDIA:", "IMAGE:", "VIDEO:")) and not cli_media:
            media_path = raw_lines.pop(0).split(":", 1)[1].strip()
        elif head_upper.startswith("WINDOW:") and not cli_window:
            window_spec = raw_lines.pop(0)[7:].strip()
        else:
            break
    clean_say = " ".join(" ".join(raw_lines).split())
    if not any((clean_say, card_label, patronus_key, media_path, window_spec)):
        print("Usage: ytsay [-c 'CARD\\nTEXT'] [-p patronus_key] [-m image_or_video] [-w window_spec] [--pre 3.0] [--linger 2.5] [--clip] [--dry-run] 'Message to speak live'")
        return 1
    has_visual_override = bool(patronus_key or media_path or window_spec)
    if card_label is None:
        resolved_card = "" if has_visual_override else "LIVE\nFROM MIKE"
    else:
        resolved_card = str(card_label).replace("\\n", "\n")
    resolved_media = str(media_path).strip() if media_path else ""
    media_dur = None
    if resolved_media and ":" in resolved_media and not resolved_media.startswith(("http://", "https://", "file://")):
        m_head, m_tail = resolved_media.rsplit(":", 1)
        try:
            media_dur = float(m_tail.strip())
            resolved_media = m_head.strip()
        except ValueError:
            pass
    local_media_file = None
    composited_tmp_file = None
    if resolved_media and not resolved_media.startswith(("http://", "https://", "file://")):
        cand = Path(resolved_media).expanduser()
        if not cand.is_file():
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                import weebo
                w_target, w_dur, _ = weebo.resolve_media_target(
                    resolved_media, default_duration=media_dur or 8.0, enroll=(not dry_run)
                )
                if w_target and os.path.isfile(w_target):
                    cand = Path(w_target)
                    if media_dur is None:
                        media_dur = w_dur
            except Exception:
                pass
        if cand.is_file():
            local_media_file = enroll_cand = cand.resolve()
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                import weebo
                if not dry_run:
                    weebo.enroll_in_local_library(enroll_cand)
                buf_path, was_comp, _, _, _, _ = weebo.prepare_backbuffer(str(local_media_file), matte=False)
                if was_comp and buf_path and os.path.isfile(buf_path):
                    composited_tmp_file = Path(buf_path)
            except Exception:
                pass
            safe_fname = re.sub(r"[^A-Za-z0-9._-]", "_", local_media_file.name)
            resolved_media = f"/home/mike/www/mikelev.in/assets/weebo/{safe_fname}"
    if resolved_media and media_dur is not None:
        resolved_media = f"{resolved_media}:{media_dur:g}"
    eff_pre_pause = float(pre_pause)
    eff_linger = float(linger)
    if not clean_say and has_visual_override:
        if eff_pre_pause == 3.0:
            eff_pre_pause = 0.5
        if media_dur is not None:
            eff_linger = max(eff_linger, float(media_dur))
        elif eff_linger == 2.5:
            eff_linger = 8.0
    payload = {
        "card": resolved_card,
        "say": clean_say,
        "pre_pause": eff_pre_pause,
        "linger": eff_linger,
        "sent_at": int(time.time()),
    }
    if patronus_key:
        payload["patronus"] = str(patronus_key).strip()
    if resolved_media:
        payload["media"] = resolved_media
    if local_media_file is not None:
        payload["staged_from"] = str(local_media_file)
    if window_spec:
        payload["window"] = str(window_spec).strip()
    payload_json = json.dumps(payload, indent=2)
    if dry_run:
        if composited_tmp_file is not None and composited_tmp_file.is_file():
            composited_tmp_file.unlink(missing_ok=True)
        print("📡 [DRY RUN] Live break-in payload for Honeybot:")
        print(payload_json)
        return 0
    if local_media_file is not None:
        remote_dest = resolved_media.rsplit(":", 1)[0] if media_dur is not None else resolved_media
        src_to_scp = composited_tmp_file if (composited_tmp_file is not None and composited_tmp_file.is_file()) else local_media_file
        subprocess.run(
            ["ssh", HONEYBOT_SSH_HOST, "mkdir", "-p", "/home/mike/www/mikelev.in/assets/weebo", "/tmp/honeybot_media"],
            check=False,
        )
        scp_res = subprocess.run(
            ["scp", "-q", str(src_to_scp), f"{HONEYBOT_SSH_HOST}:{remote_dest}"],
            check=False,
        )
        if composited_tmp_file is not None and composited_tmp_file.is_file():
            composited_tmp_file.unlink(missing_ok=True)
        if scp_res.returncode == 0:
            print(f"🖼️  Staged local media to Honeybot: {local_media_file.name} -> {remote_dest}")
        else:
            print(f"⚠️ Failed to stage local media {local_media_file} to Honeybot (exit {scp_res.returncode})")
            return scp_res.returncode
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
    res = subprocess.run(
        ["ssh", HONEYBOT_SSH_HOST, "python3", "-", payload_b64],
        input=_HONEYBOT_LIVE_MSG_HELPER,
        text=True,
    )
    if res.returncode == 0:
        if resolved_card:
            preview_card = resolved_card.replace("\n", " | ")
        elif media_path:
            preview_card = f"MEDIA:{media_path}"
        elif window_spec:
            preview_card = f"WINDOW:{window_spec}"
        else:
            preview_card = f"PATRONUS:{patronus_key}"
        print(f"🎙️  Card: [{preview_card}] | Say: {clean_say!r}")
    return res.returncode


VAULT_ENV_FILE = CONFIG_DIR / ".env"
YTWATCH_STATE_FILE = CONFIG_DIR / "ytwatch_state.json"
DEFAULT_YT_LIVE_URL = "https://www.youtube.com/@MikeLevin/live"


def _load_vault_env():
    """Read key=value pairs from ~/.config/pipulate/.env without exposing values."""
    pairs = {}
    if not VAULT_ENV_FILE.is_file():
        return pairs
    try:
        for line in VAULT_ENV_FILE.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            if k.lower().startswith("export "):
                k = k[7:].strip()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            if k:
                pairs[k] = v
    except OSError:
        pass
    return pairs


def _get_vault_var(name, default=""):
    """Return env var from os.environ first, then ~/.config/pipulate/.env."""
    return os.environ.get(name) or _load_vault_env().get(name) or default


def _save_vault_var(name, value):
    """Upsert name=value into ~/.config/pipulate/.env (mode 0600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not VAULT_ENV_FILE.exists():
        VAULT_ENV_FILE.touch(mode=0o600)
    os.chmod(VAULT_ENV_FILE, 0o600)
    lines = []
    if VAULT_ENV_FILE.is_file():
        lines = VAULT_ENV_FILE.read_text(encoding="utf-8").splitlines()
    escaped = str(value).replace("'", "'\\''")
    rendered = f"{name}='{escaped}'"
    replaced = False
    for idx, line in enumerate(lines):
        lhs = line.split("=", 1)[0].strip().replace("export ", "")
        if lhs == name:
            lines[idx] = rendered
            replaced = True
            break
    if not replaced:
        lines.append(rendered)
    VAULT_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def send_ntfy_notification(
    message,
    title="Honeybot Live",
    priority="default",
    tags="tv",
    topic=None,
    init_topic=False,
    dry_run=False,
):
    """Send a push notification via ntfy.sh (LAN outbound HTTPS POST, zero deps)."""
    import secrets
    import urllib.error
    import urllib.request
    resolved_topic = (topic or _get_vault_var("PIPULATE_NTFY_TOPIC")).strip()
    if init_topic and not resolved_topic:
        resolved_topic = f"pipulate-hb-{secrets.token_hex(8)}"
        _save_vault_var("PIPULATE_NTFY_TOPIC", resolved_topic)
        print(f"🔑 Minted PIPULATE_NTFY_TOPIC in {VAULT_ENV_FILE} (0600)")
        print(f"📲 Subscribe in the ntfy phone app to topic: {resolved_topic}")
        print(f"   (or open https://ntfy.sh/{resolved_topic})")
    body = (message or "").strip() or "Ping from Pipulate Prime"
    if dry_run:
        topic_state = "configured" if resolved_topic else "unconfigured (pass --init to mint)"
        print(f"📡 [DRY RUN] ntfy push: topic={topic_state} | title={title!r} | priority={priority} | body={body!r}")
        return 0
    if not resolved_topic:
        print("⚠️ No PIPULATE_NTFY_TOPIC configured in ~/.config/pipulate/.env.")
        print("   Mint one and send a test push with:  ytping --init 'Hello from Pipulate Prime'")
        return 1
    url = f"https://ntfy.sh/{resolved_topic}"
    safe_title = title.encode("ascii", errors="ignore").decode("ascii").strip() or "Honeybot Live"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Title": safe_title,
            "Priority": str(priority or "default"),
            "Tags": str(tags or "tv"),
            "User-Agent": "pipulate-ytping/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = getattr(resp, "status", 200)
        masked = resolved_topic[:15] + "..." if len(resolved_topic) > 18 else resolved_topic
        print(f"🔔 Sent ntfy push (HTTP {status} -> {masked}): [{title}] {body}")
        return 0
    except urllib.error.URLError as exc:
        print(f"❌ ntfy push failed: {exc}")
        return 1


def _extract_yt_json(html_text, marker):
    """Extract balanced JSON object following marker using JSONDecoder.raw_decode."""
    idx = html_text.find(marker)
    if idx < 0:
        return {}
    brace = html_text.find("{", idx + len(marker))
    if brace < 0:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(html_text, brace)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _walk_dicts(node):
    """Iterative depth-first walk yielding every dict inside a parsed JSON tree."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for val in cur.values():
                if isinstance(val, (dict, list)):
                    stack.append(val)
        elif isinstance(cur, list):
            for item in cur:
                if isinstance(item, (dict, list)):
                    stack.append(item)


_YTWATCH_RESERVED_ACTIONS = {
    "start", "stop", "status", "restart", "daemon", "kill",
    "attach", "log", "logs", "tail", "tmux",
}


def _is_self_chat_author(msg_author, channel_author=""):
    """True when a YouTube chat author is the broadcaster (@MikeLevin / Mike Levin)."""
    def _norm(s):
        return re.sub(r"[\s@_-]+", "", (s or "").strip().lower())
    norm_msg = _norm(msg_author)
    if not norm_msg:
        return False
    self_norms = {"mikelevin"}
    if channel_author:
        self_norms.add(_norm(channel_author))
    cfg_ch = _get_vault_var("PIPULATE_YT_CHANNEL")
    if cfg_ch and not cfg_ch.startswith(("http://", "https://")):
        self_norms.add(_norm(cfg_ch))
    return norm_msg in self_norms


def _normalize_yt_url(channel_or_url):
    """Normalize @handle, video ID, or URL into a fetchable YouTube watch/live URL."""
    raw = (channel_or_url or "").strip()
    if not raw or raw.lower().lstrip("@") in _YTWATCH_RESERVED_ACTIONS:
        return DEFAULT_YT_LIVE_URL
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("@"):
        return f"https://www.youtube.com/{raw}/live"
    if re.match(r"^[A-Za-z0-9_-]{11}$", raw):
        return f"https://www.youtube.com/watch?v={raw}"
    return f"https://www.youtube.com/@{raw}/live"


def _fetch_yt_chat_messages(continuation):
    """Fetch current live chat messages from youtubei/v1/live_chat/get_live_chat."""
    import urllib.request
    if not continuation:
        return []
    url = "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?prettyPrint=false"
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250101.00.00",
                "hl": "en",
                "gl": "US",
            }
        },
        "continuation": continuation,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    messages = []
    for d in _walk_dicts(data):
        renderer = d.get("liveChatTextMessageRenderer")
        if not isinstance(renderer, dict):
            continue
        msg_id = str(renderer.get("id") or "")
        author = str((renderer.get("authorName") or {}).get("simpleText") or "viewer")
        runs = (renderer.get("message") or {}).get("runs") or []
        parts = []
        for r in runs:
            if not isinstance(r, dict):
                continue
            if "text" in r:
                parts.append(str(r["text"]))
            elif "emoji" in r and isinstance(r["emoji"], dict):
                shortcuts = r["emoji"].get("shortcuts") or []
                parts.append(str(shortcuts[0]) if shortcuts else str(r["emoji"].get("emojiId") or ""))
        text = "".join(parts).strip()
        if msg_id and text:
            messages.append({
                "id": msg_id,
                "author": author,
                "text": text,
                "timestamp_usec": str(renderer.get("timestampUsec") or ""),
            })
    messages.sort(key=lambda m: m["timestamp_usec"])
    return messages


def fetch_youtube_live_state(channel_or_url=None):
    """Fetch keyless YouTube Live state (is_live, video_id, viewers, chat_messages)."""
    import urllib.request
    url = _normalize_yt_url(channel_or_url or _get_vault_var("PIPULATE_YT_CHANNEL"))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_text = resp.read().decode("utf-8", errors="replace")
    player = _extract_yt_json(html_text, "ytInitialPlayerResponse =")
    initial = _extract_yt_json(html_text, "ytInitialData =")
    vd = player.get("videoDetails") if isinstance(player.get("videoDetails"), dict) else {}
    video_id = str(vd.get("videoId") or "")
    title = str(vd.get("title") or "")
    author = str(vd.get("author") or "")
    is_live = bool(vd.get("isLive"))
    concurrent_viewers = 0
    chat_continuation = ""
    for d in _walk_dicts(initial):
        vvc = d.get("videoViewCountRenderer")
        if isinstance(vvc, dict) and vvc.get("isLive"):
            is_live = True
            vc = vvc.get("viewCount") or {}
            raw_vc = str(vc.get("simpleText") or "")
            if not raw_vc and isinstance(vc.get("runs"), list):
                raw_vc = "".join(str(r.get("text") or "") for r in vc["runs"] if isinstance(r, dict))
            if not raw_vc:
                raw_vc = str(vvc.get("originalViewCount") or "")
            digits = re.sub(r"[^\d]", "", raw_vc)
            if digits:
                concurrent_viewers = int(digits)
        lcr = d.get("liveChatRenderer")
        if isinstance(lcr, dict) and not chat_continuation:
            for cont in lcr.get("continuations") or []:
                if not isinstance(cont, dict):
                    continue
                for k in ("timedContinuationData", "invalidationContinuationData", "reloadContinuationData"):
                    if isinstance(cont.get(k), dict) and cont[k].get("continuation"):
                        chat_continuation = str(cont[k]["continuation"])
                        break
    chat_messages = _fetch_yt_chat_messages(chat_continuation) if (is_live and chat_continuation) else []
    comment_count = None
    yt_api_key = _get_vault_var("YOUTUBE_API_KEY") or load_keys_dict().get("youtube")
    if yt_api_key and video_id:
        try:
            api_url = (
                f"https://www.googleapis.com/youtube/v3/videos"
                f"?part=statistics&id={video_id}&key={yt_api_key}"
            )
            with urllib.request.urlopen(api_url, timeout=10) as aresp:
                adata = json.loads(aresp.read().decode("utf-8", errors="replace"))
            items = adata.get("items") or []
            if items:
                c_str = ((items[0].get("statistics") or {}).get("commentCount"))
                if c_str is not None:
                    comment_count = int(c_str)
        except Exception:
            comment_count = None
    return {
        "url": url,
        "is_live": is_live,
        "video_id": video_id,
        "title": title,
        "author": author,
        "concurrent_viewers": concurrent_viewers,
        "chat_messages": chat_messages,
        "comment_count": comment_count,
    }


def _load_ytwatch_state():
    """Load persisted ytwatch state from ~/.config/pipulate/ytwatch_state.json."""
    if YTWATCH_STATE_FILE.is_file():
        try:
            data = json.loads(YTWATCH_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_ytwatch_state(state_obj):
    """Persist ytwatch state to ~/.config/pipulate/ytwatch_state.json."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        YTWATCH_STATE_FILE.write_text(json.dumps(state_obj, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _sustained_viewer_count(dwell_window, now_ts, dwell_secs):
    """Return the viewer count continuously sustained for at least dwell_secs, or 0."""
    if not dwell_window:
        return 0
    if dwell_secs <= 0:
        return int(dwell_window[-1][1])
    run_min = int(dwell_window[-1][1])
    for ts, v in reversed(dwell_window):
        run_min = min(run_min, int(v))
        if (now_ts - float(ts)) >= dwell_secs:
            return run_min
    return 0


SPOKEN_ALERT_TABLE = {
    "viewers_threshold": "Web Bot Observatory alert. YouTube concurrent viewers reached {count}, meeting the summon threshold of {min_viewers}.",
    "viewers_above_2": "Web Bot Observatory alert. YouTube concurrent viewers climbed above two, now at {count}.",
    "live_comment": "Web Bot Observatory alert. A new comment was posted on the live stream by {author}.",
    "src=youtube": "Web Bot Observatory alert. A link was followed from YouTube.",
    "src=linkedin": "Web Bot Observatory alert. A link was followed from LinkedIn.",
    "src=x": "Web Bot Observatory alert. A link was followed from X dot com.",
    "src=twitter": "Web Bot Observatory alert. A link was followed from X dot com.",
    "src=rfc9110": "Web Bot Observatory alert. An engineer just ran the R F C 9110 terminal verification test.",
    "default": "Web Bot Observatory notification. {message}",
}


def _ensure_local_piper_model():
    """Locate or pull en_US-amy-low.onnx across Pipulate Prime's voice caches."""
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    voice_dir = Path.home() / ".local/share/piper_voices"
    model_name = "en_US-amy-low.onnx"
    candidates = [
        CONFIG_DIR / "piper_models" / model_name,
        repo_root / "assets" / "piper_models" / model_name,
        voice_dir / model_name,
        repo_root / "piper_models" / model_name,
    ]
    for c in candidates:
        if c.is_file() and Path(f"{c}.json").is_file():
            return c
    voice_dir.mkdir(parents=True, exist_ok=True)
    target_model = voice_dir / model_name
    target_json = voice_dir / f"{model_name}.json"
    for suffix, dest in (("", target_model), (".json", target_json)):
        if not dest.is_file():
            try:
                subprocess.run(
                    ["scp", "-q", f"{HONEYBOT_SSH_HOST}:.local/share/piper_voices/{model_name}{suffix}", str(dest)],
                    timeout=8,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
    if target_model.is_file() and target_json.is_file():
        return target_model
    return None


def _speak_local_alert(text, enabled=True):
    """Speak an alert out loud on Pipulate Prime using Piper TTS after ding.wav."""
    if not enabled or not text:
        return
    import shutil
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    piper_bin = str(repo_root / ".venv/bin/piper")
    if not Path(piper_bin).is_file():
        piper_bin = shutil.which("piper") or ""
    model_path = _ensure_local_piper_model()
    if not piper_bin or not model_path:
        return
    clean_text = re.sub(r"[^\w\s.,?!:-]", " ", str(text))
    clean_text = " ".join(clean_text.split())[:220]
    if not clean_text:
        return
    worker_code = (
        "import os, shutil, subprocess, sys, time; "
        "time.sleep(0.45); "
        "wav = f'/tmp/pipulate_alert_{os.getpid()}.wav'; "
        "subprocess.run([sys.argv[2], '--model', sys.argv[3], '--output_file', wav], "
        "input=sys.argv[1].encode('utf-8'), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "cmds = (['pw-play', wav], ['paplay', wav], ['aplay', '-q', wav], ['afplay', wav]); "
        "play = next((c for c in cmds if shutil.which(c[0])), None); "
        "subprocess.run(play, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if (play and os.path.isfile(wav)) else None; "
        "os.remove(wav) if os.path.isfile(wav) else None"
    )
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                worker_code,
                clean_text,
                piper_bin,
                str(model_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _play_local_ding(enabled=True, spoken_text=None):
    """Play assets/sounds/ding.wav locally on Prime and optionally speak an alert via Piper TTS."""
    if not enabled:
        return
    import shutil
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    ding_candidates = [
        Path.home() / ".local/share/pipulate/ding.wav",
        repo_root / "assets/sounds/ding.wav",
    ]
    sound_path = next((p for p in ding_candidates if p.is_file()), None)
    if sound_path:
        for player_cmd in (["pw-play"], ["paplay"], ["aplay", "-q"], ["afplay"]):
            if shutil.which(player_cmd[0]):
                try:
                    subprocess.Popen(
                        [*player_cmd, str(sound_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
                break
    if spoken_text:
        _speak_local_alert(spoken_text, enabled=enabled)


def _manage_ytwatch_daemon(action, interval=30, channel=None):
    """Start, stop, or inspect the background tmux 'ytwatch' session on Prime."""
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    log_path = Path("/tmp/ytwatch.log")
    has_res = subprocess.run(
        ["tmux", "has-session", "-t", "ytwatch"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    is_running = (has_res.returncode == 0)
    if action == "status":
        print(f"📡 ytwatch daemon: {'RUNNING (tmux session: ytwatch)' if is_running else 'STOPPED'}")
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
            if lines:
                print(f"--- Last {len(lines)} line(s) of {log_path} ---")
                for ln in lines:
                    print(f"   {ln}")
        return 0
    if action == "stop":
        if is_running:
            subprocess.run(["tmux", "kill-session", "-t", "ytwatch"], check=False)
            print("🛑 Stopped background tmux session 'ytwatch'.")
        else:
            print("ℹ️  No background 'ytwatch' tmux session was running.")
        return 0
    def _style_ytwatch_tmux():
        for opt, val in (
            ("status", "on"),
            ("status-style", "bg=colour235,fg=colour51,bold"),
            ("status-left-length", "28"),
            ("status-left", " 🔭 YTWATCH LIVE "),
            ("status-right-length", "68"),
            ("status-right", " EXIT (KEEP RUNNING): Press q OR Ctrl+b then d "),
        ):
            subprocess.run(
                ["tmux", "set-option", "-t", "ytwatch", opt, val],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    if action in ("daemon", "start", "restart"):
        if channel:
            _save_vault_var("PIPULATE_YT_CHANNEL", channel.strip())
        if is_running:
            subprocess.run(["tmux", "kill-session", "-t", "ytwatch"], check=False)
        py_bin = repo_root / ".venv/bin/python"
        script_path = Path(__file__).resolve()
        cmd_str = (
            f"PYTHONUNBUFFERED=1 {py_bin} {script_path} --broadcast watch "
            f"--loop --interval {max(5, int(interval))} 2>&1 | tee {log_path}"
        )
        res = subprocess.run(
            ["tmux", "new-session", "-d", "-s", "ytwatch", "-c", str(repo_root), cmd_str],
            check=False,
        )
        if res.returncode == 0:
            _style_ytwatch_tmux()
            print(f"🔭 Started background 'ytwatch' daemon in tmux (polling every {max(5, int(interval))}s).")
            print("   • Watch live stream: ytwatch log   (or `ytlog` — press `q` or `Ctrl+b d` to exit)")
            print("   • Check status:      ytwatch status")
            print("   • Stop daemon:       ytwatch stop")
            return 0
        print("❌ Failed to start tmux session 'ytwatch'.")
        return 1
    if action == "attach":
        if not is_running:
            print("🔭 'ytwatch' daemon was not running — starting it now...")
            rc = _manage_ytwatch_daemon("start", interval=interval, channel=channel)
            if rc != 0:
                return rc
        _style_ytwatch_tmux()
        if not sys.stdout.isatty():
            print("📡 [NON-TTY] ytwatch attach ready (tmux session: ytwatch)")
            return _manage_ytwatch_daemon("status", interval=interval, channel=channel)
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║ 🔭 ENTERING YTWATCH LIVE TMUX MONITOR (Read-Only Safe Mode)          ║")
        print("║ • Muscle-Memory Detach : Press Ctrl+b, release both, then press d    ║")
        print("║ • Quick Escape Hatch   : Press q (detaches & keeps daemon running!)  ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        subprocess.run(["tmux", "bind-key", "-n", "q", "detach-client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            subprocess.run(["tmux", "attach-session", "-r", "-t", "ytwatch"], check=False)
        finally:
            subprocess.run(["tmux", "unbind-key", "-n", "q"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        print("✅ Detached from 'ytwatch' monitor (daemon is STILL RUNNING in background).")
        return 0
    return 0


def _trigger_ytwatch_weebo(weebo_spec=None, duration=None):
    """Fire an undampened non-blocking centered Weebo popup on Honeybot :10.0 when ytwatch hits a viewer milestone."""
    import subprocess
    cfg_spec = (weebo_spec or _get_vault_var("PIPULATE_YTWATCH_WEEBO") or "auto").strip()
    if cfg_spec.lower() in ("0", "off", "false", "none"):
        return
    repo_root = Path(__file__).resolve().parents[2]
    weebo_script = repo_root / "scripts" / "weebo.py"
    if not weebo_script.is_file():
        return
    chosen = cfg_spec
    if chosen.lower() == "auto":
        chosen = "mike-headroom"
        local_lib = Path.home() / ".local" / "share" / "pipulate" / "weebo"
        if local_lib.is_dir():
            files = [p for p in local_lib.iterdir() if p.is_file()]
            files.sort(
                key=lambda x: (
                    x.suffix.lower() in (".mov", ".mp4", ".webm", ".mkv"),
                    x.stat().st_mtime,
                ),
                reverse=True,
            )
            for p in files:
                stem_l = p.stem.lower()
                if any(k in stem_l for k in ("mike-headroom", "headroom", "max", "halloween")):
                    chosen = p.stem
                    break
    try:
        cmd = [sys.executable, str(weebo_script), "--remote", str(chosen)]
        if duration is not None:
            cmd.append(str(duration))
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        dur_lbl = f"{duration:g}s" if duration is not None else "full-clip"
        print(f"🎭 [WEEBO] Auto-popped '{chosen}' ({dur_lbl}) on Honeybot :10.0 for viewer arrival!", flush=True)
    except Exception:
        pass


def run_youtube_watch(
    channel=None,
    loop=False,
    interval=30,
    topic=None,
    init_topic=False,
    notify_once=False,
    ding=True,
    daemon_action=None,
    dry_run=False,
):
    """Check or continuously monitor YouTube Live viewers + chat/comments on Prime."""
    import subprocess
    import time
    saved_ch = _get_vault_var("PIPULATE_YT_CHANNEL").strip()
    if saved_ch.lower().lstrip("@") in _YTWATCH_RESERVED_ACTIONS:
        _save_vault_var("PIPULATE_YT_CHANNEL", "@MikeLevin")
    if daemon_action in ("daemon", "start", "restart", "stop", "status", "attach"):
        if dry_run:
            print(f"📡 [DRY RUN] ytwatch daemon_action={daemon_action} | interval={interval}")
            return 0
        return _manage_ytwatch_daemon(daemon_action, interval=interval, channel=channel)
    if channel and channel.strip().lower().lstrip("@") not in _YTWATCH_RESERVED_ACTIONS:
        _save_vault_var("PIPULATE_YT_CHANNEL", channel.strip())
    resolved_channel = _normalize_yt_url(channel or _get_vault_var("PIPULATE_YT_CHANNEL"))
    resolved_topic = (topic or _get_vault_var("PIPULATE_NTFY_TOPIC")).strip()
    if init_topic and not resolved_topic:
        send_ntfy_notification("YouTube Live monitor initialized", init_topic=True, dry_run=dry_run)
        resolved_topic = _get_vault_var("PIPULATE_NTFY_TOPIC")
    if dry_run:
        sample = 'var ytInitialPlayerResponse = {"videoDetails":{"videoId":"test1234567","isLive":true}};'
        parsed = _extract_yt_json(sample, "ytInitialPlayerResponse =")
        ok = (parsed.get("videoDetails") or {}).get("videoId") == "test1234567"
        t_label = "configured" if resolved_topic else "unconfigured"
        print(f"📡 [DRY RUN] YouTube Watch: channel={resolved_channel} | min_viewers={YT_VIEWER_ALERT_MIN} | dwell={YT_VIEWER_ALERT_DWELL}s | ntfy={t_label} | parser_ok={ok}")
        return 0 if ok else 1
    try:
        state = fetch_youtube_live_state(resolved_channel)
    except Exception as exc:
        print(f"❌ YouTube Watch fetch failed for {resolved_channel}: {exc}")
        return 1
    persisted = _load_ytwatch_state()
    same_video = (persisted.get("video_id") == state["video_id"] and bool(state["video_id"]))
    seen_ids = set(persisted.get("seen_ids") or []) if same_video else set()
    had_prior_snapshot = bool(same_video and persisted.get("seen_ids") is not None)
    peak_viewers = int(persisted.get("peak_viewers") or 0) if same_video else 0
    prev_comments = persisted.get("comment_count") if same_video else state["comment_count"]
    last_viewer_alert = float(persisted.get("last_viewer_alert") or 0.0) if same_video else 0.0
    alerted_in_run = bool(persisted.get("alerted_in_run")) if (same_video and state["concurrent_viewers"] >= YT_VIEWER_ALERT_MIN) else False
    weebo_peak_viewers = int(persisted.get("weebo_peak_viewers") or 0) if (same_video and state["concurrent_viewers"] >= YT_VIEWER_ALERT_MIN) else 0
    daemon_running = (
        subprocess.run(
            ["tmux", "has-session", "-t", "ytwatch"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    )
    c_str = f" | comments={state['comment_count']}" if state["comment_count"] is not None else ""
    d_str = " | daemon=RUNNING" if daemon_running else ""
    print(
        f"📡 YouTube Watch: LIVE={'yes' if state['is_live'] else 'no'} | "
        f"video={state['video_id'] or 'NONE'} | viewers={state['concurrent_viewers']} (alert>={YT_VIEWER_ALERT_MIN} for {YT_VIEWER_ALERT_DWELL}s) | "
        f"chat_items={len(state['chat_messages'])}{c_str}{d_str} | title={state['title']!r}"
    )
    if not loop:
        recent = state["chat_messages"][-5:]
        for msg in recent:
            is_new = had_prior_snapshot and (msg["id"] not in seen_ids)
            badge = "🆕 [NEW] " if is_new else ""
            print(f"   💬 {badge}{msg['author']}: {msg['text']}")
            if is_new and not _is_self_chat_author(msg["author"], state.get("author")):
                print(f"      ↳ Reply on-air: ytsay \"Hey {msg['author']}, thanks for tuning in!\"")
                if notify_once and resolved_topic:
                    _play_local_ding(
                        ding,
                        spoken_text=SPOKEN_ALERT_TABLE["live_comment"].format(author=msg["author"]),
                    )
                    send_ntfy_notification(
                        f"{msg['author']}: {msg['text']}",
                        title="💬 Honeybot Live Chat",
                        priority="high",
                        tags="speech_balloon",
                        topic=resolved_topic,
                    )
        all_ids = list(dict.fromkeys([*(persisted.get("seen_ids") or []), *(m["id"] for m in state["chat_messages"])]))[-500:]
        _save_ytwatch_state({
            "video_id": state["video_id"],
            "concurrent_viewers": state["concurrent_viewers"],
            "peak_viewers": peak_viewers,
            "alerted_in_run": alerted_in_run,
            "comment_count": state["comment_count"],
            "last_viewer_alert": last_viewer_alert,
            "seen_ids": all_ids,
            "updated_at": int(time.time()),
        })
        return 0
    for m in state["chat_messages"]:
        seen_ids.add(m["id"])
    init_ts = time.time()
    dwell_window = [(init_ts, state["concurrent_viewers"])] if state["concurrent_viewers"] >= YT_VIEWER_ALERT_MIN else []
    _save_ytwatch_state({
        "video_id": state["video_id"],
        "concurrent_viewers": state["concurrent_viewers"],
        "peak_viewers": peak_viewers,
        "alerted_in_run": alerted_in_run,
        "comment_count": state["comment_count"],
        "last_viewer_alert": last_viewer_alert,
        "seen_ids": list(seen_ids)[-500:],
        "updated_at": int(init_ts),
    })
    print(f"🔭 Watching {resolved_channel} every {interval}s (dwell={YT_VIEWER_ALERT_DWELL}s)...")
    print("💡 [HOW TO EXIT TMUX WITHOUT STOPPING]: Press 'q' OR press Ctrl+b, release, then press d")
    try:
        while True:
            time.sleep(max(5, int(interval)))
            poll_ts = time.time()
            try:
                state = fetch_youtube_live_state(resolved_channel)
            except Exception as exc:
                print(f"⚠️ Poll error: {exc}")
                continue
            viewers = state["concurrent_viewers"]
            now = time.time()
            if viewers >= YT_VIEWER_ALERT_MIN:
                if viewers > weebo_peak_viewers:
                    weebo_peak_viewers = viewers
                    _trigger_ytwatch_weebo()
                dwell_window.append((poll_ts, viewers))
                cutoff_ts = poll_ts - max(YT_VIEWER_ALERT_DWELL * 3, int(interval) * 4)
                dwell_window = [(ts, v) for ts, v in dwell_window if ts >= cutoff_ts]
                if len(dwell_window) == 1 and YT_VIEWER_ALERT_DWELL > 0:
                    print(
                        f"⏳ [VIEWER DWELL] {viewers} watching (min={YT_VIEWER_ALERT_MIN}) — "
                        f"holding {YT_VIEWER_ALERT_DWELL}s to confirm they stick around...",
                        flush=True,
                    )
                sustained = _sustained_viewer_count(dwell_window, poll_ts, YT_VIEWER_ALERT_DWELL)
                cooldown_ok = (now - last_viewer_alert) > YT_VIEWER_ALERT_COOLDOWN
                if sustained >= YT_VIEWER_ALERT_MIN and (not alerted_in_run or sustained > peak_viewers) and cooldown_ok:
                    alerted_in_run = True
                    peak_viewers = max(peak_viewers, sustained)
                    last_viewer_alert = now
                    dwell_elapsed = int(round(poll_ts - dwell_window[0][0]))
                    alert_msg = (
                        f"{viewers} watching now (sustained >={dwell_elapsed}s, min={YT_VIEWER_ALERT_MIN}) — "
                        f"{state['title']}"
                    )
                    print(f"👀 [VIEWER] {alert_msg}", flush=True)
                    spoken_v = SPOKEN_ALERT_TABLE["viewers_threshold"].format(
                        count=viewers, min_viewers=YT_VIEWER_ALERT_MIN
                    )
                    _play_local_ding(ding, spoken_text=spoken_v)
                    if resolved_topic:
                        send_ntfy_notification(
                            alert_msg,
                            title="👀 Honeybot Live Viewer",
                            priority="default",
                            tags="eyes",
                            topic=resolved_topic,
                        )
            else:
                if dwell_window and not alerted_in_run and YT_VIEWER_ALERT_DWELL > 0:
                    dwell_elapsed = int(round(poll_ts - dwell_window[0][0]))
                    print(
                        f"💨 [VIEWER DWELL] Dropped to {viewers} after {dwell_elapsed}s "
                        f"(<{YT_VIEWER_ALERT_DWELL}s dwell) — notification suppressed.",
                        flush=True,
                    )
                dwell_window.clear()
                alerted_in_run = False
                weebo_peak_viewers = 0
            for msg in state["chat_messages"]:
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])
                if _is_self_chat_author(msg["author"], state.get("author")):
                    continue
                chat_line = f"{msg['author']}: {msg['text']}"
                print(f"💬 [CHAT] {chat_line}", flush=True)
                print(f"   ↳ Reply on-air: ytsay \"Hey {msg['author']}, thanks for tuning in!\"", flush=True)
                _play_local_ding(
                    ding,
                    spoken_text=SPOKEN_ALERT_TABLE["live_comment"].format(author=msg["author"]),
                )
                if resolved_topic:
                    send_ntfy_notification(
                        chat_line,
                        title="💬 Honeybot Live Chat",
                        priority="high",
                        tags="speech_balloon",
                        topic=resolved_topic,
                    )
            cur_comments = state["comment_count"]
            if prev_comments is not None and cur_comments is not None and cur_comments > prev_comments:
                diff = cur_comments - prev_comments
                c_msg = f"+{diff} new comment(s) on {state['title']} (total: {cur_comments})"
                print(f"📝 [COMMENT] {c_msg}", flush=True)
                _play_local_ding(
                    ding,
                    spoken_text=SPOKEN_ALERT_TABLE["live_comment"].format(author="a viewer"),
                )
                if resolved_topic:
                    send_ntfy_notification(
                        c_msg,
                        title="📝 Honeybot Video Comment",
                        priority="high",
                        tags="memo",
                        topic=resolved_topic,
                    )
            prev_comments = cur_comments
            try:
                last_ref_ts = int(persisted.get("last_referral_ts") or int(now))
                ref_res = subprocess.run(
                    ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", HONEYBOT_SSH_HOST, "tail -n 20 /tmp/honeybot_referrals.jsonl 2>/dev/null"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                max_ref_ts = last_ref_ts
                for rline in (ref_res.stdout or "").splitlines():
                    try:
                        robj = json.loads(rline)
                    except Exception:
                        continue
                    rts = int(robj.get("ts") or 0)
                    rsrc = str(robj.get("src") or "")
                    rpath = str(robj.get("path") or "/")
                    if rts > last_ref_ts and rsrc in SPOKEN_ALERT_TABLE:
                        max_ref_ts = max(max_ref_ts, rts)
                        ref_msg = f"Inbound click ({rsrc}) -> {rpath}"
                        print(f"🔗 [REFERRAL] {ref_msg}", flush=True)
                        _play_local_ding(ding, spoken_text=SPOKEN_ALERT_TABLE[rsrc])
                        if resolved_topic:
                            send_ntfy_notification(
                                ref_msg,
                                title="🔗 Inbound Social Referral",
                                priority="high",
                                tags="link",
                                topic=resolved_topic,
                            )
                persisted["last_referral_ts"] = max_ref_ts
            except Exception:
                pass
            _save_ytwatch_state({
                "video_id": state["video_id"],
                "concurrent_viewers": viewers,
                "peak_viewers": peak_viewers,
                "weebo_peak_viewers": weebo_peak_viewers,
                "alerted_in_run": alerted_in_run,
                "comment_count": cur_comments,
                "last_viewer_alert": last_viewer_alert,
                "seen_ids": list(seen_ids)[-500:],
                "updated_at": int(now),
            })
    except KeyboardInterrupt:
        print("\n🛑 Stopped YouTube Watch.")
        return 0


def _parse_yt_view_count(raw_str):
    """Parse view count strings like '1,420 views', '678', or '1.2K views' into an integer."""
    s = (raw_str or "").strip().upper().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*([KMB])?", s)
    if not m:
        return 0
    val = float(m.group(1))
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(m.group(2) or "", 1)
    return int(round(val * mult))


def fetch_youtube_top_videos(channel_or_url=None, limit=12, dry_run=False):
    """Keyless HitTail-style leaderboard of top-performing YouTube videos & live streams."""
    import urllib.request
    raw_ch = (channel_or_url or _get_vault_var("PIPULATE_YT_CHANNEL") or "@MikeLevin").strip()
    if raw_ch.startswith(("http://", "https://")):
        base_ch = raw_ch.rstrip("/")
        for suffix in ("/live", "/streams", "/videos"):
            if base_ch.endswith(suffix):
                base_ch = base_ch[: -len(suffix)]
    elif raw_ch.startswith("@"):
        base_ch = f"https://www.youtube.com/{raw_ch}"
    else:
        base_ch = f"https://www.youtube.com/@{raw_ch}"
    if dry_run:
        sample = 'var ytInitialData = {"contents":{"videoRenderer":{"videoId":"abc12345678","title":{"runs":[{"text":"Max Headroom Test"}]},"viewCountText":{"simpleText":"1,420 views"}}}};'
        parsed = _extract_yt_json(sample, "ytInitialData =")
        found = [d for d in _walk_dicts(parsed) if "videoRenderer" in d]
        ok = len(found) == 1
        print(f"📊 [DRY RUN] YouTube Top Videos Radar: base={base_ch} | parser_ok={ok}")
        return 0 if ok else 1
    seen = {}
    for tab in ("streams", "videos"):
        tab_url = f"{base_ch}/{tab}"
        req = urllib.request.Request(
            tab_url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html_text = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"⚠️ Could not fetch {tab_url}: {exc}")
            continue
        initial = _extract_yt_json(html_text, "ytInitialData =")
        for d in _walk_dicts(initial):
            vr = d.get("videoRenderer")
            if isinstance(vr, dict):
                vid = str(vr.get("videoId") or "")
                if not vid or vid in seen:
                    continue
                t_obj = vr.get("title") or {}
                title = str(t_obj.get("simpleText") or "")
                if not title and isinstance(t_obj.get("runs"), list):
                    title = "".join(str(r.get("text") or "") for r in t_obj["runs"] if isinstance(r, dict))
                vc_obj = vr.get("viewCountText") or {}
                vc_raw = str(vc_obj.get("simpleText") or "")
                if not vc_raw and isinstance(vc_obj.get("runs"), list):
                    vc_raw = "".join(str(r.get("text") or "") for r in vc_obj["runs"] if isinstance(r, dict))
                digits = re.sub(r"[^\d]", "", vc_raw)
                views = int(digits) if digits else 0
                pub_raw = str((vr.get("publishedTimeText") or {}).get("simpleText") or "LIVE/Recent")
                len_raw = str((vr.get("lengthText") or {}).get("simpleText") or "LIVE")
                seen[vid] = {
                    "video_id": vid,
                    "kind": "STREAM" if tab == "streams" else "VIDEO",
                    "views": views,
                    "views_raw": vc_raw or "0 views",
                    "age": pub_raw,
                    "length": len_raw,
                    "title": title.strip(),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                }
                continue
            lvm = d.get("lockupViewModel")
            if isinstance(lvm, dict):
                vid = str(lvm.get("contentId") or "")
                if not vid or not re.match(r"^[A-Za-z0-9_-]{11}$", vid) or vid in seen:
                    continue
                meta = ((lvm.get("metadata") or {}).get("lockupMetadataViewModel")) or {}
                title = str((meta.get("title") or {}).get("content") or "").strip()
                if not title:
                    continue
                rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel")) or {}).get("metadataRows") or []
                parts_text = []
                for row in rows:
                    if isinstance(row, dict):
                        for part in row.get("metadataParts") or []:
                            if isinstance(part, dict):
                                txt = str((part.get("text") or {}).get("content") or "").strip()
                                if txt:
                                    parts_text.append(txt)
                vc_raw = next(
                    (
                        p for p in parts_text
                        if "view" in p.lower()
                        or "watching" in p.lower()
                        or re.match(r"^\d[\d,\.]*\s*[KMBkmb]?$", p)
                    ),
                    "",
                )
                pub_raw = next((p for p in parts_text if p != vc_raw), "VOD")
                views = _parse_yt_view_count(vc_raw)
                len_raw = "LIVE"
                for sub in _walk_dicts(lvm.get("contentImage") or {}):
                    tb = sub.get("thumbnailBadgeViewModel")
                    if isinstance(tb, dict) and tb.get("text"):
                        len_raw = str(tb.get("text")).strip()
                        break
                seen[vid] = {
                    "video_id": vid,
                    "kind": "STREAM" if tab == "streams" else "VIDEO",
                    "views": views,
                    "views_raw": vc_raw or "0 views",
                    "age": pub_raw,
                    "length": len_raw,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                }
    ranked = sorted(seen.values(), key=lambda x: x["views"], reverse=True)[: max(1, int(limit))]
    print(f"📊 YouTube Title & Topic Radar ({base_ch} — Top {len(ranked)} of {len(seen)} sampled):")
    for idx, item in enumerate(ranked, 1):
        print(
            f"  {idx:2d}. [{item['views']:5d} views] ({item['kind']:6s} | {item['length']:>8s} | {item['age']}) "
            f"{item['title']} -> {item['url']}"
        )
    return 0


def _load_standby_speech_from_stream():
    """Extract (STANDBY_INTRO_LINE, STANDBY_LOOP_LINES, stream_path) from remotes/honeybot/scripts/stream.py."""
    import ast
    repo_root = Path(__file__).resolve().parents[2]
    stream_path = repo_root / "remotes" / "honeybot" / "scripts" / "stream.py"
    intro = "Receiving updates. This broadcast is coming to an end."
    loop_lines = ()
    if stream_path.is_file():
        try:
            tree = ast.parse(stream_path.read_text(encoding="utf-8"))
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
    return intro, loop_lines, stream_path


def reboot_honeybot_stream(sync_only=False, dry_run=False):
    """Sync remotes/honeybot/scripts/ to Honeybot and optionally restart stream.py."""
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    scripts_src = f"{repo_root}/remotes/honeybot/scripts/"
    if dry_run:
        mode_lbl = "sync-only" if sync_only else "sync + restart stream.py"
        print(f"🔄 [DRY RUN] Honeybot Stream Reboot ({mode_lbl}): rsync {scripts_src} -> {HONEYBOT_SSH_HOST}:~/www/mikelev.in/scripts/")
        return 0
    print(f"🚀 Syncing Honeybot scripts to {HONEYBOT_SSH_HOST}:~/www/mikelev.in/scripts/...")
    sync_res = subprocess.run(
        ["rsync", "--delete", "-av", scripts_src, f"{HONEYBOT_SSH_HOST}:~/www/mikelev.in/scripts/"],
        check=False,
    )
    if sync_res.returncode != 0:
        print(f"❌ rsync failed (exit {sync_res.returncode}).")
        return sync_res.returncode
    subprocess.run(
        ["rsync", "-aq", f"{repo_root}/imports/ascii_displays.py", f"{HONEYBOT_SSH_HOST}:~/www/mikelev.in/imports/"],
        check=False,
    )
    subprocess.run(
        ["rsync", "-aq", f"{repo_root}/assets/sounds/tick.wav", f"{HONEYBOT_SSH_HOST}:~/www/mikelev.in/assets/sounds/tick.wav"],
        check=False,
    )
    if sync_only:
        print("✅ Honeybot scripts synced (stream.py left running; new standby text will load on next .deploy_standby).")
        return 0
    print(f"🔄 Restarting Honeybot stream.py child on {HONEYBOT_SSH_HOST}...")
    remote_sh = r"""
pattern="/home/mike/www/mikelev[.]in/scripts/stream[.]py"
old_pids=$(pgrep -f -- "$pattern" || true)
for old in $old_pids; do
    echo "   stopping old stream.py pid=$old"
    kill -TERM "$old" 2>/dev/null || true
done
sleep 1
for old in $old_pids; do
    if kill -0 "$old" 2>/dev/null; then
        echo "   force-killing stubborn stream.py pid=$old"
        kill -KILL "$old" 2>/dev/null || true
    fi
done
pkill -9 -f "aplay.*22050|honeybot_tts|piper.*output_raw" 2>/dev/null || true
rm -f /tmp/honeybot_tts_*.raw 2>/dev/null || true
pkill -f "/home/mike/www/mikelev[.]in/scripts/logs[.]py" 2>/dev/null || true
pkill -f "tail -f /var/log/nginx/access[.]log" 2>/dev/null || true
for i in $(seq 1 14); do
    sleep 1
    cand_pids=$(pgrep -f -- "$pattern" || true)
    fresh_pids=""
    for cp in $cand_pids; do
        is_old=0
        for op in $old_pids; do
            if [ "$cp" = "$op" ]; then
                is_old=1
                break
            fi
        done
        if [ "$is_old" -eq 0 ]; then
            fresh_pids="$fresh_pids $cp"
        fi
    done
    fresh_pids=$(echo "$fresh_pids" | sed 's/^ *//;s/ *$//')
    if [ -n "$fresh_pids" ]; then
        echo "✅ Stream watchdog relaunched fresh stream.py (pid=${fresh_pids} after ${i}s)."
        exit 0
    fi
done
echo "⚠️ No new stream.py PID seen within 14s; verify the stream watchdog on Honeybot."
exit 1
"""
    res = subprocess.run(["ssh", HONEYBOT_SSH_HOST, "sh", "-s"], input=remote_sh, text=True)
    return res.returncode


def run_honeybot_outro(action="play", tick=True, dry_run=False):
    """Audition, edit, sync, or reboot the Honeybot deploy-standby outro speech on Pipulate Prime."""
    import os
    import shutil
    import signal
    import subprocess
    act = (action or "play").strip().lower()
    intro, loop_lines, stream_path = _load_standby_speech_from_stream()
    if act in ("edit", "vim", "nvim"):
        editor = shutil.which("nvim") or shutil.which("vim") or "vi"
        if dry_run:
            print(f"✏️  [DRY RUN] {editor} +/STANDBY_LOOP_LINES {stream_path}")
            return 0
        subprocess.run([editor, "+/STANDBY_LOOP_LINES", str(stream_path)])
        print("💡 Audition locally: ytoutro  |  Sync without restart: ytoutro sync  |  Sync + restart stream: ytreboot")
        return 0
    if act in ("sync", "push"):
        return reboot_honeybot_stream(sync_only=True, dry_run=dry_run)
    if act in ("reboot", "restart"):
        return reboot_honeybot_stream(sync_only=False, dry_run=dry_run)
    all_lines = [intro, *loop_lines]
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"🎙️  HONEYBOT DEPLOY-STANDBY OUTRO ({stream_path})")
    print("-" * 72)
    print(f"  [Intro] {intro}")
    for idx, ln in enumerate(loop_lines, 1):
        print(f"  [{idx}/{len(loop_lines)}]   {ln}")
    print("-" * 72)
    print("🎛️  Subcommands: ytoutro (play) | ytoutro --no-tick | ytoutro show | ytoutro edit | ytoutro sync | ytreboot")
    print(bar)
    if dry_run or act in ("show", "text", "print"):
        if dry_run:
            print(f"🗣️  [DRY RUN] Outro audition ready ({len(all_lines)} spoken segments, tick={tick}).")
        return 0
    repo_root = Path(__file__).resolve().parents[2]
    piper_bin = str(repo_root / ".venv/bin/piper")
    if not Path(piper_bin).is_file():
        piper_bin = shutil.which("piper") or ""
    model_path = _ensure_local_piper_model()
    if not piper_bin or not model_path:
        print("⚠️ Local Piper TTS model or binary not found; printed text only.")
        return 1
    play_cmds = (["pw-play"], ["paplay"], ["aplay", "-q"], ["afplay"])
    player_base = next((c for c in play_cmds if shutil.which(c[0])), None)
    if not player_base:
        print("⚠️ No local audio player (pw-play/paplay/aplay/afplay) found.")
        return 1
    tick_proc = None
    active_proc = None
    wav_path = Path(f"/tmp/pipulate_outro_{os.getpid()}.wav")
    tick_file = repo_root / "assets" / "sounds" / "tick.wav"
    print("🔊 Playing standby outro locally on Pipulate Prime (press Ctrl+C to stop)...")
    try:
        if tick and tick_file.is_file():
            tick_cmd_str = " ".join([*player_base, f'"{tick_file}"'])
            tick_proc = subprocess.Popen(
                ["sh", "-c", f"while :; do {tick_cmd_str} >/dev/null 2>&1; sleep 1; done"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        for seg in all_lines:
            subprocess.run(
                [piper_bin, "--model", str(model_path), "--output_file", str(wav_path)],
                input=seg.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if wav_path.is_file():
                active_proc = subprocess.Popen(
                    [*player_base, str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                active_proc.wait()
                active_proc = None
        print("✅ Outro audition complete.")
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Stopped local outro playback.")
        return 0
    finally:
        if active_proc and active_proc.poll() is None:
            try:
                active_proc.kill()
            except Exception:
                pass
        if tick_proc is not None:
            try:
                os.killpg(os.getpgid(tick_proc.pid), signal.SIGKILL)
            except Exception:
                pass
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipulate article common utilities & broadcast kit.")
    add_standard_arguments(parser)
    parser.add_argument(
        "--broadcast",
        choices=("help", "card", "hero", "yaml", "tweet", "linkedin", "pebble", "title", "desc", "top", "outro", "reboot", "status", "bell", "stop", "start", "roll", "enable-ws", "say", "ping", "watch"),
        default="card",
        help="Print/copy broadcast kit or control Honeybot (help|card|hero|yaml|tweet|linkedin|pebble|title|desc|top|outro|reboot|status|bell|stop|start|roll|enable-ws|say|ping|watch).",
    )
    parser.add_argument(
        "--no-tick",
        action="store_true",
        help="Disable background tick.wav clock loop during local `ytoutro` audition.",
    )
    parser.add_argument(
        "-s", "--slug",
        type=str,
        default=None,
        help="Optional substring to match a specific dated post filename.",
    )
    parser.add_argument(
        "-c", "--card",
        type=str,
        default=None,
        help="Figlet card label for --broadcast say (use \\n for multiple lines; default: LIVE\\nFROM MIKE).",
    )
    parser.add_argument(
        "-p", "--patronus",
        type=str,
        default=None,
        help="Optional figurate ASCII art key (e.g. white_rabbit) for --broadcast say.",
    )
    parser.add_argument(
        "-m", "--media",
        type=str,
        default=None,
        help="Optional image/video path or URL (e.g. /assets/images/slug.jpeg) for --broadcast say.",
    )
    parser.add_argument(
        "-w", "--window",
        type=str,
        default=None,
        help="Optional TUI window spec (e.g. forest.py:30:bimodal) for --broadcast say.",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        help="Read the spoken message from the OS clipboard for --broadcast say.",
    )
    parser.add_argument(
        "--pre",
        type=float,
        default=3.0,
        help="Seconds of pre-banner silence after cutting article audio (default: 3.0).",
    )
    parser.add_argument(
        "--linger",
        type=float,
        default=2.5,
        help="Seconds the banner hovers silently after speech before POOF (default: 2.5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload / verify parser without network side effects.",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Mint and save a random PIPULATE_NTFY_TOPIC in ~/.config/pipulate/.env if unset.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Override PIPULATE_NTFY_TOPIC for --broadcast ping/watch.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Honeybot Live",
        help="Notification title for --broadcast ping (default: 'Honeybot Live').",
    )
    parser.add_argument(
        "--priority",
        type=str,
        default="default",
        help="ntfy priority (min|low|default|high|urgent) for --broadcast ping.",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="YouTube channel URL/handle or video ID for --broadcast watch (saves PIPULATE_YT_CHANNEL).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously poll YouTube Live in --broadcast watch and push ntfy alerts.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Poll interval in seconds when --loop is active (default: 30).",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send ntfy push on one-shot ytwatch if new chat messages arrived since last check.",
    )
    parser.add_argument(
        "--no-ding",
        action="store_true",
        help="Disable local ding.wav audio chime on new viewer/chat events.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start ytwatch --loop in a detached background tmux session ('ytwatch').",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the background 'ytwatch' tmux session.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify reciprocal Honeybot access.log and Wayback CDX receipts for --broadcast pebble.",
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="Spoken message words for say, push body for ping, or optional interval/channel for watch.",
    )
    cli_args = parser.parse_args()
    if cli_args.broadcast == "say":
        msg_text = _read_from_clipboard() if cli_args.clip else " ".join(cli_args.message)
        sys.exit(
            send_honeybot_live_message(
                msg_text,
                card_label=cli_args.card,
                patronus_key=cli_args.patronus,
                media_path=cli_args.media,
                window_spec=cli_args.window,
                pre_pause=cli_args.pre,
                linger=cli_args.linger,
                dry_run=cli_args.dry_run,
            )
        )
    if cli_args.broadcast == "ping":
        msg_text = _read_from_clipboard() if cli_args.clip else " ".join(cli_args.message)
        spoken_key = next((k for k in SPOKEN_ALERT_TABLE if k in (msg_text or "").lower()), "default")
        spoken_line = (
            SPOKEN_ALERT_TABLE[spoken_key].format(
                count=YT_VIEWER_ALERT_MIN,
                min_viewers=YT_VIEWER_ALERT_MIN,
                author="viewer",
                message=msg_text or "Ping from Pipulate Prime",
            )
        )
        if not cli_args.dry_run:
            _play_local_ding(not cli_args.no_ding, spoken_text=spoken_line)
        else:
            print(f"🗣️  [DRY RUN] Spoken Piper TTS: {spoken_line!r}")
        sys.exit(
            send_ntfy_notification(
                msg_text,
                title=cli_args.title,
                priority=cli_args.priority,
                topic=cli_args.topic,
                init_topic=cli_args.init,
                dry_run=cli_args.dry_run,
            )
        )
    if cli_args.broadcast == "watch":
        watch_channel = cli_args.channel
        watch_loop = cli_args.loop
        watch_interval = cli_args.interval
        daemon_act = "stop" if cli_args.stop else ("daemon" if cli_args.daemon else None)
        if cli_args.message:
            first_arg = cli_args.message[0].strip().lower()
            if first_arg in ("daemon", "start", "restart"):
                daemon_act = "daemon"
            elif first_arg in ("stop", "kill"):
                daemon_act = "stop"
            elif first_arg == "status":
                daemon_act = "status"
            elif first_arg in ("attach", "log", "logs", "tail", "tmux"):
                daemon_act = "attach"
            elif first_arg.isdigit():
                watch_interval = int(first_arg)
                watch_loop = True
            elif not watch_channel:
                watch_channel = cli_args.message[0].strip()
        sys.exit(
            run_youtube_watch(
                channel=watch_channel,
                loop=watch_loop,
                interval=watch_interval,
                topic=cli_args.topic,
                init_topic=cli_args.init,
                notify_once=cli_args.notify,
                ding=not cli_args.no_ding,
                daemon_action=daemon_act,
                dry_run=cli_args.dry_run,
            )
        )
    if cli_args.broadcast == "top":
        top_limit = int(cli_args.message[0]) if (cli_args.message and cli_args.message[0].isdigit()) else 12
        sys.exit(fetch_youtube_top_videos(channel_or_url=cli_args.channel, limit=top_limit, dry_run=cli_args.dry_run))
    if cli_args.broadcast == "pebble":
        first_pebble_arg = cli_args.message[0].strip().lower() if cli_args.message else ""
        if cli_args.verify or first_pebble_arg in ("verify", "check", "status"):
            sys.exit(verify_pebble_receipts(cli_args.target, slug_match=cli_args.slug))
        sys.exit(drop_pebble_pings(cli_args.target, slug_match=cli_args.slug, dry_run=cli_args.dry_run))
    if cli_args.broadcast == "reboot":
        sys.exit(reboot_honeybot_stream(sync_only=False, dry_run=cli_args.dry_run))
    if cli_args.broadcast == "outro":
        outro_act = cli_args.message[0].strip().lower() if cli_args.message else "play"
        use_tick = not (cli_args.no_tick or cli_args.no_ding or outro_act in ("voice", "notick"))
        if outro_act in ("voice", "notick"):
            outro_act = "play"
        sys.exit(run_honeybot_outro(action=outro_act, tick=use_tick, dry_run=cli_args.dry_run))
    if cli_args.broadcast in ("status", "bell", "stop", "start", "roll", "enable-ws"):
        sys.exit(run_honeybot_obs(cli_args.broadcast))
    sys.exit(print_broadcast_kit(cli_args.target, cli_args.broadcast, slug_match=cli_args.slug))
