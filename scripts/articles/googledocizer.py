#!/usr/bin/env python3
# scripts/articles/googledocizer.py
"""
googledocizer.py — The Idempotent Google Docs Publishing Adapter.

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

AUTH (the ~/repos/nixos wallet convention — composite filenames, one flat dir)
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


def _prepare_markdown(md_text: str) -> str:
    """Strip Liquid wrappers and prune public-web meta blocks before conversion."""
    # Liquid safety wrappers matter to Jekyll, are noise in a Google Doc.
    md_text = re.sub(r'\{%-?\s*raw\s*-?%\}\s*\n?', '', md_text)
    md_text = re.sub(r'\{%-?\s*endraw\s*-?%\}\s*\n?', '', md_text)
    # Prune promo/meta blocks that only make sense on the public site.
    md_text = re.sub(
        r'### 🐦 X\.com Promo Tweet\n```text\n.*?\n```\n*', '', md_text, flags=re.DOTALL
    )
    md_text = re.sub(
        r'### Title Brainstorm\n.*?(?=\n### |\Z)', '', md_text, flags=re.DOTALL
    )
    return _sanitize_internal_pii(md_text)


def markdown_to_html(md_text: str) -> bytes:
    """Markdown -> minimal HTML document, ready for Drive import-on-upload."""
    if md_lib is None:
        raise RuntimeError(
            "The 'markdown' package is required. Add it to requirements.in "
            "and reinstall (probe: .venv/bin/python -c 'import markdown')."
        )
    body = md_lib.markdown(_prepare_markdown(md_text), extensions=['extra', 'sane_lists'])
    html = f"<html><head><meta charset=\"utf-8\"></head><body>{body}</body></html>"
    return html.encode('utf-8')


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


def _target_title(md_file: Path, post) -> str:
    metadata = post.metadata or {}
    title = _sanitize_internal_pii(
        _metadata_value(metadata, "title") or _fallback_title(md_file)
    )
    sort_order = _metadata_value(metadata, "sort_order", "order", "sort", "ordinal")
    date_part = _doc_date(md_file, metadata)
    if sort_order is None:
        return f"{date_part} | {title}"
    return f"{date_part} ({sort_order}) | {title}"


# ----------------------------------------------------------------------------
# Drive primitives
# ----------------------------------------------------------------------------
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
    the version ledger — no version arithmetic like the Confluence adapter.
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
    is the fixed 'anyoneWithLink'), so calling this on every upsert — CREATE
    and UPDATE alike — is safe and retroactively heals docs created before
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
        # NOTE: exports the first/default tab only; multi-tab needs per-gid
        # exports — a deliberately deferred probe.
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
    parser.add_argument("--list", action="store_true",
                        help="List the Drive folder inventory and exit.")
    parser.add_argument("--folder", metavar="ID",
                        help="Override the target's gdrive_folder_id (probe before committing to Nix).")
    parser.add_argument("--csv", metavar="PATH",
                        help="Upsert a CSV file as a native Google Sheet in the folder.")
    parser.add_argument("--bootstrap-folder", metavar="NAME",
                        help="Create the Drive folder once and print its ID.")
    args = parser.parse_args()

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
        print(f"⚠ {len(duplicates)} duplicate name(s) in folder — those titles will be skipped.")

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
            print(f"🅳🆁🆈 DRY-RUN — would {verb} Sheet {sheet_name!r} from {csv_path.name}. Add --yes to arm.")
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

    # Selection precedence: explicit --file > --latest > full directory sweep.
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
        latest_path = common.get_last_published(target_key)
        if not latest_path:
            print(f"❌ --latest: no recorded publish for target '{target_key}'.")
            print("  ↳ Run articleizer first, pass --file PATH, or drop --latest for a full sweep.")
            sys.exit(1)
        md_files = [Path(latest_path).resolve()]
        print(f"🎯 Latest-only selection (from marker): {md_files[0].name}")
    else:
        md_files = sorted(posts_dir.glob("*.md"))

    print(f"📝 Found {len(md_files)} candidate document(s) for publishing queue.")
    if not md_files:
        print("🛑 Queue empty. Nothing to parse.")
        return

    local_contracts = []
    print("\n🧾 Local Target Title Contract:")
    try:
        for md_file in md_files:
            post = frontmatter.load(md_file)
            target_title = _target_title(md_file, post)
            html_bytes = markdown_to_html(post.content)
            local_contracts.append((md_file, target_title, html_bytes))
            print(f"   Target Title: {target_title}")
        print(f"✅ Local contract pass complete. {len(local_contracts)} document(s) mapped.")
    except Exception as e:
        print(f"❌ Local contract failure: {e}")
        sys.exit(1)

    print("\n🧭 Remote Match Contract:")
    for md_file, target_title, _html in local_contracts:
        meta = inventory.get(target_title)
        if meta:
            print(f"   MATCH: {md_file.name} -> [ID: {meta['id']}] {target_title}")
        else:
            print(f"   MISS:  {md_file.name} -> {target_title}")

    if not args.yes:
        print("\n🅳🆁🆈 DRY-RUN — no mutation. Review MATCH/MISS lines, then re-run with --yes.")
        return

    print(f"\n✍️  Mutations armed (--yes). Upserting {len(local_contracts)} document(s)...")
    created = updated = skipped = failed = 0
    for md_file, target_title, html_bytes in local_contracts:
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
        try:
            file_id, verb = drive_convert_upsert(
                service, folder_id, target_title, html_bytes,
                'text/html', DOC_MIME, existing_id=existing
            )
            ok, detail = readback_ok(service, file_id, target_title)
            shared = ensure_anyone_reader(service, file_id)
            flag = "✅" if ok else "⚠"
            share_note = "🌐 link-shared" if shared else "⚠ SHARE FAILED"
            print(f"   {flag} {verb} [ID: {file_id}] -> {target_title} ({detail} | {share_note})")
            print(f"      🔗 https://docs.google.com/document/d/{file_id}/edit?usp=sharing")
            if not ok:
                print(f"      ⚠ Round-trip suspect: {detail}. Inspect before trusting.")
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

    print(f"\n🏁 Upsert complete. Created: {created}  Updated: {updated}  Skipped: {skipped}  Failed: {failed}")


if __name__ == "__main__":
    main()
