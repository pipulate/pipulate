import os
import re
import sys
import time
import yaml
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Path to your Jekyll posts on the Honeybot
POSTS_DIR = Path("/home/mike/www/mikelev.in/_posts")
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

def check_for_updates():
    """
    Checks if the _posts directory has changed since the last playlist generation.
    Returns True if updates are detected.
    """
    global _last_scan_time, _last_file_count, _last_trigger
    
    try:
        # Get directory stats
        stat = POSTS_DIR.stat()
        current_mtime = stat.st_mtime
        
        # Also check file count (sometimes mtime on dir doesn't update on all FS)
        current_files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
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


def get_playlist(recent_n=10, include_archive=True):
    """
    Returns a playlist: Recent N (sorted date desc + sort_order desc) + optional Rest (shuffled).
    When include_archive=False, stops scanning older dates once recent_n articles are loaded.
    """
    all_articles = []
    
    try:
        # Find all markdown files, newest date prefixes first so include_archive=False
        # can stop scanning once the newest N articles (and same-day siblings) are read.
        files = sorted(
            list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown")),
            key=lambda p: p.name,
            reverse=True,
        )
        cutoff_date = None
        
        for filepath in files:
            filename = filepath.name
            
            # 1. Extract Date
            try:
                date_str = filename[:10]
                post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue 

            if not include_archive and cutoff_date is not None and post_date < cutoff_date:
                break
            # 2. Read File & Frontmatter
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read()

            frontmatter = {}
            body_text = raw_text
            
            if raw_text.startswith('---'):
                try:
                    parts = raw_text.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        body_text = parts[2]
                except yaml.YAMLError:
                    pass

            # 3. Extract Sort Order (Default to 0)
            try:
                sort_order = int(frontmatter.get('sort_order', 0))
            except (ValueError, TypeError):
                sort_order = 0

            # 4. Construct URL
            slug = frontmatter.get('permalink', '').strip('/')
            if not slug:
                slug = filename[11:].rsplit('.', 1)[0]
            url = f"{BASE_URL}/{slug}/"
            
            # 5. Clean Text
            # 7 days is one publishing week at current velocity (24 posts in the
            # last 7 days, per the STATS gauge), so the on-air census covers
            # roughly the newest two dozen articles -- the ones being watched --
            # and stays silent over the 1300-post archive. One number to tune.
            clean_text = clean_markdown(
                body_text,
                label=filename,
                census=include_archive and (datetime.now().date() - post_date).days <= 7,
            )
            
            all_articles.append({
                'date': post_date,
                'sort_order': sort_order, # Added for secondary sort key
                'title': frontmatter.get('title', slug.replace('-', ' ')),
                'url': url,
                'content': clean_text
            })
            if not include_archive and len(all_articles) >= recent_n and cutoff_date is None:
                cutoff_date = post_date

        # Sort ALL by date first, then by sort_order (both Descending/Reverse)
        # Tuple comparison works element by element: (2026-01-01, 2) > (2026-01-01, 1)
        all_articles.sort(key=lambda x: (x['date'], x['sort_order']), reverse=True)
        
        # Split the lists
        recent_articles = all_articles[:recent_n]
        archive_articles = all_articles[recent_n:]
        
        # Shuffle the archive to keep it fresh
        random.shuffle(archive_articles)
        
        global _last_scan_time, _last_file_count, _last_trigger
        try:
            stat = POSTS_DIR.stat()
            _last_scan_time = stat.st_mtime
            files = list(POSTS_DIR.glob("*.md")) + list(POSTS_DIR.glob("*.markdown"))
            _last_file_count = len(files)
            try:
                _last_trigger = TRIGGER_FILE.read_text().strip()
            except FileNotFoundError:
                _last_trigger = None
        except: pass
        
        if not include_archive:
            return recent_articles
        return recent_articles + archive_articles

    except Exception as e:
        print(f"Librarian Error: {e}", file=sys.stderr)
        return []

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

    # Strip fenced code blocks and disarm backticked inline-code examples
    # (e.g. `[[[weebo:name:seconds]]]` or `<!-- weebo: name -->` in prose)
    # BEFORE capturing live player-piano cues so documentation never fires as a cue.
    CODE_SENTINEL = '\x00CODEBLOCK\x00'
    text = re.sub(r'```.*?```', f' {CODE_SENTINEL} ', text, flags=re.DOTALL)
    text = re.sub(
        r'`([^`\n]+)`',
        lambda m: '`' + re.sub(r'\[{2,}|\]{2,}|<!--|-->', '', m.group(1)) + '`'
        if ('[[' in m.group(1) or '<!--' in m.group(1))
        else m.group(0),
        text,
    )
    # Capture both HTML comments (<!-- pp4: ... --> / <!-- weebo: ... -->) and
    # triple-bracket player-piano cues ([[[weebo:ambigram:6]]]) before stripping.
    text = re.sub(r'<!--\s*(pp4|weebo|media)\b(?::|\s)?(.*?)-->', capture_pp4_comment, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\[{3}\s*(weebo|media|image|video|patronus)\s*:\s*([^\]\s]+)\s*\]{3}', capture_inline_bracket_cue, text, flags=re.IGNORECASE)

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
    text = text.replace(CODE_SENTINEL, 'See the code at MikeLev dot Eye N slash latest.')
    # Global cap: no article should repeat this more than once.
    spoken = 'See the code at MikeLev dot Eye N slash latest.'
    if text.count(spoken) > 1:
        idx = text.index(spoken)
        text = text[:idx + len(spoken)] + text[idx + len(spoken):].replace(spoken, '')

    # Remove Inline Code
    text = re.sub(r'`([^`]+)`', r'\1', text)
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

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove Headers/Bold/Italic markers
    text = re.sub(r'[*_#]', '', text)

    # Reflow Logic (The Hard Wrap Fix)
    text = re.sub(r'\n\s*\n', '||PARAGRAPH||', text)
    text = re.sub(r'\n', ' ', text)
    text = text.replace('||PARAGRAPH||', '\n')
    text = re.sub(r' +', ' ', text).strip()

    for index, item in enumerate(pp4_directives):
        cue_kind, asset_name, duration = item if len(item) == 3 else ("PATRONUS", item[0], item[1])
        text = text.replace(f"PP4PATRONUS{index}PP4", f"\n[[{cue_kind}:{asset_name}:{duration}]]\n")
    
    return text
