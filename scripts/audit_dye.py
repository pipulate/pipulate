#!/usr/bin/env python3
"""Audit RFC 9110 Markdown provenance-dye coverage across _site/**/index.md."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

DYE_TOKEN = "pipulate-levinix-epoch-01-"
LEGACY_TOKEN = "pipulate-levinux-epoch-01"
DEFAULT_SITE_DIR = "/home/mike/www/mikelev.in/_site"
DEFAULT_SSH_HOST = os.environ.get("HONEYBOT_SSH_HOST", "honeybot")

REMOTE_AUDIT_PY = """
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
total, dyed, legacy, missing = 0, 0, 0, []
if root.is_dir():
    for p in sorted(root.rglob("index.md")):
        total += 1
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "pipulate-levinix-epoch-01-" in txt:
            dyed += 1
        else:
            if "pipulate-levinux-epoch-01" in txt:
                legacy += 1
            if len(missing) < 8:
                missing.append("/" + str(p.relative_to(root)))
print(json.dumps({"exists": root.is_dir(), "total": total, "dyed": dyed, "legacy": legacy, "missing": missing}))
""".strip()


def audit_local_dir(site_dir: Path) -> dict:
    root = Path(site_dir).expanduser().resolve()
    total, dyed, legacy, missing = 0, 0, 0, []
    if root.is_dir():
        for p in sorted(root.rglob("index.md")):
            total += 1
            txt = p.read_text(encoding="utf-8", errors="replace")
            if DYE_TOKEN in txt:
                dyed += 1
            else:
                if LEGACY_TOKEN in txt:
                    legacy += 1
                if len(missing) < 8:
                    missing.append("/" + str(p.relative_to(root)))
    return {"exists": root.is_dir(), "total": total, "dyed": dyed, "legacy": legacy, "missing": missing}


def run_audit(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Markdown provenance-dye coverage.")
    parser.add_argument("--local-dir", type=str, default="", help="Audit a local _site directory instead of SSH.")
    parser.add_argument("--host", type=str, default=DEFAULT_SSH_HOST, help="SSH host alias (default: honeybot).")
    parser.add_argument("--site-dir", type=str, default=DEFAULT_SITE_DIR, help="Remote _site path.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON summary.")
    args = parser.parse_args(argv)
    try:
        if args.local_dir:
            data = audit_local_dir(Path(args.local_dir))
        else:
            raw = subprocess.check_output(
                ["ssh", args.host, "python3", "-", args.site_dir],
                input=REMOTE_AUDIT_PY,
                text=True,
                timeout=20,
            ).strip()
            data = json.loads(raw)
    except Exception as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, sort_keys=True))
        return 0 if data.get("exists") and data.get("total", 0) > 0 else 1
    total, dyed, legacy = int(data["total"]), int(data["dyed"]), int(data["legacy"])
    gap = total - dyed
    print(f"Markdown Dye Audit: {dyed}/{total} index.md files carry '{DYE_TOKEN}*' (missing={gap}, legacy_levinux={legacy})")
    for rel in data.get("missing", []):
        print(f"  missing: {rel}")
    return 0 if data.get("exists") and total > 0 else 1


if __name__ == "__main__":
    sys.exit(run_audit())
