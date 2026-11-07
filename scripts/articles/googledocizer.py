#!/usr/bin/env python3
# scripts/articles/googledocizer.py
"""
googledocizer.py -- The Idempotent Google Docs Publishing Adapter.

A WET fork of confluenceizer.py aimed at Google Drive/Docs. Same contract:
read local Jekyll markdown, compute a deterministic Target Title, scan ONE
Drive folder for existing children, then CREATE or UPDATE native Google Docs
via Drive's import-on-upload HTML conversion. No hand-batched Docs API
updateTextStyle requests, and (unlike Confluence) no version-number
bookkeeping: files().update() replaces content in place and Drive's own
revision history tracks the diff.

MODES
  Publish (default): dry-run contract; add --yes to arm mutations.
      python googledocizer.py -t 1                       # full sweep, dry run
      python googledocizer.py -t 1 --yes --latest        # only the last-articleized post
      python googledocizer.py -t 1 --yes --file 2026-07-05-some-post.md
  Fetch (the Prompt Fu read path, mirroring gmail.py's positional dispatch):
      python googledocizer.py FILE_ID                    # Doc -> markdown, Sheet -> csv, stdout
  List the folder inventory:
      python googledocizer.py -t 1 --list
  Bootstrap the folder once (prints the ID to paste into blogs.nix):
      python googledocizer.py --bootstrap-folder "MikeLev.in Articles"
  CSV -> native Google Sheet (same conversion trick, different mimetype pair):
      python googledocizer.py -t 1 --yes --csv data.csv

AUTH (the ~/repos/nixos wallet convention -- composite filenames, one flat dir)
  App identity:  ~/repos/nixos/credentials/pipulate_credentials.json
                 (override: PIPULATE_GDRIVE_CREDENTIALS)
  User session:  ~/repos/nixos/credentials/pipulate_gdrive_token.json
                 (override: PIPULATE_GDRIVE_TOKEN)
  Scope is full Drive because the fetch path must read arbitrary Docs/Sheets
  shared to the Pipulate account, not only app-created files; drive.file
  would silently hide a hand-made folder or a shared doc. The first run must
  be INTERACTIVE (real terminal) to mint the token via the browser loopback
  flow; after that, headless refresh is silent, exactly like scripts/gmail.py.
  Nothing here is ever read by Nix evaluation, so nothing lands in /nix/store.

CONFIG
  blogs.json target entries gain "gdrive_folder_id" (materialized from
  ~/repos/nixos/blogs.nix). Empty or missing means the feature is off for
  that target. --folder ID overrides for probing before committing to Nix.
"""

import os
import re
import sys
import json
import time
import argparse
from html import escape as html_escape
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Comment
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import common

try:
    import markdown as md_lib
except ImportError:
    md_lib = None

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

SCOPES = ['https://www.googleapis.com/auth/drive']

WALLET_DIR = Path.home() / 'repos' / 'nixos' / 'credentials'
CREDS_PATH = os.environ.get('PIPULATE_GDRIVE_CREDENTIALS') or str(
    WALLET_DIR / 'pipulate_credentials.json'
)
TOKEN_PATH = os.environ.get('PIPULATE_GDRIVE_TOKEN') or str(
    WALLET_DIR / 'pipulate_gdrive_token.json'
)

DOC_MIME = 'application/vnd.google-apps.document'
SHEET_MIME = 'application/vnd.google-apps.spreadsheet'
FOLDER_MIME = 'application/vnd.google-apps.folder'


# ----------------------------------------------------------------------------
# Authentication (forked from scripts/gmail.py; different scope => own token)
# ----------------------------------------------------------------------------
def _save_token(creds):
    token_path = Path(TOKEN_PATH)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())


def get_service():
    """Return an authenticated Drive v3 service, minting/refreshing tokens as needed."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (json.JSONDecodeError, ValueError):
            creds = None

    if creds and creds.valid:
        return build('drive', 'v3', credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return build('drive', 'v3', credentials=creds)
        except Exception:
            creds = None

    if not sys.stdout.isatty():
        sys.stderr.write(
            "Google Drive auth needs a one-time interactive login.\n"
            "Run this directly in your terminal first to mint the token:\n"
            "    python scripts/articles/googledocizer.py --bootstrap-folder \"MikeLev.in Articles\"\n"
        )
        sys.exit(1)

    if not os.path.exists(CREDS_PATH):
        sys.stderr.write(
            f"Missing OAuth client JSON at: {CREDS_PATH}\n"
            "Export a Desktop-app OAuth client from the Pipulate GCP project\n"
            "(with the Drive API enabled) and save it to that path.\n"
        )
        sys.exit(1)

    print("Opening local browser window for Google Drive OAuth negotiation...",
          file=sys.stderr)
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return build('drive', 'v3', credentials=creds)


# ----------------------------------------------------------------------------
# Markdown preparation (forked from confluenceizer.py, minus md2conf)
# ----------------------------------------------------------------------------
def _sanitize_internal_pii(text: str) -> str:
    """Map pseudo-private client/colleague identities to roles out-of-band."""
    if not text:
        return text
    rules = []
    txt_file = Path.home() / ".config" / "pipulate" / "pii_substitutions.txt"
    if txt_file.exists():
        for line in txt_file.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if " === " in line:
                pattern, repl = line.split(" === ", 1)
                rules.append((pattern, repl))
    for pattern, replacement in rules:
        text = re.sub(pattern, replacement, text)
    return text


_INLINE_CODE_RE = re.compile(r'(?<!\\)(`+)(.+?)(?<!`)\1(?!`)')
_FENCE_OPEN_RE = re.compile(r'^(`{3,}|~{3,})(.*)$')
_SAFE_INLINE_TAG_RE = re.compile(r'^<(?:sup|sub|/sup|/sub|br|br\s*/)>$', re.IGNORECASE)
_ANY_ANGLE_RE = re.compile(r'<[^<>]*>')
_ALLOWED_GDRIVE_TAGS = frozenset({
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'ul', 'ol', 'li',
    'blockquote', 'pre', 'code', 'strong', 'b', 'em', 'i', 'a', 'hr', 'br',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sup', 'sub',
})
_TIER3_GDRIVE_TAGS = frozenset({'h1', 'h2', 'h3', 'h4', 'p', 'pre', 'br', 'hr'})
_DROP_CONTENT_TAGS = (
    'script', 'style', 'svg', 'iframe', 'object', 'embed',
    'form', 'input', 'button', 'select', 'textarea', 'meta', 'link', 'head', 'title',
)


def _escape_prose_angles(segment: str) -> str:
    """Escape < and > in plain prose except simple <sup>/<sub>/<br> tags."""
    def _repl(match):
        tok = match.group(0)
        if _SAFE_INLINE_TAG_RE.match(tok):
            return tok
        return html_escape(tok, quote=False)

    out = _ANY_ANGLE_RE.sub(_repl, segment)
    # Also escape any stray unclosed < or > outside balanced <...>
    parts = re.split(r'(</?(?:sup|sub|br)\b[^<>]*>)', out, flags=re.IGNORECASE)
    cleaned = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            cleaned.append(part)
        else:
            cleaned.append(part.replace('<', '&lt;').replace('>', '&gt;'))
    return ''.join(cleaned)


def _escape_prose_line(line: str) -> str:
    """Preserve leading blockquote '>' markers and inline code spans while escaping prose <...>."""
    bq_match = re.match(r'^(\s*>+\s?)', line)
    prefix = bq_match.group(1) if bq_match else ''
    rest = line[len(prefix):]
    out = []
    last = 0
    for m in _INLINE_CODE_RE.finditer(rest):
        out.append(_escape_prose_angles(rest[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(_escape_prose_angles(rest[last:]))
    return prefix + ''.join(out)


def _is_valid_gdrive_href(href: str) -> bool:
    """True when href is a clean absolute HTTP(S) URL that Google Drive's importer accepts."""
    if not href or len(href) > 2000 or any(c in href for c in ' \t\r\n<>"\'{}|\\^`'):
        return False
    try:
        parts = urlsplit(href)
    except ValueError:
        return False
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return False
    return bool(re.match(r'^[A-Za-z0-9.-]+(?::\d+)?$', parts.netloc))


def _prepare_markdown(md_text: str, canonical_url: str = "", tier: int = 1) -> str:
    """Strip Liquid/control chars, cap giant fenced blocks, and escape prose pseudo-tags."""
    if not md_text:
        return ""
    md_text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', md_text)
    md_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u2060\ud800-\udfff]', '', md_text)
    md_text = re.sub(r'\{%-?\s*raw\s*-?%\}\s*\n?', '', md_text)
    md_text = re.sub(r'\{%-?\s*endraw\s*-?%\}\s*\n?', '', md_text)
    md_text = re.sub(r'<!--[\s\S]*?-->', '', md_text)
    md_text = re.sub(
        r'### 🐦 X\.com Promo Tweet\n```text\n.*?\n```\n*', '', md_text, flags=re.DOTALL
    )
    md_text = re.sub(
        r'### Title Brainstorm\n.*?(?=\n### |\Z)', '', md_text, flags=re.DOTALL
    )
    md_text = _sanitize_internal_pii(md_text)
    link_target = canonical_url or "https://mikelev.in"
    max_fence_chars = 12000 if tier == 1 else (1600 if tier == 2 else 0)
    max_fence_lines = 200 if tier == 1 else (35 if tier == 2 else 0)
    out_lines = []
    in_ledger = False
    fence_char = None
    fence_len = 0
    fence_lang = ""
    fence_buf = []

    def _flush_fence():
        if tier >= 3:
            out_lines.append(
                f"\n> *[Code block omitted in compact Google Doc — full source at {link_target}]*\n"
            )
            return
        body_lines = []
        char_count = 0
        truncated = False
        for fline in fence_buf:
            safe_line = re.sub(r'`{3,}', '[triple-backtick]', fline)
            safe_line = re.sub(r'~{3,}', '[triple-tilde]', safe_line)
            if len(safe_line) > 500:
                safe_line = safe_line[:500] + " ... [line truncated]"
            if len(body_lines) >= max_fence_lines or (char_count + len(safe_line)) > max_fence_chars:
                truncated = True
                break
            body_lines.append(safe_line)
            char_count += len(safe_line) + 1
        if truncated:
            body_lines.append(
                f"... [Code block truncated for Google Docs — full source: {link_target}]"
            )
        out_lines.append(f"```{fence_lang}")
        out_lines.extend(body_lines)
        out_lines.append("```")

    for line in md_text.splitlines():
        if fence_char is not None:
            close_re = re.compile(rf'^{re.escape(fence_char)}{{{fence_len},}}[ \t]*$')
            if close_re.match(line):
                _flush_fence()
                fence_char = None
                fence_len = 0
                fence_lang = ""
                fence_buf = []
            else:
                fence_buf.append(line)
            continue
        m_open = _FENCE_OPEN_RE.match(line)
        if m_open:
            marker, tail = m_open.group(1), m_open.group(2).strip()
            fence_char = marker[0]
            fence_len = len(marker)
            fence_lang = re.sub(r'[^A-Za-z0-9_+-]', '', tail.split()[0]) if tail else "text"
            fence_buf = []
            continue
        if '<div class="commit-ledger"' in line:
            in_ledger = True
        if in_ledger:
            out_lines.append(line)
            if '</div>' in line:
                in_ledger = False
            continue
        out_lines.append(_escape_prose_line(line))

    if fence_char is not None:
        _flush_fence()
    return "\n".join(out_lines)


def markdown_to_html(
    md_text: str, headline: str = "", canonical_url: str = "", tier: int = 1
) -> bytes:
    """Markdown -> minimal HTML document, ready for Drive import-on-upload.
    `headline` is the article title, emitted as the Doc's opening <h1>. The
    title lives in YAML frontmatter, which frontmatter.load() strips from
    .content, so without this the Doc body opened on the first H2 the body
    happened to carry ("Setting the Stage: Context for the Curious Book
    Reader") while only the Drive FILENAME knew the real title. Drive's
    import maps <h1> to Heading 1, so it lands styled and in the outline.
    """
    if md_lib is None:
        raise RuntimeError(
            "The 'markdown' package is required. Add it to requirements.in "
            "and reinstall (probe: .venv/bin/python -c 'import markdown')."
        )
    exts = ['fenced_code', 'tables', 'sane_lists'] if tier == 1 else ['fenced_code', 'sane_lists']
    raw_body = md_lib.markdown(
        _prepare_markdown(md_text, canonical_url=canonical_url, tier=tier),
        extensions=exts,
    )
    body = _sanitize_html_for_gdrive(raw_body, canonical_url=canonical_url, tier=tier)
    if headline:
        body = f"<h1>{html_escape(headline)}</h1>\n{body}"
    html = f"<html><head><meta charset=\"utf-8\"></head><body>{body}</body></html>"
    return html.encode('utf-8')


def _sanitize_html_for_gdrive(raw_body: str, canonical_url: str = "", tier: int = 1) -> str:
    """Clean rendered HTML with BeautifulSoup and enforce DOM-safe byte caps for Google Drive."""
    soup = BeautifulSoup(raw_body, 'html.parser')
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for bad_tag in soup.find_all(_DROP_CONTENT_TAGS):
        bad_tag.decompose()
    for img_tag in soup.find_all('img'):
        img_tag.decompose()
    if tier >= 2:
        for tbl in soup.find_all('table'):
            for tr in tbl.find_all('tr'):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(['th', 'td'])]
                p_tag = soup.new_tag('p')
                p_tag.string = " | ".join(c for c in cells if c)
                tbl.insert_before(p_tag)
            tbl.decompose()
    allowed = _ALLOWED_GDRIVE_TAGS if tier in (1, 2) else _TIER3_GDRIVE_TAGS
    for tag in list(soup.find_all(True)):
        if tag.name not in allowed:
            if tag.name == 'li':
                tag.insert(0, "• ")
                tag.name = 'p'
                tag.attrs = {}
            else:
                tag.unwrap()
            continue
        if tag.name == 'a' and tier in (1, 2):
            href = str(tag.get('href') or '').strip()
            if href.startswith('/') and not href.startswith('//'):
                href = f"https://mikelev.in{href}"
            if _is_valid_gdrive_href(href):
                tag.attrs = {'href': href}
            else:
                tag.unwrap()
        else:
            tag.attrs = {}
    link_target = canonical_url or "https://mikelev.in"
    for blk in soup.find_all(['p', 'pre', 'li', 'blockquote']):
        txt = blk.get_text()
        if len(txt) > 14000:
            blk.clear()
            blk.string = txt[:14000] + f"\n... [Truncated — full text at {link_target}]"
    max_bytes = 220000 if tier == 1 else (100000 if tier == 2 else 45000)
    truncated_tail = False
    while len(str(soup).encode('utf-8')) > max_bytes and len(soup.contents) > 1:
        last_node = soup.contents[-1]
        last_node.extract()
        truncated_tail = True
    if truncated_tail or tier >= 2:
        hr_tag = soup.new_tag('hr')
        soup.append(hr_tag)
        note_p = soup.new_tag('p')
        if tier in (1, 2) and _is_valid_gdrive_href(link_target):
            strong = soup.new_tag('strong')
            strong.string = "📖 Read the complete article and full code receipts online: "
            a_tag = soup.new_tag('a', href=link_target)
            a_tag.string = link_target
            note_p.append(strong)
            note_p.append(a_tag)
        else:
            note_p.string = f"Read the complete article and full code receipts online: {link_target}"
        soup.append(note_p)
    return str(soup)


def markdown_to_plain_bytes(md_text: str, headline: str = "", canonical_url: str = "") -> bytes:
    """Tier 4 emergency fallback: clean UTF-8 plain text ready for Drive text/plain -> Doc import."""
    link_target = canonical_url or "https://mikelev.in"
    prepared = _prepare_markdown(md_text, canonical_url=link_target, tier=2)
    header = f"{headline}\nCanonical URL: {link_target}\n" + ("=" * 72) + "\n\n" if headline else ""
    full_text = header + prepared
    raw_bytes = full_text.encode('utf-8', errors='ignore')
    if len(raw_bytes) > 120000:
        clipped = raw_bytes[:120000].decode('utf-8', errors='ignore')
        clipped += f"\n\n---\n[Truncated for Google Docs — read full article at {link_target}]\n"
        return clipped.encode('utf-8')
    return raw_bytes


def _canonical_url(md_file: Path, post, base_url: str = "https://mikelev.in") -> str:
    """Resolve the public canonical URL for a post so truncated Google Docs can link back."""
    metadata = (post.metadata if post else None) or {}
    permalink = _metadata_value(metadata, "permalink")
    base = (base_url or "https://mikelev.in").rstrip("/")
    if permalink:
        p = str(permalink).strip()
        if p.startswith(("http://", "https://")):
            return p
        if not p.startswith("/"):
            p = "/" + p
        return f"{base}{p}"
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", md_file.stem)
    return f"{base}/futureproof/{stem}/"


def upsert_article_doc(service, folder_id, md_file, post, target_title, base_url="", existing_id=None):
    """Upsert a markdown post as a native Google Doc with a 4-tier HTTP 500 fallback ladder."""
    headline = _headline(md_file, post)
    canonical_url = _canonical_url(md_file, post, base_url=base_url)
    tiers = (
        (1, 'text/html', 'tier1:html-full'),
        (2, 'text/html', 'tier2:html-compact'),
        (3, 'text/html', 'tier3:html-minimal'),
        (4, 'text/plain', 'tier4:text-plain'),
    )
    last_err = None
    for tier_num, source_mime, tier_label in tiers:
        try:
            if source_mime == 'text/plain':
                payload_bytes = markdown_to_plain_bytes(
                    post.content, headline=headline, canonical_url=canonical_url
                )
            else:
                payload_bytes = markdown_to_html(
                    post.content, headline=headline, canonical_url=canonical_url, tier=tier_num
                )
            file_id, verb = drive_convert_upsert(
                service, folder_id, target_title, payload_bytes,
                source_mime, DOC_MIME, existing_id=existing_id
            )
            return file_id, verb, tier_label
        except HttpError as http_err:
            last_err = http_err
            status = http_err.resp.status if http_err.resp else 0
            if status not in (400, 413, 429, 500, 502, 503, 504):
                raise
            print(f"      ↻ {target_title!r} HTTP {status} on {tier_label}; trying next fallback tier...")
            time.sleep(0.5 * tier_num)
    raise last_err


# ----------------------------------------------------------------------------
# Title contract (forked verbatim-in-spirit from confluenceizer.py)
# ----------------------------------------------------------------------------
def _metadata_value(metadata: dict, *keys):
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _doc_date(md_file: Path, metadata: dict) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-", md_file.name)
    if match:
        return match.group(1)
    raw_date = _metadata_value(metadata, "date", "created", "published")
    if raw_date:
        return str(raw_date)[:10]
    return "0000-00-00"


def _fallback_title(md_file: Path) -> str:
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", md_file.stem)
    return stem.replace("-", " ").strip().title()


def _load_frontmatter_only(md_file: Path):
    """Parse only the leading YAML frontmatter block without reading the full markdown body."""
    try:
        with open(md_file, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(16384)
        if head.startswith('---'):
            end_idx = head.find('\n---', 3)
            if end_idx != -1:
                return frontmatter.loads(head[:end_idx + 4])
    except Exception:
        pass
    return frontmatter.load(md_file)


def _headline(md_file: Path, post) -> str:
    """The bare, PII-scrubbed article title: the Doc's opening H1."""
    metadata = post.metadata or {}
    return _sanitize_internal_pii(
        _metadata_value(metadata, "title") or _fallback_title(md_file)
    )
def _target_title(md_file: Path, post) -> str:
    metadata = post.metadata or {}
    title = _headline(md_file, post)
    sort_order = _metadata_value(metadata, "sort_order", "order", "sort", "ordinal")
    date_part = _doc_date(md_file, metadata)
    if sort_order is None:
        return f"{date_part} | {title}"
    return f"{date_part} ({sort_order}) | {title}"


# ----------------------------------------------------------------------------
# Drive primitives
# ----------------------------------------------------------------------------
def _remote_is_fresh(meta, md_file):
    """True when the remote Doc is at least as new as the local markdown file.

    Caveat: git checkouts reset mtimes, so a fresh clone makes every local
    file look newer and re-opens the upload path for one sweep. That converges
    and fails in the safe direction (re-upload, never silently stale).
    """
    modified = (meta or {}).get('modified')
    if not modified:
        return False
    try:
        remote = datetime.fromisoformat(modified.replace('Z', '+00:00'))
    except ValueError:
        return False
    local = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
    return remote >= local


def fetch_folder_inventory(service, folder_id):
    """Scan ONE Drive folder. Returns (inventory{name: meta}, duplicates{name})."""
    inventory = {}
    duplicates = set()
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        for f in resp.get('files', []):
            name = f.get('name')
            if name in inventory:
                duplicates.add(name)
            inventory[name] = {
                'id': f.get('id'),
                'mime': f.get('mimeType'),
                'modified': f.get('modifiedTime'),
            }
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return inventory, duplicates


def drive_convert_upsert(service, folder_id, name, payload_bytes,
                         source_mime, target_mime, existing_id=None):
    """The whole trick: upload convertible bytes, let Drive mint native formatting.

    CREATE: files.create with target google-apps mimeType + convertible media.
    UPDATE: files.update replaces content in place; Drive revision history is
    the version ledger -- no version arithmetic like the Confluence adapter.
    """
    media = MediaInMemoryUpload(payload_bytes, mimetype=source_mime, resumable=False)
    if existing_id:
        result = service.files().update(
            fileId=existing_id, media_body=media, body={"name": name}
        ).execute()
        return result.get('id', existing_id), "UPDATE"
    result = service.files().create(
        body={"name": name, "mimeType": target_mime, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    return result.get('id'), "CREATE"


def readback_ok(service, file_id, expected_name):
    """Light round-trip proof: title survived, export is non-empty."""
    meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    if meta.get('name') != expected_name:
        return False, f"title mismatch (got {meta.get('name')!r})"
    export_mime = 'text/plain' if meta.get('mimeType') == DOC_MIME else 'text/csv'
    data = service.files().export(fileId=file_id, mimeType=export_mime).execute()
    if not data:
        return False, "empty export"
    return True, f"{len(data):,} bytes exported"


def ensure_anyone_reader(service, file_id):
    """Idempotently grant 'anyone with the link can view' on one file.

    Drive treats a repeated anyone/reader grant as a no-op (the permission id
    is the fixed 'anyoneWithLink'), so calling this on every upsert -- CREATE
    and UPDATE alike -- is safe and retroactively heals docs created before
    this helper existed. Per-document on purpose: the folder itself stays
    private inventory; each article is independently public.
    """
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
        return True
    except HttpError:
        return False


def fetch_file(service, file_id):
    """FETCH mode: Doc -> server-side markdown export, Sheet -> csv, to stdout."""
    meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime = meta.get('mimeType')
    if mime == DOC_MIME:
        export_mime = 'text/markdown'
    elif mime == SHEET_MIME:
        # EARMARK -- multi-tab Sheets fetch, SPECULATIVE, and deliberately NOT
        # scheduled (verdict recorded 2026-08-31). This exports the first tab
        # only; a full export needs one request per gid. It stays a caveat
        # rather than a plan because nothing has ever asked for it: the CSV
        # lane has one caller, and no incident names a multi-tab sheet.
        # The comment survives so a later reader cannot mistake 'text/csv' for
        # a COMPLETE export -- the failure mode is silent truncation, which is
        # exactly the kind that gets diagnosed twice. Build it the first time a
        # real second tab is missed, and let that miss be the receipt.
        export_mime = 'text/csv'
    else:
        sys.stderr.write(f"Unsupported mimeType for fetch: {mime}\n")
        sys.exit(1)
    data = service.files().export(fileId=file_id, mimeType=export_mime).execute()
    text = data.decode('utf-8', errors='replace') if isinstance(data, bytes) else str(data)
    print(f"# Google Drive: {meta.get('name')} ({mime}) exported as {export_mime}\n")
    print(text)


def bootstrap_folder(service, name):
    resp = service.files().create(
        body={"name": name, "mimeType": FOLDER_MIME}, fields="id"
    ).execute()
    folder_id = resp.get('id')
    print(f"✅ Created Drive folder {name!r}")
    print(f"   Folder ID: {folder_id}")
    print(f"   Paste into ~/repos/nixos/blogs.nix as: gdrive_folder_id = \"{folder_id}\";")
    print("   Then: cd ~/repos/nixos && sudo nixos-rebuild switch")
    return folder_id


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Publish local markdown articles to Google Docs (Drive import-on-upload)."
    )
    common.add_standard_arguments(parser)
    parser.add_argument("fetch_id", nargs="?",
                        help="Drive file ID to FETCH (Doc->markdown, Sheet->csv) to stdout.")
    parser.add_argument("--yes", action="store_true",
                        help="Arm Drive mutations. Without this, only print the dry-run contract.")
    parser.add_argument("--file", action="append", metavar="PATH",
                        help="Sync only the given file(s). Repeatable. Beats --latest and the sweep.")
    parser.add_argument("--latest", action="store_true",
                        help="Sync only the article articleizer.py most recently wrote for this target.")
    # EARMARK -- --restamp, CONTINGENT RATHER THAN SPECULATIVE (2026-08-31).
    # --force is currently the ONLY remedy for a stale gdoc_url STRING, and it
    # is the wrong-sized tool: it re-uploads all ~1,400 documents to repair a
    # value the ledger shortcut could have rewritten locally. The trigger is
    # specific and dated -- the moment anyone edits common.gdoc_share_url().
    # On that day every post carries the right Doc ID in the wrong text, the
    # `stamped_id == existing` shortcut skips the whole corpus, and only a full
    # --force sweep heals it.
    # BUILD IT AS A RIDER ON THAT CHANGE, NEVER STANDALONE. --restamp would
    # walk the same freshness branch, skip the shortcut, call
    # stamp_frontmatter_value unconditionally, and perform ZERO Drive
    # mutations. Shipping it before the format change would add a flag with no
    # users guarding a change nobody has proposed.
    parser.add_argument("--force", action="store_true",
                        help="Re-upload even docs the freshness gate would skip (e.g. after a rendering-pipeline change).")
    parser.add_argument("--list", action="store_true",
                        help="List the Drive folder inventory and exit.")
    parser.add_argument("--folder", metavar="ID",
                        help="Override the target's gdrive_folder_id (probe before committing to Nix).")
    parser.add_argument("--csv", metavar="PATH",
                        help="Upsert a CSV file as a native Google Sheet in the folder.")
    parser.add_argument("--bootstrap-folder", metavar="NAME",
                        help="Create the Drive folder once and print its ID.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print a line per article even on a full sweep (a sweep is quiet by default).")
    args = parser.parse_args()

    # THE RULE OF SILENCE, GATED BY INTENT RATHER THAN BY COUNT (2026-08-31).
    # A sweep printed ~2,900 lines before a single upload: one Target Title
    # line and one MATCH line per article, both of which say only that the
    # ORDINARY thing happened. release.py's precedent is the rule -- print the
    # lines that name a CHANGE, plus one counter -- and the counter matters
    # more here than there, because silence that cannot be told apart from a
    # dead loop is worse than the noise it replaced.
    # INTENT, NOT SIZE: --file and --latest mean the human NAMED the documents,
    # so every line is signal and nothing is suppressed. A count-based gate
    # ("quiet above N") would make the same command print differently on
    # different targets, which is exactly the kind of surface that gets
    # diagnosed twice. -v recovers the detail on a sweep, mirroring release.py.
    verbose = args.verbose or bool(args.file or args.latest)

    service = get_service()

    if args.bootstrap_folder:
        bootstrap_folder(service, args.bootstrap_folder)
        return

    if args.fetch_id:
        fetch_file(service, args.fetch_id)
        return

    targets = common.load_targets()
    target_key = str(args.target)
    if target_key not in targets:
        print(f"❌ Error: Target key '{target_key}' not found in blogs.json.")
        sys.exit(1)
    config = targets[target_key]
    print(f"🔒 Locked Target: {config.get('name')} ({config.get('path')})")

    folder_id = (args.folder or config.get("gdrive_folder_id") or "").strip()
    if not folder_id:
        print("❌ Aborted: no Drive folder configured for this target.")
        print("  ↳ Bootstrap: python scripts/articles/googledocizer.py --bootstrap-folder \"MikeLev.in Articles\"")
        print("  ↳ Then set gdrive_folder_id in ~/repos/nixos/blogs.nix and rebuild, or pass --folder ID to probe.")
        sys.exit(1)
    print(f"📡 Anchored Drive Folder ID: {folder_id}")

    print("🔎 Scanning remote folder inventory...")
    inventory, duplicates = fetch_folder_inventory(service, folder_id)
    print(f"✅ Inventory scan complete. {len(inventory)} child file(s).")
    if duplicates:
        print(f"⚠ {len(duplicates)} duplicate name(s) in folder -- those titles will be skipped.")

    if args.list:
        for name, meta in sorted(inventory.items()):
            kind = 'Doc' if meta['mime'] == DOC_MIME else (
                'Sheet' if meta['mime'] == SHEET_MIME else meta['mime'])
            print(f"   • [{kind}] [ID: {meta['id']}] {name}")
        return

    # --- CSV -> Sheet lane (same helper, different mimetype pair) ---
    if args.csv:
        csv_path = Path(args.csv).expanduser().resolve()
        if not csv_path.is_file():
            print(f"❌ CSV not found: {csv_path}")
            sys.exit(1)
        sheet_name = csv_path.stem
        meta = inventory.get(sheet_name)
        existing = meta['id'] if meta and meta['mime'] == SHEET_MIME else None
        if not args.yes:
            verb = "UPDATE" if existing else "CREATE"
            print(f"🅳🆁🆈 DRY-RUN -- would {verb} Sheet {sheet_name!r} from {csv_path.name}. Add --yes to arm.")
            return
        file_id, verb = drive_convert_upsert(
            service, folder_id, sheet_name, csv_path.read_bytes(),
            'text/csv', SHEET_MIME, existing_id=existing
        )
        ok, detail = readback_ok(service, file_id, sheet_name)
        flag = "✅" if ok else "⚠"
        print(f"   {flag} {verb} [ID: {file_id}] -> {sheet_name} ({detail})")
        return

    # --- Article publish lane (mirror of confluenceizer.py) ---
    posts_dir = Path(config["path"]).expanduser().resolve()
    if not posts_dir.is_dir():
        print(f"❌ Error: Posts directory does not exist: {posts_dir}")
        sys.exit(1)

    # Selection precedence: explicit --file > --latest (pending catch-up + latest) > full directory sweep.
    latest_update_set = set()
    if args.file:
        md_files = []
        for raw in args.file:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = posts_dir / candidate
            candidate = candidate.resolve()
            if candidate.is_file():
                md_files.append(candidate)
            else:
                print(f"   ⚠ Skipping --file (not found): {candidate}")
        print(f"🎯 Explicit selection via --file: {len(md_files)} document(s).")
    elif args.latest:
        all_posts = sorted(posts_dir.glob("*.md"))
        dated_posts = [p for p in all_posts if p.name[:4].isdigit()]
        latest_path = common.get_last_published(target_key)
        if latest_path and Path(latest_path).is_file():
            latest_update_set.add(Path(latest_path).resolve())
        if dated_posts:
            latest_update_set.add(dated_posts[-1].resolve())
        if not latest_update_set:
            print(f"❌ --latest: no markdown posts found for target '{target_key}'.")
            sys.exit(1)
        md_files = all_posts
        marker_names = ", ".join(sorted(p.name for p in latest_update_set))
        print(f"🎯 Latest + pending catch-up selection (latest marker: {marker_names})")
    else:
        md_files = sorted(posts_dir.glob("*.md"))

    print(f"📝 Found {len(md_files)} candidate document(s) for publishing queue.")
    if not md_files:
        print("🛑 Queue empty. Nothing to parse.")
        return

    # SORT THE FAILURE BY ITS SCOPE (2026-08-31). A missing `markdown` package
    # is GLOBAL: it cannot fail for one article and succeed for another. Under
    # the per-file handling the lazy render introduces below, it would print
    # 1,431 identical RuntimeErrors instead of one legible abort -- the same
    # RETIRE-THE-CANARY failure as a warning that fires every time. So the
    # global condition keeps failing CLOSED, once, here, before any Drive
    # mutation; only genuinely per-file failures get per-file tolerance.
    if md_lib is None:
        print("❌ The 'markdown' package is missing; every render would fail identically.")
        print("   Add it to requirements.in and reinstall.")
        print("   Probe: .venv/bin/python -c 'import markdown'")
        sys.exit(1)

    local_contracts = []
    pre_settled = 0
    print("\n🧾 Local Target Title Contract:")
    try:
        for md_file in md_files:
            resolved_md = md_file.resolve()
            post = _load_frontmatter_only(resolved_md)
            target_title = _target_title(resolved_md, post)
            stamped_id = common.gdoc_id_from_frontmatter(post.metadata)
            if args.latest:
                meta_chk = inventory.get(target_title)
                if meta_chk and stamped_id == meta_chk['id'] and resolved_md not in latest_update_set:
                    pre_settled += 1
                    continue
            # THE RENDER MOVED OUT OF THIS LOOP (measured: ~5 minutes for a
            # 1,431-article sweep, ~119 of which actually upload). This loop
            # exists to compute TITLES, and a title needs frontmatter, not
            # HTML. Rendering here markdown-converted every article in the
            # corpus and held ~215MB of HTML in memory so that the freshness
            # gate below could discard 92% of it unread. The API was never the
            # cost; the render was, and it was paid whether or not anything
            # uploaded. It now happens at its one point of use, inside the
            # upload branch of the upsert loop.
            # THE SLOT IS GONE, NOT NULLED. A tuple position that could only
            # ever hold None reads like a cache a later change might populate,
            # and there is no such future: point-of-use rendering strictly
            # dominates any pre-render. Three unpack sites move to 3-tuples.
            local_contracts.append((resolved_md, target_title, stamped_id))
        local_contracts.sort(key=lambda item: item[1])
        if verbose:
            for _, target_title, _ in local_contracts:
                print(f"   Target Title: {target_title}")
        settled_note = f" ({pre_settled} prior post(s) already synced & stamped)" if pre_settled else ""
        print(f"✅ Local contract pass complete. {len(local_contracts)} active document(s) mapped{settled_note}.")
    except Exception as e:
        print(f"❌ Local contract failure: {e}")
        sys.exit(1)

    print("\n🧭 Remote Match Contract:")
    settled = 0
    for md_file, target_title, stamped_id in local_contracts:
        meta = inventory.get(target_title)
        if meta:
            if stamped_id == meta['id']:
                # THE ORDINARY CASE, AND THE ONLY ONE THAT IS SILENT: the post
                # already points at the doc this run would point it at. Nothing
                # downstream will touch it. Counted, not narrated.
                settled += 1
                if verbose:
                    print(f"   MATCH: {md_file.name} -> [ID: {meta['id']}] {target_title} [stamped]")
                continue
            if stamped_id:
                stamp_note = "STAMP MISMATCH -- frontmatter points at a different doc; --yes heals to inventory"
            else:
                stamp_note = "unstamped -- --yes heals without re-upload if fresh"
            print(f"   MATCH: {md_file.name} -> [ID: {meta['id']}] {target_title} [{stamp_note}]")
        else:
            stale = " [stamped but doc missing from folder -- --yes recreates and restamps]" if stamped_id else ""
            print(f"   MISS:  {md_file.name} -> {target_title}{stale}")
    if settled and not verbose:
        print(f"   ... plus {settled} already-stamped MATCH(es) with nothing to do (-v to list).")

    # WHAT THE DRY RUN CANNOT TELL YOU (named 2026-08-31, because the probe
    # that measured this file's new silence could not have caught it). The
    # freshness gate, the ledger shortcut and the lazy render ALL live below
    # this return. A dry run therefore exercises the Local Contract and Remote
    # Match passes and NOTHING ELSE -- it prints an identical stream whether
    # the freshness gate is perfect or completely broken.
    # CONSEQUENCE FOR PROBES: `googledocizer.py -t 1 | wc -l` measures the
    # silence of the two passes above, and is a fine straddle for THEM. It is
    # not, and cannot be made into, evidence about the upsert loop. The only
    # honest witness for that loop is an armed run's 🏁 counters -- which is
    # why Fresh was split out of Skipped rather than left folded in.
    if not args.yes:
        print("\n🅳🆁🆈 DRY-RUN -- no mutation. Review MATCH/MISS lines, then re-run with --yes.")
        return

    print(f"\n✍️  Mutations armed (--yes). Upserting {len(local_contracts)} document(s)...")
    # FRESH SPLIT OUT OF SKIPPED, forced by the silence above. `skipped` merged
    # two unlike things: "nothing to do" (FRESH) and "I refused" (duplicate
    # name, wrong mime). While every FRESH printed its own line you could tell
    # them apart by eye. With those lines suppressed the 🏁 summary is the only
    # witness left, and a merged counter there cannot answer the discrimination
    # question. `skipped` now means refusals only -- a nonzero value is
    # something to go look at.
    created = updated = healed = skipped = failed = fresh = 0
    for md_file, target_title, stamped_id in local_contracts:
        if target_title in duplicates:
            print(f"   ⚠ SKIP {target_title!r}: duplicate name in folder; resolve by hand first.")
            skipped += 1
            continue
        meta = inventory.get(target_title)
        if meta and meta['mime'] != DOC_MIME:
            print(f"   ⚠ SKIP {target_title!r}: name exists but is not a Google Doc ({meta['mime']}).")
            skipped += 1
            continue
        existing = meta['id'] if meta else None

        # Freshness gate: an existing doc that is not older than the local
        # file costs ZERO Drive mutations. The frontmatter stamp is still
        # verified locally, so a MATCHed-but-unstamped post gets its ledger
        # entry (and a share re-assert) without a re-upload. --force reopens
        # the full re-render path for rendering-pipeline changes.
        is_catchup_heal = bool(args.latest and md_file not in latest_update_set)
        if existing and not args.force and (is_catchup_heal or _remote_is_fresh(meta, md_file)):
            # THE LEDGER SHORTCUT (2026-08-31). stamp_frontmatter_value opens
            # the file, read_text()s ~200k bytes, splits them into a line list,
            # scans the YAML block, finds the line already correct and returns
            # UNCHANGED -- having allocated all of it to answer a question the
            # contract loop already answered. stamped_id came out of THAT parse;
            # if it equals the doc we are about to point at, the answer is
            # UNCHANGED and no second read is needed.
            #
            # IN THE CALLER, NOT IN common. stamp_frontmatter_value is a GENERIC
            # key/value upserter and its contract is "read the file, tell the
            # truth about that line." A known_current= argument would make it
            # trust a claim it cannot verify, and the claim available here is
            # not the current value but an ID a regex pulled OUT of it. Domain
            # knowledge belongs to the domain caller; the helper stays honest.
            #
            # STALENESS IS STRUCTURALLY EXCLUDED, not merely unlikely.
            # stamped_id was parsed seconds ago, but this guard sits INSIDE the
            # freshness branch, and _remote_is_fresh stats mtime LIVE. Any real
            # write bumps mtime, fails that gate, and routes to the upload path
            # -- which stamps from a fresh read. A concurrent edit cannot reach
            # this line. Our own stamps preserve mtime by design, so they never
            # disturb it either.
            #
            # WHAT IT CAN GET WRONG: ID equality is not STRING equality. A post
            # whose gdoc_url carries the right ID in non-canonical text (hand
            # edited, or written before a change to gdoc_share_url) is skipped
            # rather than canonicalized. Remedy today is --force, which also
            # re-uploads; a cheap --restamp that walks the stamp path without
            # the upload is an earmark, not a promise.
            if stamped_id == existing:
                if verbose:
                    print(f"   ⏭  FRESH [ID: {existing}] -> {target_title} (no upload; --force to re-render)")
                fresh += 1
                continue
            # KEPT AS INSURANCE, not as dead code. If the shortcut above ever
            # misses -- a Doc ID containing a character outside the extractor's
            # [A-Za-z0-9_-] class would truncate stamped_id and defeat it --
            # this branch still reads the file and still reports the truth. It
            # costs one read on a path the shortcut has already emptied.
            stamp = common.stamp_frontmatter_value(
                md_file, common.GDOC_URL_KEY, common.gdoc_share_url(existing))
            if stamp == "UNCHANGED":
                if verbose:
                    print(f"   ⏭  FRESH [ID: {existing}] -> {target_title} (no upload; --force to re-render)")
                fresh += 1
            else:
                shared = ensure_anyone_reader(service, existing)
                share_note = "🌐 link-shared" if shared else "⚠ SHARE FAILED"
                print(f"   🩹 HEAL  [ID: {existing}] -> {target_title} (frontmatter {stamp} | {share_note})")
                healed += 1
            continue

        try:
            # THE LAZY RENDER, inside the existing per-file try. Reaching this
            # line means the freshness gate has already decided this article
            # WILL be uploaded, so the render is never speculative.
            # WHY THIS IS SAFE AFTER THE MOVE, stated rather than assumed: the
            # upsert loop was NEVER atomic. It already writes document by
            # document and already catches HttpError per file and continues, so
            # an HTTP 500 on number 400 has always left 399 written. Partial
            # state is the designed-for reality here -- the freshness gate plus
            # title matching is precisely what makes a re-run heal it. The
            # contract loop's try/except only ever guarded ONE narrow failure
            # class while leaving the far likelier one wide open, which is
            # illusory atomicity, and an illusory guarantee is worse than an
            # absent one. What this buys: one unrenderable article now costs
            # one ❌ line and a `failed` increment instead of aborting the
            # other 1,430.
            # RE-READ RATHER THAN RETAIN: holding post.content for the whole
            # corpus would trade the HTML for markdown of comparable size and
            # give back most of the memory win. One extra read of ~119 files
            # is cheaper than 1,431 retained bodies. Safe against the stamp
            # writer below, which only touches the file AFTER the upload.
            post = frontmatter.load(md_file)
            file_id, verb, tier_label = upsert_article_doc(
                service, folder_id, md_file, post, target_title,
                base_url=config.get("url") or "https://mikelev.in",
                existing_id=existing,
            )
            ok, detail = readback_ok(service, file_id, target_title)
            if tier_label != "tier1:html-full":
                detail = f"{detail} | {tier_label}"
            shared = ensure_anyone_reader(service, file_id)
            stamp = common.stamp_frontmatter_value(
                md_file, common.GDOC_URL_KEY, common.gdoc_share_url(file_id))
            flag = "✅" if ok else "⚠"
            share_note = "🌐 link-shared" if shared else "⚠ SHARE FAILED"
            print(f"   {flag} {verb} [ID: {file_id}] -> {target_title} ({detail} | {share_note} | stamp: {stamp})")
            print(f"      🔗 {common.gdoc_share_url(file_id)}")
            if not ok:
                print(f"      ⚠ Round-trip suspect: {detail}. Inspect before trusting.")
            if stamp == "NO_FRONTMATTER":
                print(f"      ⚠ Could not stamp {md_file.name}: no YAML frontmatter block found.")
            if verb == "CREATE":
                created += 1
                inventory[target_title] = {'id': file_id, 'mime': DOC_MIME, 'modified': None}
            else:
                updated += 1
            time.sleep(0.2)  # polite pacing for full-corpus sweeps
        except HttpError as http_err:
            print(f"   ❌ {target_title!r} failed (HTTP {http_err.resp.status if http_err.resp else '?'}): {http_err}")
            failed += 1
        except Exception as err:
            print(f"   ❌ {target_title!r} failed: {err}")
            failed += 1

    print(f"\n🏁 Upsert complete. Created: {created}  Updated: {updated}  Healed: {healed}  Fresh: {fresh}  Skipped: {skipped}  Failed: {failed}")


if __name__ == "__main__":
    main()
