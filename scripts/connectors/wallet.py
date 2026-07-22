#!/usr/bin/env python3
# scripts/connectors/wallet.py
"""
wallet.py — Read-only scoreboard for the Pipulate connector wallet.

Golden-path modes, auto-detected from the leading positional argument:

  python scripts/connectors/wallet.py                 # SCOREBOARD: stat every oauth_token_file slot (filled / stale / empty)
  python scripts/connectors/wallet.py login <slot>    # (NEXT SLICE — not wired) mint a slot's token interactively

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/wallet.py
  ! python scripts/connectors/wallet.py -n 5

This is the GENERALIZATION of each connector's no-argument identity() walk
(see sheets.py) lifted from ONE connector to the WHOLE wallet: instead of a
single connector reporting its own OAuth wiring, wallet.py reads
~/.config/pipulate/connectors.json (override: PIPULATE_WALLET) and reports
every oauth_token_file slot at once, so a glance tells you which sessions are
live, which have gone stale, and which have never been minted.

SCOREBOARD is strictly READ-ONLY and OFFLINE:
  - It reads connectors.json (names and paths only).
  - It os.stat()s each slot's token file for existence, size, and mtime.
  - It NEVER opens the token bytes (the wallet's own _rule: names and paths
    ONLY, never secret values), NEVER touches the network, and NEVER reads
    credentials.json / client_secret. Token VALIDITY (is the refresh token
    revoked?) cannot be known offline; `stale` is an honest mtime heuristic,
    not a verdict — only `wallet login <slot>` (the next slice) can prove a
    session live, and that walk is gated on external Cloud-console registration.

WHY mtime, WHY --stale-days 7: the connectors rewrite the token file on every
successful refresh (see _save_token after creds.refresh), so mtime tracks
"last refreshed", not "first minted". Google OAuth clients in *Testing*
publishing status expire their refresh tokens 7 days after issuance, so 7 days
is the tightest real cliff and the honest default warning window. A token not
rewritten in a week is the one most likely to have lapsed. It is a heuristic,
never proof.

States (per token file, from stat alone):
  filled   — present, non-empty, modified within --stale-days. Assumed live.
  stale    — present and non-empty, but last modified > --stale-days ago.
  empty    — missing, or present-but-0-bytes (the truncated-write trap the
             connectors re-auth on). This slot needs a login.
  no-path  — slot declares auth=oauth_token_file but resolves no token path
             (a wallet config error — surfaced, not hidden).
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

WALLET_PATH = os.environ.get('PIPULATE_WALLET') or str(
    Path.home() / '.config' / 'pipulate' / 'connectors.json')

_OAUTH_KIND = 'oauth_token_file'
_MARK = {'filled': '[x]', 'stale': '[~]', 'empty': '[ ]', 'no-path': '[!]'}


def die(msg, code=1):
    sys.stderr.write(msg.rstrip('\n') + '\n')
    sys.exit(code)


def load_wallet():
    """Read connectors.json (names and paths only). Fail loud, never guess."""
    path = Path(WALLET_PATH).expanduser()
    if not path.exists():
        die(f"No wallet at: {path}\n"
            "Set PIPULATE_WALLET or create ~/.config/pipulate/connectors.json.")
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        die(f"Unreadable wallet at {path}: {e}")


def resolve_token_path(slot):
    """Resolved, ~-expanded token path for an oauth_token_file slot, honoring
    any env override the wallet declares as 'overrides paths.token' — mirroring
    the connectors' own `os.environ.get(...) or <path>`. None when no path.
    """
    for env_key, desc in (slot.get('env') or {}).items():
        if 'paths.token' in str(desc) and os.environ.get(env_key):
            return str(Path(os.environ[env_key]).expanduser())
    raw = (slot.get('paths') or {}).get('token')
    return str(Path(raw).expanduser()) if raw else None


def classify(token_path, stale_days):
    """Return (state, detail) from an os.stat only — never opens the bytes."""
    if token_path is None:
        return 'no-path', 'slot declares no paths.token'
    p = Path(token_path)
    if not p.exists():
        return 'empty', 'not yet minted'
    try:
        st = p.stat()
    except OSError as e:
        return 'empty', f'unstatable ({e})'
    if st.st_size == 0:
        return 'empty', '0 bytes (poisoned/truncated)'
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400.0
    detail = f"{mtime.strftime('%Y-%m-%d')} ({age_days:.0f}d ago)"
    return ('stale' if age_days > stale_days else 'filled'), detail


def scoreboard(wallet, max_items, stale_days):
    """Print the read-only wallet board for every oauth_token_file slot."""
    slots = [(name, cfg) for name, cfg in wallet.items()
             if not name.startswith('_') and isinstance(cfg, dict)
             and cfg.get('auth') == _OAUTH_KIND]

    print("# wallet.py — connector OAuth scoreboard (read-only, offline)")
    print(f"# wallet: {Path(WALLET_PATH).expanduser()}")
    print(f"# stale after: {stale_days}d (mtime heuristic, not a validity proof)\n")

    if not slots:
        print("(no oauth_token_file slots in this wallet)")
        print("\n# Next: add an oauth_token_file slot to connectors.json, "
              "then re-run this scoreboard.")
        return

    shown = slots[:max_items]
    rows = []
    for name, cfg in shown:
        tok = resolve_token_path(cfg)
        state, detail = classify(tok, stale_days)
        rows.append((state, name, detail, tok or '(no path)'))

    name_w = max(len('slot'), *(len(r[1]) for r in rows))
    det_w = max(len('token mtime'), *(len(r[2]) for r in rows))
    print(f"     {'state':<7}  {'slot':<{name_w}}  {'token mtime':<{det_w}}  path")
    for state, name, detail, tok in rows:
        mark = _MARK.get(state, '[?]')
        print(f"  {mark} {state:<7}  {name:<{name_w}}  {detail:<{det_w}}  {tok}")

    if len(slots) > max_items:
        print(f"\n... +{len(slots) - max_items} more slot(s) (raise -n/--max)")

    empties = [r[1] for r in rows if r[0] in ('empty', 'no-path')]
    stales = [r[1] for r in rows if r[0] == 'stale']
    filled = sum(1 for r in rows if r[0] == 'filled')
    print(f"\n# {filled} filled | {len(stales)} stale | {len(empties)} empty")
    if empties:
        print(f"# Next: python scripts/connectors/wallet.py login {empties[0]}"
              "   (mint its token — interactive, one-time; NEXT slice)")
    elif stales:
        print(f"# Next: re-mint the stale slot — python "
              f"scripts/connectors/wallet.py login {stales[0]}")
    else:
        print("# Next: wallet fully minted — nothing to log into.")


def login_guard(slot):
    """login is the NEXT slice, gated on external Cloud-console registration.
    This slice is read-only: refuse honestly rather than open a consent flow.
    """
    who = slot or '<slot>'
    die(
        f"wallet login {who} is not wired in this slice.\n"
        "The token-minting walk needs the OAuth client registered in the Cloud\n"
        "console first; it is the next Tier-2 slice. Until then, mint via the\n"
        "connector's own interactive first-run (e.g. `python scripts/connectors/\n"
        "sheets.py` or `python scripts/connectors/gmail.py <you@example.com>`).",
        code=2,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Read-only scoreboard for the Pipulate connector wallet.")
    parser.add_argument('command', nargs='?', default=None,
                        help="omit for the SCOREBOARD; 'login <slot>' is the "
                             "next slice (not wired this turn).")
    parser.add_argument('slot', nargs='?', default=None,
                        help="slot name for 'login' (e.g. gmail).")
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Max slots to show per THE PROBE ECONOMY RULE '
                             '(default: 25).')
    parser.add_argument('--stale-days', type=int, default=7,
                        help='mtime age (days) above which a token reads stale '
                             '(default: 7 — the Testing-mode refresh cliff).')
    args = parser.parse_args()

    if args.command in (None, 'scoreboard', 'board', 'status'):
        scoreboard(load_wallet(), args.max, args.stale_days)
    elif args.command == 'login':
        login_guard(args.slot)
    else:
        die(f"Unknown command: {args.command}\n"
            "Usage: wallet.py                 (scoreboard)\n"
            "       wallet.py login <slot>    (next slice — not wired)")


if __name__ == '__main__':
    main()
