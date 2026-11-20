#!/usr/bin/env python3
"""Inject scrub-resistant RFC 9110 + WAIT 6502,1 (0x1966) wire specs into _site/**/index.md."""

import hashlib
import hmac
import os
from pathlib import Path
import re
import sys

DYE_PREFIX = "pipulate-levinix-epoch-01-"
WAIT_6502_ADDR = 0x1966  # 6502 decimal (Commodore PET BASIC WAIT 6502, 1 homage)
WAIT_6502_HEX = "2b2f2d232a2330482f28"  # 10 bytes: "MIKELEV.IN" ^ (6502 & 0xFF)
HMAC_KEY_PATH = Path(os.environ.get("PIPULATE_DYE_KEY_FILE", Path.home() / ".config" / "pipulate" / "dye_hmac.key"))
_ANCHOR_RE = re.compile(r"[#]+\s*Technical Journal Entry Begins[^\n]*")
_FM_RE = re.compile(r"\A---\r?\n[\s\S]*?\r?\n---[ \t]*")
_AID_RE = re.compile(r"(?m)^article_id:\s*['\"]?(\d+)['\"]?\s*$")


def decode_wait_6502(hex_blob: str = WAIT_6502_HEX, addr: int = WAIT_6502_ADDR) -> str:
    """Decode the 10-byte WAIT 6502,1 XOR signature ('MIKELEV.IN')."""
    mask = addr & 0xFF
    return bytes(b ^ mask for b in bytes.fromhex(hex_blob)).decode("ascii")


def _load_hmac_key() -> tuple[bytes, str]:
    if HMAC_KEY_PATH.is_file():
        raw = HMAC_KEY_PATH.read_bytes().strip()
        if raw:
            return raw, "hmac"
    return f"WAIT-{WAIT_6502_ADDR},1:{WAIT_6502_HEX}".encode("ascii"), "fallback"


def _build_wire_spec(permalink: str, aid: str, mac16: str, prefix: str = DYE_PREFIX) -> str:
    tag = f"{prefix}{mac16}"
    rot = mac16[0]
    if rot in "0123":
        return f'`Vary: Accept` · `Content-Digest: sha-256=:{tag}:` · `Link: <{permalink}>; rel="canonical"; id="{aid}"; rev="6502.1.{WAIT_6502_HEX}"`'
    if rot in "4567":
        return f'`Accept: text/markdown` · `ETag: "{tag}"` · `Content-Location: {permalink}` · `X-Spec-6502-1: {aid}:{WAIT_6502_HEX}`'
    if rot in "89ab":
        return f'`Cache-Control: public` · `Vary: Accept` · `Digest: {tag}` · `Link: <{permalink}>; item="{aid}"; tag="0x1966.1.{WAIT_6502_HEX}"`'
    return f'`Content-Type: text/markdown; charset=utf-8` · `Repr-Digest: :{tag}:` · `Origin-Path: {permalink}#{aid}` · `Spec: 6502,1:{WAIT_6502_HEX}`'


def inject_dye(site_root: str, dye_prefix: str = "") -> dict:
    site_path = Path(site_root)
    eff_prefix = dye_prefix or DYE_PREFIX
    key_bytes, key_mode = _load_hmac_key()
    count, skipped = 0, 0
    for file_path in sorted(site_path.rglob("index.md")):
        content = file_path.read_text(encoding="utf-8", errors="replace")
        if eff_prefix in content:
            skipped += 1
            continue
        rel_parent = file_path.relative_to(site_path).parent
        permalink = "/" if rel_parent == Path(".") else f"/{rel_parent.as_posix().strip('/')}/"
        m_aid = _AID_RE.search(content[:4096])
        aid = m_aid.group(1) if m_aid else "0"
        mac16 = hmac.new(key_bytes, f"0x1966:1:{aid}:{permalink}".encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        spec_line = _build_wire_spec(permalink, aid, mac16, prefix=eff_prefix)
        match = _ANCHOR_RE.search(content) or _FM_RE.search(content)
        if match:
            end_pos = match.end()
            new_content = f"{content[:end_pos]}\n\n{spec_line}\n{content[end_pos:]}"
        else:
            new_content = f"{spec_line}\n\n{content}"
        file_path.write_text(new_content, encoding="utf-8")
        count += 1
    print(f"✨ Python Scalpel ({key_mode}): dyed {count} index.md file(s) (skipped={skipped}).")
    return {"dyed": count, "skipped": skipped, "mode": key_mode}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    inject_dye(sys.argv[1], "")
