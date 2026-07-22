#!/usr/bin/env python3
# scripts/connectors/wallet.py
"""
wallet.py — Read-only scoreboard for the Pipulate connector wallet.

Golden-path modes, auto-detected from the leading positional argument:

  python scripts/connectors/wallet.py                 # SCOREBOARD: stat every oauth_token_file slot (filled / stale / empty)
  python scripts/connectors/wallet.py login <slot>    # LOGIN: mint/re-mint that slot's token via its connector's own OAuth walk

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
              "   (mint its token — interactive, one-time)")
    elif stales:
        print(f"# Next: re-mint the stale slot — python "
              f"scripts/connectors/wallet.py login {stales[0]}")
    else:
        print("# Next: wallet fully minted — nothing to log into.")


def resolve_creds_path(slot):
    """Resolved, ~-expanded credentials path for an oauth_token_file slot,
    honoring any env override the wallet declares as 'overrides
    paths.credentials' — the mirror of resolve_token_path. None when absent.
    """
    for env_key, desc in (slot.get('env') or {}).items():
        if 'paths.credentials' in str(desc) and os.environ.get(env_key):
            return str(Path(os.environ[env_key]).expanduser())
    raw = (slot.get('paths') or {}).get('credentials')
    return str(Path(raw).expanduser()) if raw else None


def _env_override_key(slot, needle):
    """The slot's declared env-override variable whose description points at
    `needle` (e.g. 'paths.token'), so login can steer the reused connector at
    the wallet-declared path. None when the slot declares no such override.
    """
    for env_key, desc in (slot.get('env') or {}).items():
        if needle in str(desc):
            return env_key
    return None


def login(slot_name, stale_days):
    """Mint (or re-mint) exactly ONE slot's OAuth token by REUSING that
    connector's own get_service() walk — never re-implementing the flow.

    The slot name IS the connector module name: `gmail` -> gmail.py,
    `sheets` -> sheets.py, sitting beside this file. We resolve the slot's
    credentials + token paths from the wallet, point the connector at them via
    its declared env overrides, then hand off to its get_service(), which owns
    the real SCOPES and the exact InstalledAppFlow.from_client_secrets_file ->
    run_local_server(port=0) -> creds.to_json() walk (plus its own headless-
    refresh, non-TTY, and missing-credentials gates). We touch ONLY this slot:
    no other slot's token is read, and the board is not rewritten — we just
    re-stat this one slot and print its single row afterward.
    """
    if not slot_name:
        die("Usage: wallet.py login <slot>   (e.g. wallet.py login gmail)\n"
            "Run the bare scoreboard to see which slots exist and their state.")

    wallet = load_wallet()
    slot = wallet.get(slot_name)
    if not isinstance(slot, dict):
        oauth = [n for n, c in wallet.items()
                 if isinstance(c, dict) and c.get('auth') == _OAUTH_KIND]
        die(f"No slot '{slot_name}' in {Path(WALLET_PATH).expanduser()}.\n"
            f"oauth_token_file slots you can log into: "
            f"{', '.join(oauth) or '(none)'}")

    if slot.get('auth') != _OAUTH_KIND:
        die(f"Slot '{slot_name}' is auth={slot.get('auth')!r}, not "
            f"{_OAUTH_KIND!r}.\n"
            "login drives the browser OAuth mint, which only oauth_token_file\n"
            "slots use. This slot authenticates by token/basic-auth env vars —\n"
            "set those in your env or .env; there is nothing to mint here.",
            code=2)

    creds_path = resolve_creds_path(slot)
    token_path = resolve_token_path(slot)
    if not token_path:
        die(f"Slot '{slot_name}' declares no paths.token — cannot mint. "
            "Fix the wallet entry first.")

    # Gate hard on the OAuth client file, with the Cloud-console breadcrumb.
    # A live headless refresh would not strictly need it, but a first mint or a
    # revoked-refresh re-mint does — so surface the path now, not mid-browser.
    if not creds_path or not Path(creds_path).exists():
        die(f"Missing credentials.json for '{slot_name}' at: "
            f"{creds_path or '(no paths.credentials declared)'}\n"
            "Download the Desktop-app OAuth client JSON from the Google Cloud\n"
            "Console and place it there (the same client the other Google\n"
            "connectors use), then re-run:\n"
            f"    python scripts/connectors/wallet.py login {slot_name}")

    # The connector module of the SAME name lives beside this file.
    connector_file = Path(__file__).resolve().parent / f"{slot_name}.py"
    if not connector_file.exists():
        die(f"No connector module for slot '{slot_name}' at: {connector_file}\n"
            "The slot name must match its connector filename to reuse its walk.")

    # Steer the reused connector at THIS slot's resolved paths via the env
    # overrides the wallet itself declares, so a non-default wallet still mints
    # to the right place. No-ops when they already equal the connector default.
    ck = _env_override_key(slot, 'paths.credentials')
    tk = _env_override_key(slot, 'paths.token')
    if ck:
        os.environ[ck] = creds_path
    if tk:
        os.environ[tk] = token_path

    before_state, _ = classify(token_path, stale_days)
    print(f"# wallet login {slot_name} — reusing {connector_file.name}'s own "
          "OAuth walk (this slot only)")
    print(f"# credentials : {creds_path}")
    print(f"# token       : {token_path}  [{before_state} before]\n")

    # REUSE, don't re-implement: load the connector by file and call its own
    # get_service(), which refreshes headlessly or browser-mints per its real
    # SCOPES and writes exactly this slot's token through its own _save_token.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        f"_wallet_connector_{slot_name}", connector_file)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        die(f"Could not load connector '{connector_file.name}': {e}")

    get_service = getattr(mod, 'get_service', None)
    if not callable(get_service):
        die(f"Connector '{connector_file.name}' exposes no get_service() to "
            "reuse; refusing to re-implement its OAuth flow here.")

    try:
        get_service()  # refresh headlessly, or browser-mint on a TTY
    except SystemExit:
        raise  # connector already spoke (non-TTY / missing creds); keep its code
    except Exception as e:
        die(f"OAuth walk for '{slot_name}' failed: {e}\n"
            "If a stale refresh token was revoked (the Testing-mode 7-day\n"
            "cliff), re-run this in a real terminal to browser-mint a fresh one.")

    # Re-stat ONLY this slot and print its single board row — no wallet
    # rewrite, no other slot's token touched.
    after_state, detail = classify(token_path, stale_days)
    mark = _MARK.get(after_state, '[?]')
    print("\n# minted — this slot now reads:")
    print(f"  {mark} {after_state:<7}  {slot_name}  {detail}  {token_path}")
    if after_state == 'filled':
        print("# Done. Re-run the bare scoreboard for the whole board.")
    else:
        print(f"# Note: slot still reads '{after_state}' — "
              "check the walk output above.")


def main():
    parser = argparse.ArgumentParser(
        description="Read-only scoreboard for the Pipulate connector wallet.")
    parser.add_argument('command', nargs='?', default=None,
                        help="omit for the SCOREBOARD; 'login <slot>' mints "
                             "or re-mints that slot's OAuth token.")
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
        login(args.slot, args.stale_days)
    else:
        die(f"Unknown command: {args.command}\n"
            "Usage: wallet.py                 (scoreboard)\n"
            "       wallet.py login <slot>    (mint/re-mint one slot's token)")


if __name__ == '__main__':
    main()
