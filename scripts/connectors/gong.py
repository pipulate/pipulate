#!/usr/bin/env python3
# scripts/connectors/wallet.py
"""
wallet.py — Read-only scoreboard for the Pipulate connector wallet.

Golden-path modes, auto-detected from the leading positional argument:

  python scripts/connectors/wallet.py                 # SCOREBOARD: warm-state of EVERY connector slot, all auth kinds
  python scripts/connectors/wallet.py login <slot>    # LOGIN: mint/re-mint that slot's OAuth token via its connector's own walk

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/wallet.py
  ! python scripts/connectors/wallet.py -n 5

This is the GENERALIZATION of each connector's no-argument identity() walk
(see sheets.py) lifted from ONE connector to the WHOLE wallet: instead of a
single connector reporting its own wiring, wallet.py reads
~/.config/pipulate/connectors.json (override: PIPULATE_WALLET) and reports
every slot at once, so a glance tells you which sessions are warm, which have
gone stale, and which have never been warmed.

SCOREBOARD is strictly READ-ONLY and OFFLINE. It reads connectors.json (names
and paths only), os.stat()s token files / browser-profile dirs, and checks
whether each slot's required env-var NAMES are visible (in os.environ or as a
`NAME=` line in ~/.config/pipulate/.env). It NEVER opens a token's bytes, NEVER
reads a secret's VALUE (the wallet's own _rule: names and paths ONLY), NEVER
touches the network. Warmth is an honest heuristic, never a validity proof — a
present token can still be revoked; a present env var can still be wrong.

FIVE auth kinds, each with its own honest warmth rule and its own way to warm:

  oauth_token_file    file at paths.token; stale by mtime > --stale-days.
                      WARM: `wallet login <slot>` (browser-mint / headless refresh).
  service_account_file file at paths.service_account; present = filled (keys
                      don't rotate on mtime, so no stale window).
                      WARM: paste the downloaded service-account JSON at its path.
  bearer_token        one required env-var NAME (e.g. BOTIFY_API_TOKEN).
                      WARM: export the var, or add it to ~/.config/pipulate/.env.
  basic_auth          several required env-var NAMES (URL + EMAIL + TOKEN).
                      filled = all present, partial = some, empty = none.
                      WARM: export the vars, or add them to ~/.config/pipulate/.env.
  browser_session     persistent Chrome profile dir at
                      $PIPULATE_ROOT/data/uc_profiles/<name> (the dir weblogin.py
                      writes and scraper_tools.py reads); stale by mtime.
                      WARM: `python scripts/weblogin.py <site> --profile <name>`.

WHY mtime, WHY --stale-days 7 (oauth / browser_session): connectors rewrite the
token file on every successful refresh (see _save_token after creds.refresh),
and Chrome rewrites the profile dir on every session, so mtime tracks "last
warmed", not "first minted". Google OAuth clients in *Testing* status expire
refresh tokens 7 days after issuance, so 7 days is the tightest real cliff and
the honest default warning window. A slot not rewritten in a week is the one
most likely to have lapsed. Heuristic, never proof.

States:
  filled   — warm and recent (file/dir present within --stale-days, or all
             required env vars visible).
  stale    — file/dir present but last touched > --stale-days ago.
  partial  — a multi-secret slot (basic_auth) with some, but not all, required
             env vars visible.
  empty    — nothing to warm from: missing/0-byte file, missing profile dir, or
             no required env vars visible.
  no-path  — slot's auth kind needs a path it doesn't declare (a wallet config
             error — surfaced, not hidden).
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

WALLET_PATH = os.environ.get('PIPULATE_WALLET') or str(
    Path.home() / '.config' / 'pipulate' / 'connectors.json')

# Repo root: wallet.py lives at <root>/scripts/connectors/wallet.py, so parents[2]
# is the root. PIPULATE_ROOT overrides it, matching weblogin.py's anchor so the
# browser-profile path we stat is the exact dir weblogin writes and the scraper
# reads.
REPO_ROOT = Path(os.environ.get('PIPULATE_ROOT') or Path(__file__).resolve().parents[2])

# The dotenv the paste-key family may live in, out of git reach, beside the wallet.
DOTENV_PATH = Path(WALLET_PATH).expanduser().parent / '.env'

_OAUTH_KIND = 'oauth_token_file'
_SVC_KIND = 'service_account_file'
_BEARER_KIND = 'bearer_token'
_BASIC_KIND = 'basic_auth'
_BROWSER_KIND = 'browser_session'

# Kinds warmed by the interactive `login` OAuth walk. Everything else is warmed
# a different way, which classify()/login() name explicitly.
_LOGINABLE = {_OAUTH_KIND}

_KIND_ABBR = {
    _OAUTH_KIND: 'oauth',
    _SVC_KIND: 'svc-acct',
    _BEARER_KIND: 'bearer',
    _BASIC_KIND: 'basic',
    _BROWSER_KIND: 'browser',
}

_MARK = {'filled': '[x]', 'stale': '[~]', 'partial': '[-]',
         'empty': '[ ]', 'no-path': '[!]'}


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


# ---------------------------------------------------------------------------
# Path / env resolution — names and paths ONLY, never a secret value.
# ---------------------------------------------------------------------------
def _resolve_pathish(slot, key, needle):
    """Resolved, ~-expanded path for `paths.<key>`, honoring any env override the
    slot declares as 'overrides paths.<key>'. None when the slot declares none.
    """
    for env_key, desc in (slot.get('env') or {}).items():
        if needle in str(desc) and os.environ.get(env_key):
            return str(Path(os.environ[env_key]).expanduser())
    raw = (slot.get('paths') or {}).get(key)
    return str(Path(raw).expanduser()) if raw else None


def resolve_token_path(slot):
    return _resolve_pathish(slot, 'token', 'paths.token')


def resolve_creds_path(slot):
    return _resolve_pathish(slot, 'credentials', 'paths.credentials')


def resolve_service_account_path(slot):
    return _resolve_pathish(slot, 'service_account', 'paths.service_account')


def resolve_profile_path(slot):
    """Browser-session profile dir under $PIPULATE_ROOT/data/uc_profiles/<name>.
    paths.profile may be an absolute path, a repo-relative path, or a bare
    profile name; all resolve to the dir weblogin.py writes.
    """
    for env_key, desc in (slot.get('env') or {}).items():
        if 'paths.profile' in str(desc) and os.environ.get(env_key):
            raw = os.environ[env_key]
            break
    else:
        raw = (slot.get('paths') or {}).get('profile')
    if not raw:
        return None
    p = Path(raw).expanduser()
    if p.is_absolute():
        return str(p)
    if len(p.parts) == 1:  # bare profile name
        return str(REPO_ROOT / 'data' / 'uc_profiles' / p)
    return str(REPO_ROOT / p)  # repo-relative path


def _dotenv_keys():
    """The set of env-var NAMES declared in ~/.config/pipulate/.env — names only,
    values never read. Empty set when no .env exists. Cached per process.
    """
    if getattr(_dotenv_keys, '_cache', None) is not None:
        return _dotenv_keys._cache
    keys = set()
    try:
        for line in DOTENV_PATH.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name = line.split('=', 1)[0].strip()
            if name.lower().startswith('export '):
                name = name[len('export '):].strip()
            if name:
                keys.add(name)
    except OSError:
        pass
    _dotenv_keys._cache = keys
    return keys


def _env_source(name):
    """Where a required env NAME is visible, or None. 'env' if set & non-empty in
    os.environ, else 'dotenv' if declared in ~/.config/pipulate/.env, else None.
    Never reads or returns the secret VALUE.
    """
    if os.environ.get(name):
        return 'env'
    if name in _dotenv_keys():
        return 'dotenv'
    return None


def _required_env_names(slot):
    """Required env-var NAMES for a bearer/basic slot: every declared env whose
    description does NOT contain 'optional'. `env` blocks are documentation-as-
    data (README), so this reads intent without a second config surface.
    """
    return [name for name, desc in (slot.get('env') or {}).items()
            if 'optional' not in str(desc).lower()]


# ---------------------------------------------------------------------------
# Classification — one function, dispatched by auth kind. os.stat / env only.
# ---------------------------------------------------------------------------
def _classify_file(path, stale_days, missing_detail):
    if path is None:
        return 'no-path', 'slot declares no path'
    p = Path(path)
    if not p.exists():
        return 'empty', missing_detail
    try:
        st = p.stat()
    except OSError as e:
        return 'empty', f'unstatable ({e})'
    if st.st_size == 0:
        return 'empty', '0 bytes (poisoned/truncated)'
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    age = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400.0
    detail = f"{mtime.strftime('%Y-%m-%d')} ({age:.0f}d ago)"
    return ('stale' if age > stale_days else 'filled'), detail


def _classify_dir(path, stale_days):
    if path is None:
        return 'no-path', 'slot declares no paths.profile'
    p = Path(path)
    if not p.exists() or not any(p.iterdir() if p.is_dir() else []):
        return 'empty', 'no warmed profile (run weblogin)'
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    age = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400.0
    detail = f"{mtime.strftime('%Y-%m-%d')} ({age:.0f}d ago)"
    return ('stale' if age > stale_days else 'filled'), detail


def _classify_env(slot):
    required = _required_env_names(slot)
    if not required:
        return 'no-path', 'slot declares no required env'
    present, missing = [], []
    src = None
    for name in required:
        s = _env_source(name)
        if s:
            present.append(name)
            src = src or s
        else:
            missing.append(name)
    if not present:
        return 'empty', f"unset: {', '.join(missing)}"
    if missing:
        return 'partial', f"set via {src}; missing {', '.join(missing)}"
    return 'filled', f"{len(present)} var(s) via {src}"


def classify(slot, stale_days):
    """(state, detail, target) for any slot, dispatched by auth kind. target is the
    path or env-source the state was read from, for the board's rightmost column.
    """
    kind = slot.get('auth')
    if kind == _OAUTH_KIND:
        tok = resolve_token_path(slot)
        state, detail = _classify_file(tok, stale_days, 'not yet minted')
        return state, detail, tok or '(no path)'
    if kind == _SVC_KIND:
        sa = resolve_service_account_path(slot)
        # Service-account keys don't rotate on mtime; present == warm, no stale.
        state, detail = _classify_file(sa, float('inf'), 'not yet placed')
        return state, detail, sa or '(no path)'
    if kind == _BROWSER_KIND:
        prof = resolve_profile_path(slot)
        state, detail = _classify_dir(prof, stale_days)
        return state, detail, prof or '(no path)'
    if kind in (_BEARER_KIND, _BASIC_KIND):
        state, detail = _classify_env(slot)
        return state, detail, 'env / .env'
    return 'no-path', f'unknown auth kind {kind!r}', '(unknown)'


def _how_to_warm(name, slot):
    """The exact one-liner that warms this slot, per its auth kind. This is the
    'name anything it genuinely can't warm' contract: every un-mintable kind
    still gets a concrete instruction, not silence.
    """
    kind = slot.get('auth')
    if kind == _OAUTH_KIND:
        return f"python scripts/connectors/wallet.py login {name}"
    if kind == _SVC_KIND:
        sa = resolve_service_account_path(slot) or '(declare paths.service_account)'
        return f"place the service-account JSON at {sa}"
    if kind == _BROWSER_KIND:
        prof = (slot.get('paths') or {}).get('profile') or name
        site = slot.get('defaults', {}).get('site', f'{name}.com')
        return f"python scripts/weblogin.py {site} --profile {prof}"
    if kind in (_BEARER_KIND, _BASIC_KIND):
        need = _required_env_names(slot)
        return (f"export {', '.join(need)}  "
                f"(or add to {DOTENV_PATH})")
    return f"unknown auth kind {kind!r} — fix the wallet entry"


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------
def scoreboard(wallet, max_items, stale_days):
    """Print the read-only wallet board for EVERY connector slot, all auth kinds."""
    slots = [(name, cfg) for name, cfg in wallet.items()
             if not name.startswith('_') and isinstance(cfg, dict) and cfg.get('auth')]

    print("# wallet.py — connector warm-state scoreboard (read-only, offline)")
    print(f"# wallet: {Path(WALLET_PATH).expanduser()}")
    print(f"# stale after: {stale_days}d (mtime heuristic, not a validity proof)\n")

    if not slots:
        print("(no connector slots in this wallet)")
        print("\n# Next: add a slot to connectors.json, then re-run this scoreboard.")
        return

    shown = slots[:max_items]
    rows = []
    for name, cfg in shown:
        state, detail, target = classify(cfg, stale_days)
        rows.append((state, _KIND_ABBR.get(cfg.get('auth'), '?'), name, detail, target))

    kind_w = max(len('kind'), *(len(r[1]) for r in rows))
    name_w = max(len('slot'), *(len(r[2]) for r in rows))
    det_w = max(len('detail'), *(len(r[3]) for r in rows))
    print(f"     {'state':<7}  {'kind':<{kind_w}}  {'slot':<{name_w}}  "
          f"{'detail':<{det_w}}  target")
    for state, kind, name, detail, target in rows:
        mark = _MARK.get(state, '[?]')
        print(f"  {mark} {state:<7}  {kind:<{kind_w}}  {name:<{name_w}}  "
              f"{detail:<{det_w}}  {target}")

    if len(slots) > max_items:
        print(f"\n... +{len(slots) - max_items} more slot(s) (raise -n/--max)")

    filled = sum(1 for r in rows if r[0] == 'filled')
    stales = [r[2] for r in rows if r[0] == 'stale']
    partial = [r[2] for r in rows if r[0] == 'partial']
    empties = [(r[2], r[0]) for r in rows if r[0] in ('empty', 'no-path')]
    print(f"\n# {filled} filled | {len(stales)} stale | "
          f"{len(partial)} partial | {len(empties)} empty")

    # Fresh-install nudge: if NOTHING is warm, this is a just-installed wallet.
    # This is the post-`curl | bash` Yen Sid line — warm the wallet to begin.
    if filled == 0 and not stales and not partial:
        print("\n# 🧙 Fresh wallet — nothing warmed yet. Warm your first slot:")
        first, cfg = shown[0][0], shown[0][1]
        print(f"#   {_how_to_warm(first, cfg)}")
        return

    # Otherwise point at the single most-actionable next warm, empties first.
    def _lookup(nm):
        return dict(shown)[nm]
    if empties:
        nm = empties[0][0]
        print(f"# Next: warm '{nm}' — {_how_to_warm(nm, _lookup(nm))}")
    elif partial:
        nm = partial[0]
        print(f"# Next: finish '{nm}' — {_how_to_warm(nm, _lookup(nm))}")
    elif stales:
        nm = stales[0]
        print(f"# Next: re-warm the stale slot '{nm}' — {_how_to_warm(nm, _lookup(nm))}")
    else:
        print("# Next: wallet fully warmed — nothing to do.")


# ---------------------------------------------------------------------------
# Login (OAuth mint) — unchanged reuse-don't-reimplement walk, with per-kind
# guidance for the kinds login cannot warm.
# ---------------------------------------------------------------------------
def _env_override_key(slot, needle):
    for env_key, desc in (slot.get('env') or {}).items():
        if needle in str(desc):
            return env_key
    return None


def login(slot_name, stale_days):
    """Mint (or re-mint) exactly ONE oauth_token_file slot by REUSING that
    connector's own get_service() walk — never re-implementing the flow. For any
    other auth kind, print exactly how THAT kind is warmed and exit — the wallet
    names what it cannot mint rather than pretending it can.
    """
    if not slot_name:
        die("Usage: wallet.py login <slot>   (e.g. wallet.py login gmail)\n"
            "Run the bare scoreboard to see which slots exist and their state.")

    wallet = load_wallet()
    slot = wallet.get(slot_name)
    if not isinstance(slot, dict):
        loginable = [n for n, c in wallet.items()
                     if isinstance(c, dict) and c.get('auth') in _LOGINABLE]
        die(f"No slot '{slot_name}' in {Path(WALLET_PATH).expanduser()}.\n"
            f"Slots you can `login` (OAuth mint): {', '.join(loginable) or '(none)'}")

    if slot.get('auth') not in _LOGINABLE:
        die(f"Slot '{slot_name}' is auth={slot.get('auth')!r}; `login` only mints "
            f"{sorted(_LOGINABLE)} slots.\n"
            f"This slot warms differently:\n"
            f"    {_how_to_warm(slot_name, slot)}",
            code=2)

    creds_path = resolve_creds_path(slot)
    token_path = resolve_token_path(slot)
    if not token_path:
        die(f"Slot '{slot_name}' declares no paths.token — cannot mint. "
            "Fix the wallet entry first.")

    if not creds_path or not Path(creds_path).exists():
        die(f"Missing credentials.json for '{slot_name}' at: "
            f"{creds_path or '(no paths.credentials declared)'}\n"
            "Download the Desktop-app OAuth client JSON from the Google Cloud\n"
            "Console and place it there (the same client the other Google\n"
            "connectors use), then re-run:\n"
            f"    python scripts/connectors/wallet.py login {slot_name}")

    connector_file = Path(__file__).resolve().parent / f"{slot_name}.py"
    if not connector_file.exists():
        die(f"No connector module for slot '{slot_name}' at: {connector_file}\n"
            "The slot name must match its connector filename to reuse its walk.")

    ck = _env_override_key(slot, 'paths.credentials')
    tk = _env_override_key(slot, 'paths.token')
    if ck:
        os.environ[ck] = creds_path
    if tk:
        os.environ[tk] = token_path

    before_state, _, _ = classify(slot, stale_days)
    print(f"# wallet login {slot_name} — reusing {connector_file.name}'s own "
          "OAuth walk (this slot only)")
    print(f"# credentials : {creds_path}")
    print(f"# token       : {token_path}  [{before_state} before]\n")

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
        get_service()
    except SystemExit:
        raise
    except Exception as e:
        die(f"OAuth walk for '{slot_name}' failed: {e}\n"
            "If a stale refresh token was revoked (the Testing-mode 7-day\n"
            "cliff), re-run this in a real terminal to browser-mint a fresh one.")

    after_state, detail, target = classify(slot, stale_days)
    mark = _MARK.get(after_state, '[?]')
    print("\n# minted — this slot now reads:")
    print(f"  {mark} {after_state:<7}  {slot_name}  {detail}  {target}")
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
                        help='mtime age (days) above which a token/profile reads '
                             'stale (default: 7 — the Testing-mode refresh cliff).')
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
