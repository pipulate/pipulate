#!/usr/bin/env python3
# scripts/connectors/wallet.py
"""
wallet.py — Connect your accounts and see which credentials are live.

Golden-path modes, auto-detected from the leading positional argument:

  python scripts/connectors/wallet.py                 # SCOREBOARD: stat EVERY slot, whatever its auth kind (OFFLINE)
  python scripts/connectors/wallet.py check [<slot>]  # CHECK: the red/green game — one bounded probe per enrolled slot
  python scripts/connectors/wallet.py warm [<slot>]   # WARM: fix whatever is cold, dispatched per auth kind
  python scripts/connectors/wallet.py login <slot>    # LOGIN: mint an oauth slot, or NAME how any other kind is warmed

Designed to be dropped into adhoc.txt as a `!` chisel-strike, e.g.:

  ! python scripts/connectors/wallet.py
  ! python scripts/connectors/wallet.py -n 5

This is the GENERALIZATION of each connector's no-argument identity() walk
lifted from ONE connector to the WHOLE wallet. It reads
~/.config/pipulate/connectors.json (override: PIPULATE_WALLET) and reports
every slot at once — across all FIVE auth kinds the wallet actually holds —
so a glance tells you which sessions are live, which have gone stale, which
have never been warmed, and (crucially) which the wallet genuinely CANNOT
warm for you and why.

SCOREBOARD is strictly READ-ONLY and OFFLINE — the CHECK verb is the one lane
in this file that touches the network, deliberately kept a separate verb so
the offline board still works on a plane. SCOREBOARD never opens a token's
bytes, never touches the network, never reads credentials.json /
client_secret. It learns a slot's state from cheap, local evidence only:

  oauth_token_file      os.stat() the token file → mtime staleness
                        (gmail, sheets). Google *Testing*-mode refresh tokens
                        lapse 7d after issue; connectors rewrite the file on
                        every refresh, so mtime tracks "last refreshed".
  service_account_file  os.stat() the key file → present/non-empty (gsc).
                        SA keys don't hit the 7d cliff, so NO mtime staleness:
                        present is filled, missing is empty. Honest either way.
  bearer_token          is the required env var NAME set in THIS process's
                        environment? (botify, slack). A "paste" kind.
  basic_auth            are the required env var NAMES set? (confluence, jira,
                        gong). Also a "paste" kind.
  browser_session       os.stat() the persistent Chrome profile dir
                        data/uc_profiles/<name> that weblogin.py warms
                        (botify_browser, semrush) → mtime staleness, because
                        sites DO expire browser sessions.

HONEST HEURISTICS, stated plainly (a clean caveat is a valid receipt):
  - `stale` is an mtime guess, never a validity proof. Only a live call can
    prove a session/token truly live; SCOREBOARD refuses to make that call,
    which is exactly why CHECK exists as a separate verb rather than as a
    flag that would quietly change what a familiar command does.
  - env-var kinds read the process environment AND the vault
    (~/.config/pipulate/.env) by NAME. What they cannot read is a connector's
    own fallback logic: the wallet reports each slot's DECLARED variable
    names, so a connector that accepts CONFLUENCE_URL where the wallet
    declares CONFLUENCE_BASE_URL reads emptier than it is. Convicted
    2026-07-23 by a FALSE RED. When a row disagrees with reality, suspect the
    declared NAME before you suspect the credential.
  - CHECK's browser_session rows read cookie METADATA only (never a decrypted
    value) and green on a live HttpOnly cookie for the slot's apex domain.
    HttpOnly is a structural stand-in for "a server set this", not proof of a
    working session: a stale-but-unexpired session cookie still greens. It is
    the cheapest honest discriminator that does not launch a browser.

States (per slot):
  filled   — warmed and fresh (or, for env kinds, all required vars present).
  stale    — present but last touched > --stale-days ago (mtime kinds only).
  partial  — some but not all required env vars present (env kinds only).
  empty    — missing / 0-bytes / no required var set. Needs warming.
  no-path  — slot's kind needs a path/profile it doesn't declare (config error).
  unknown  — auth kind not recognized by this wallet (surfaced, never hidden).
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

WALLET_PATH = os.environ.get('PIPULATE_WALLET') or str(
    Path.home() / '.config' / 'pipulate' / 'connectors.json')

# The one file where paste-kind secrets come to rest: beside the wallet, never
# in the repo, never in git, chmod 0600 on first write. `warm` writes NAMES and
# VALUES here; the SCOREBOARD still reads NAMES only and never opens a value.
DOTENV_PATH = Path(os.environ.get('PIPULATE_DOTENV') or
                   Path.home() / '.config' / 'pipulate' / '.env').expanduser()

# Repo root anchors browser_session profiles (data/uc_profiles/<name>), the
# SAME directory weblogin.py writes. weblogin honors PIPULATE_ROOT then falls
# back to its own parent.parent; wallet.py lives one level deeper
# (scripts/connectors/), so parents[2] is the repo root. Keep in sync.
REPO_ROOT = Path(os.environ.get('PIPULATE_ROOT') or Path(__file__).resolve().parents[2])

# Auth kinds — these strings MUST match connectors.json exactly.
_OAUTH_KIND = 'oauth_token_file'       # mint + auto-refresh (gmail, sheets)
_SERVICE_KIND = 'service_account_file'  # a key file on disk (gsc)
_BEARER_KIND = 'bearer_token'          # paste: single API token (botify, slack)
_BASIC_KIND = 'basic_auth'             # paste: user + API token (confluence, jira, gong)
_BROWSER_KIND = 'browser_session'      # weblogin persistent profile (botify_browser, semrush)

_FILE_KINDS = (_OAUTH_KIND, _SERVICE_KIND)
_ENV_KINDS = (_BEARER_KIND, _BASIC_KIND)
_MTIME_KINDS = (_OAUTH_KIND, _BROWSER_KIND)  # kinds whose freshness decays with time

_KIND_LABEL = {
    _OAUTH_KIND: 'oauth',
    _SERVICE_KIND: 'svc-acct',
    _BEARER_KIND: 'bearer',
    _BASIC_KIND: 'basic',
    _BROWSER_KIND: 'browser',
}

_MARK = {'filled': '[x]', 'stale': '[~]', 'partial': '[/]', 'empty': '[ ]',
         'no-path': '[!]', 'unknown': '[?]'}


def die(msg, code=1):
    sys.stderr.write(msg.rstrip('\n') + '\n')
    sys.exit(code)


def load_wallet():
    """Read connectors.json (names and paths only).

    ABSENT is not BROKEN. The moment boot_menu's door 2 names `warm`, this
    function is what a stranger with zero credentials reaches first -- and a
    terse die() there makes their first thirty seconds a crash rather than a
    start state. No wallet prints the cold-start card and exits 0, because an
    empty board is the beginning of the game and not a fault in it.

    A wallet that EXISTS and will not parse still fails loud: that is a real
    fault, and guessing past a malformed credential map is worse than
    stopping. Absent gets a welcome; corrupt gets a wall.
    """
    path = Path(WALLET_PATH).expanduser()
    if not path.exists():
        print("# no wallet yet -- that is the start state, not an error.")
        print(f"# A wallet is one JSON file: {path}")
        print("# Keys are slot names. Each slot declares an `auth` kind plus the")
        print("# env var NAMES or file paths it needs -- names only, never secrets.")
        print("# Smallest wallet that plays:")
        print('#   {"botify": {"auth": "bearer_token",')
        print('#               "env": {"BOTIFY_API_TOKEN": "required; API token"}}}')
        print("# Write that, run this again for one red row, then "
              "`wallet.py warm botify`.")
        sys.exit(0)
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        die(f"Unreadable wallet at {path}: {e}")


def _env_override_path(slot, needle):
    """A path the slot declares, honoring any env override whose description
    points at `needle` (e.g. 'paths.token'), mirroring the connectors' own
    `os.environ.get(...) or <path>`. Returns an expanded str, or None."""
    for env_key, desc in (slot.get('env') or {}).items():
        if needle in str(desc) and os.environ.get(env_key):
            return str(Path(os.environ[env_key]).expanduser())
    return None


def resolve_path(slot, key, needle):
    """Resolved, ~-expanded path for paths.<key>, honoring a declared env
    override described as `needle`. None when the slot declares no such path."""
    override = _env_override_path(slot, needle)
    if override:
        return override
    raw = (slot.get('paths') or {}).get(key)
    return str(Path(raw).expanduser()) if raw else None


def _required_env_vars(slot):
    """The env var NAMES this slot declares as required. Heuristic: any var
    whose description says 'required' (and not 'optional'); if none is so
    marked, every declared var is treated as required. Documentation-as-data,
    read straight from the wallet — never a hardcoded per-connector list."""
    env = slot.get('env') or {}
    req = [name for name, desc in env.items()
           if 'required' in str(desc).lower() and 'optional' not in str(desc).lower()]
    return req or list(env.keys())


def _stat_state(path, stale_days, mtime_matters):
    """(state, detail) from an os.stat only — never opens the bytes.
    mtime_matters=False → present/non-empty is always 'filled' (no 7d cliff)."""
    if path is None:
        return 'no-path', 'slot declares no path'
    p = Path(path)
    if not p.exists():
        return 'empty', 'not present'
    try:
        st = p.stat()
    except OSError as e:
        return 'empty', f'unstatable ({e})'
    if p.is_file() and st.st_size == 0:
        return 'empty', '0 bytes (poisoned/truncated)'
    if p.is_dir() and not any(p.iterdir()):
        return 'empty', 'profile dir empty (never warmed)'
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400.0
    stamp = f"{mtime.strftime('%Y-%m-%d')} ({age_days:.0f}d ago)"
    if not mtime_matters:
        return 'filled', stamp
    return ('stale' if age_days > stale_days else 'filled'), stamp


def _dotenv_names():
    """The env-var NAMES declared in DOTENV_PATH — the names-only projection
    of _dotenv_pairs, because the SCOREBOARD must never touch a value. Empty
    set when there is no .env. Cached per process, and the cache is
    invalidated by _save_env so the board re-reads what warm wrote."""
    if getattr(_dotenv_names, '_cache', None) is not None:
        return _dotenv_names._cache
    _dotenv_names._cache = set(_dotenv_pairs())
    return _dotenv_names._cache


def _env_source(name):
    """Where a required var is visible — 'env', 'dotenv', or None. Never reads
    or returns the secret VALUE (the wallet's names-and-paths-only rule)."""
    if os.environ.get(name):
        return 'env'
    if name in _dotenv_names():
        return 'dotenv'
    return None


def _env_state(slot):
    """(state, detail) for a paste kind: is each required env var NAME visible
    in THIS process, or declared in DOTENV_PATH? Reading the .env is what closes
    the old "reads emptier than it is" caveat — a secret parked in
    ~/.config/pipulate/.env now counts, because that is where `warm` puts it."""
    req = _required_env_vars(slot)
    if not req:
        return 'no-path', 'slot declares no env vars'
    seen = {v: _env_source(v) for v in req}
    present = [v for v in req if seen[v]]
    missing = [v for v in req if not seen[v]]
    if not present:
        return 'empty', f"unset: {', '.join(req)}"
    where = ', '.join(f"{v} ({seen[v]})" for v in present)
    if missing:
        return 'partial', f"set: {where} | unset: {', '.join(missing)}"
    return 'filled', f"set: {where}"


def classify_slot(name, cfg, stale_days):
    """Dispatch on the slot's auth kind. Returns (state, kind, detail, locator).
    The single place that knows how each of the five kinds proves itself."""
    kind = cfg.get('auth')
    if kind == _OAUTH_KIND:
        tok = resolve_path(cfg, 'token', 'paths.token')
        state, detail = _stat_state(tok, stale_days, mtime_matters=True)
        return state, kind, detail, tok or '(no token path)'
    if kind == _SERVICE_KIND:
        key = resolve_path(cfg, 'service_account', 'paths.service_account')
        state, detail = _stat_state(key, stale_days, mtime_matters=False)
        return state, kind, detail, key or '(no key path)'
    if kind == _BROWSER_KIND:
        profile = (cfg.get('paths') or {}).get('profile')
        pdir = str(REPO_ROOT / 'data' / 'uc_profiles' / profile) if profile else None
        state, detail = _stat_state(pdir, stale_days, mtime_matters=True)
        return state, kind, detail, pdir or '(no profile declared)'
    if kind in _ENV_KINDS:
        state, detail = _env_state(cfg)
        return state, kind, detail, 'env / .env (out of git)'
    return 'unknown', kind or '(none)', f"unrecognized auth kind {kind!r}", '—'


def _next_hint(name, state, kind):
    """The exact command that warms THIS slot's kind — the connector teaching
    its own use, even for kinds this wallet cannot mint itself."""
    if kind == _OAUTH_KIND:
        return f"python scripts/connectors/wallet.py login {name}   (browser-mint, one-time)"
    if kind == _SERVICE_KIND:
        return (f"place the service-account key JSON at the path above "
                f"(Google Cloud Console → IAM → Service Accounts)")
    if kind == _BROWSER_KIND:
        return (f"python scripts/connectors/wallet.py warm {name}   "
                f"(confirms, then opens this slot's own site + profile)")
    if kind in _ENV_KINDS:
        return (f"python scripts/connectors/wallet.py warm {name}   "
                f"(prompts for each missing var, saves to {DOTENV_PATH})")
    return "unrecognized kind — check connectors.json `auth`"


def scoreboard(wallet, max_items, stale_days):
    """Print the read-only board for EVERY slot, across all five auth kinds."""
    slots = [(name, cfg) for name, cfg in wallet.items()
             if not name.startswith('_') and isinstance(cfg, dict) and cfg.get('auth')]

    print("# wallet.py — connector auth scoreboard (read-only, offline)")
    print(f"# wallet: {Path(WALLET_PATH).expanduser()}")
    print(f"# repo:   {REPO_ROOT}  (anchors browser_session profiles)")
    print(f"# stale after: {stale_days}d — mtime heuristic for oauth/browser, "
          "not a validity proof\n")

    if not slots:
        print("(no connector slots in this wallet)")
        print("\n# Next: add a slot to connectors.json, then re-run this scoreboard.")
        return

    shown = slots[:max_items]
    rows = []
    for name, cfg in shown:
        state, kind, detail, locator = classify_slot(name, cfg, stale_days)
        rows.append((state, kind, name, detail, locator))

    kind_w = max(len('kind'), *(len(_KIND_LABEL.get(r[1], r[1])) for r in rows))
    name_w = max(len('slot'), *(len(r[2]) for r in rows))
    det_w = max(len('evidence'), *(len(r[3]) for r in rows))
    print(f"     {'state':<7}  {'kind':<{kind_w}}  {'slot':<{name_w}}  "
          f"{'evidence':<{det_w}}  where")
    for state, kind, name, detail, locator in rows:
        mark = _MARK.get(state, '[?]')
        klabel = _KIND_LABEL.get(kind, kind)
        print(f"  {mark} {state:<7}  {klabel:<{kind_w}}  {name:<{name_w}}  "
              f"{detail:<{det_w}}  {locator}")

    if len(slots) > max_items:
        print(f"\n... +{len(slots) - max_items} more slot(s) (raise -n/--max)")

    # Tally + the single most useful next step.
    def n(state):
        return sum(1 for r in rows if r[0] == state)
    filled, stale, partial = n('filled'), n('stale'), n('partial')
    empty = sum(1 for r in rows if r[0] in ('empty', 'no-path'))
    unknown = n('unknown')
    tally = f"# {filled} filled | {stale} stale | {partial} partial | {empty} empty"
    if unknown:
        tally += f" | {unknown} unknown-kind"
    print(f"\n{tally}")

    warmed = filled + stale + partial
    if warmed == 0:
        # Fresh install: the Yen Sid nudge. Pure Python → identical on
        # macOS / WSL / Linux, so the curl|bash installer can echo it verbatim.
        first, fcfg = shown[0]
        fstate, fkind, _, _ = classify_slot(first, fcfg, stale_days)
        print("\n# 🧙 Your wallet is cold. Warm your first connector so it just "
              "keeps working:")
        print(f"#    {_next_hint(first, fstate, fkind)}")
        return

    # Point at the most warmable thing: empties first, then stales, then partials.
    def first_where(states):
        for r in rows:
            if r[0] in states:
                return r  # (state, kind, name, detail, locator)
        return None
    target = (first_where(('empty', 'no-path'))
              or first_where(('stale',)) or first_where(('partial',)))
    if target:
        _, kind, name, _, _ = target
        print(f"# Next: {_next_hint(name, target[0], kind)}")
    else:
        print("# Next: wallet fully warm — nothing to warm.")


# ---------------------------------------------------------------------------
# login — mints OAuth by reusing the connector's own walk; for every other
# kind it NAMES how that kind is warmed instead of pretending it can mint.
# ---------------------------------------------------------------------------
def login(slot_name, stale_days):
    if not slot_name:
        die("Usage: wallet.py login <slot>   (e.g. wallet.py login gmail)\n"
            "Run the bare scoreboard to see every slot, its kind, and state.")

    wallet = load_wallet()
    slot = wallet.get(slot_name)
    if not isinstance(slot, dict):
        names = [n for n, c in wallet.items()
                 if not n.startswith('_') and isinstance(c, dict) and c.get('auth')]
        die(f"No slot '{slot_name}' in {Path(WALLET_PATH).expanduser()}.\n"
            f"Slots: {', '.join(names) or '(none)'}")

    kind = slot.get('auth')

    # Non-oauth kinds cannot be minted here — but say EXACTLY how each is warmed.
    if kind != _OAUTH_KIND:
        state, _, detail, locator = classify_slot(slot_name, slot, stale_days)
        mark = _MARK.get(state, '[?]')
        msg = [f"Slot '{slot_name}' is auth={kind!r} — there is no OAuth token to mint here.",
               f"  now: {mark} {state}  ({detail})",
               f"  warm it:  {_next_hint(slot_name, state, kind)}"]
        if kind == _SERVICE_KIND:
            msg.append(f"  key path: {locator}")
        die('\n'.join(msg), code=2)

    # --- OAuth mint path: reuse the connector's own get_service() walk. ---
    creds_path = resolve_path(slot, 'credentials', 'paths.credentials')
    token_path = resolve_path(slot, 'token', 'paths.token')
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

    # Steer the reused connector at THIS slot's resolved paths via declared
    # env overrides, so a non-default wallet still mints to the right place.
    for needle, value in (('paths.credentials', creds_path), ('paths.token', token_path)):
        for env_key, desc in (slot.get('env') or {}).items():
            if needle in str(desc):
                os.environ[env_key] = value

    before_state, _, _, _ = classify_slot(slot_name, slot, stale_days)
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
        get_service()  # refresh headlessly, or browser-mint on a TTY
    except SystemExit:
        raise
    except Exception as e:
        die(f"OAuth walk for '{slot_name}' failed: {e}\n"
            "If a stale refresh token was revoked (the Testing-mode 7-day\n"
            "cliff), re-run this in a real terminal to browser-mint a fresh one.")

    after_state, _, detail, _ = classify_slot(slot_name, slot, stale_days)
    mark = _MARK.get(after_state, '[?]')
    print("\n# minted — this slot now reads:")
    print(f"  {mark} {after_state}  {slot_name}  {detail}  {token_path}")
    if after_state == 'filled':
        print("# Done. Re-run the bare scoreboard for the whole board.")
    else:
        print(f"# Note: slot still reads '{after_state}' — check the walk output above.")


# ---------------------------------------------------------------------------
# warm — the verb the scoreboard implies. One dispatch per auth kind, and each
# branch DELEGATES to the mechanism that already owns that kind: oauth reuses
# login()'s connector walk, browser shells out to weblogin.py, paste kinds
# prompt once and persist to DOTENV_PATH. Nothing here re-implements an OAuth
# dance or a login page. What genuinely cannot be minted is NAMED, not faked.
# ---------------------------------------------------------------------------
def _interactive():
    """True only on a real terminal. A `! python .../wallet.py` chisel-strike
    runs non-TTY inside a compile, so warm must print a PLAN there and never
    block on input() — otherwise it would deadlock the compile that ran it."""
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except Exception:
        return False


def _ask(question, secret=False):
    """One prompt. Returns '' on EOF/Ctrl-C so a skipped answer is just a skip.
    Secrets go through getpass so they never echo and never enter shell history."""
    import getpass
    try:
        return (getpass.getpass(question) if secret else input(question)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ''


def _confirm(question, assume_yes=False):
    return True if assume_yes else _ask(f"{question} [y/N] ").lower() in ('y', 'yes')


def _looks_secret(var):
    return any(w in var.lower() for w in ('token', 'secret', 'key', 'password', 'pass'))


def _save_env(name, value):
    """Upsert NAME=value into DOTENV_PATH at 0600. Prefers python-dotenv (a
    declared dependency) for correct quoting, with a stdlib fallback so this
    file still works outside the Nix shell — wallet.py stays import-light."""
    DOTENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DOTENV_PATH.exists():
        DOTENV_PATH.touch(mode=0o600)
    os.chmod(DOTENV_PATH, 0o600)
    try:
        from dotenv import set_key
        set_key(str(DOTENV_PATH), name, value)
    except ImportError:
        lines = DOTENV_PATH.read_text(encoding='utf-8').splitlines()
        rendered = "{}='{}'".format(name, value.replace("'", "'\\''"))
        for i, line in enumerate(lines):
            if line.split('=', 1)[0].strip().replace('export ', '') == name:
                lines[i] = rendered
                break
        else:
            lines.append(rendered)
        DOTENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    _dotenv_names._cache = None  # the board must re-read what we just wrote


def _warm_oauth(name, stale_days, assume_yes):
    """Reuse login() verbatim. SystemExit is caught so one failed slot cannot
    abort the walk over the rest of the board."""
    if not _confirm(f"  mint/refresh OAuth for '{name}' (may open a browser)?", assume_yes):
        return 'skipped'
    try:
        login(name, stale_days)
    except SystemExit as e:
        return f"login aborted (exit {e.code}) — see its message above"
    return 'oauth walk finished'


def _warm_env(name, cfg, assume_yes, force=False):
    """bearer/basic: prompt for declared vars and persist them. The
    `env` block is documentation-as-data, so the prompt shows the wallet's own
    description and any non-secret example from `defaults`.

    FORCE (2026-08-26, receipt-convicted inside ONE compile): the offline
    scoreboard reads NAMES ONLY, so a REVOKED token still reads `filled` and
    warm's cold-gate skipped it -- `check slack` printed RED gate2 while
    `warm slack --dry-run` printed "already reads filled" in the same payload.
    Naming a slot on the command line IS the explicit act; every declared var
    is re-offered, and blank input keeps whatever is already there."""
    req = _required_env_vars(cfg)
    missing = req if force else [v for v in req if not _env_source(v)]
    if not missing:
        return 'nothing missing'
    env_doc = cfg.get('env') or {}
    defaults = cfg.get('defaults') or {}
    print(f"  {len(missing)} value(s) -- blank keeps what is there, a paste overwrites.")
    saved = []
    for var in missing:
        desc = str(env_doc.get(var, '')).strip()
        if desc:
            print(f"    {var} — {desc}")
        if defaults.get(var):
            print(f"    example: {defaults[var]}")
        secret = _looks_secret(var)
        label = f"    {var}{' (hidden)' if secret else ''} = "
        value = _ask(label, secret=secret)
        if not value:
            print(f"    kept {var}" if _env_source(var) else f"    skipped {var}")
            continue
        _save_env(var, value)
        saved.append(var)
    if not saved:
        return 'nothing entered'
    return f"saved {', '.join(saved)} → {DOTENV_PATH}"


def _warm_browser(name, cfg, assume_yes):
    """browser_session: hand off to weblogin.py, which already owns the
    persistent-profile format. Confirm first — this pops a real window, and the
    human must either log in or simply dismiss it."""
    profile = (cfg.get('paths') or {}).get('profile') or name
    site = (cfg.get('defaults') or {}).get('site')
    if not site:
        # Never guess a hostname from a slot name (botify_browser is not a domain).
        site = _ask(f"  no defaults.site declared for '{name}' — site to open (blank skips): ")
        if not site:
            return 'skipped (no site declared)'
    if not _confirm(f"  open {site} in profile '{profile}'?", assume_yes):
        return 'skipped'
    script = REPO_ROOT / 'scripts' / 'weblogin.py'
    if not script.exists():
        return f"weblogin.py not found at {script}"
    print(f"  → {Path(sys.executable).name} {script.relative_to(REPO_ROOT)} {site} --profile {profile}")
    print("    Log in (or just dismiss it), then CLOSE the window to continue.")
    import subprocess
    try:
        rc = subprocess.call([sys.executable, str(script), site, '--profile', profile])
    except OSError as e:
        return f"could not run weblogin.py: {e}"
    return 'weblogin finished' if rc == 0 else f"weblogin exited {rc}"


def _warm_service(name, cfg):
    """service_account_file: genuinely un-mintable from here. Say so, and say
    exactly where the downloaded key must land."""
    key = resolve_path(cfg, 'service_account', 'paths.service_account')
    return ("cannot mint — download the service-account JSON (Google Cloud "
            f"Console → IAM → Service Accounts) to {key or '(declare paths.service_account)'}")


def warm(slot_name, stale_days, assume_yes=False, dry_run=False):
    """Walk every not-filled slot (or just one) and actually warm it."""
    wallet = load_wallet()
    slots = [(n, c) for n, c in wallet.items()
             if not n.startswith('_') and isinstance(c, dict) and c.get('auth')]
    if slot_name:
        picked = [(n, c) for n, c in slots if n == slot_name]
        if not picked:
            die(f"No slot '{slot_name}' in {Path(WALLET_PATH).expanduser()}.\n"
                f"Slots: {', '.join(n for n, _ in slots) or '(none)'}")
        slots = picked

    cold = []
    for n, c in slots:
        state, kind, detail, _loc = classify_slot(n, c, stale_days)
        if state != 'filled':
            cold.append((n, c, state, kind, detail))

    print("# wallet warm — the verb the scoreboard implies")
    print(f"# wallet:  {Path(WALLET_PATH).expanduser()}")
    print(f"# secrets: {DOTENV_PATH}  (0600, out of git)\n")

    if not cold:
        scope = f"slot '{slot_name}'" if slot_name else 'every slot'
        print(f"# Nothing to warm — {scope} already reads filled.")
        return

    print(f"# {len(cold)} slot(s) to warm:")
    for n, _c, state, kind, detail in cold:
        print(f"  {_MARK.get(state, '[?]')} {state:<7}  "
              f"{_KIND_LABEL.get(kind, kind):<8}  {n:<14}  {detail}")

    if dry_run:
        print("\n# --dry-run: nothing prompted, opened, or written.")
        return

    if not _interactive():
        target = f" {slot_name}" if slot_name else ''
        print("\n# Not a TTY — refusing to prompt, because a `!` chisel-strike must")
        print("# never block the compile that embedded it. In a real terminal:")
        print(f"#    python scripts/connectors/wallet.py warm{target}")
        return

    results = []
    for n, c, state, kind, _detail in cold:
        print("\n" + "-" * 70)
        print(f"{_MARK.get(state, '[?]')} {n}  ({_KIND_LABEL.get(kind, kind)}, was {state})")
        if kind == _OAUTH_KIND:
            note = _warm_oauth(n, stale_days, assume_yes)
        elif kind in _ENV_KINDS:
            note = _warm_env(n, c, assume_yes)
        elif kind == _BROWSER_KIND:
            note = _warm_browser(n, c, assume_yes)
        elif kind == _SERVICE_KIND:
            note = _warm_service(n, c)
        else:
            note = f"unrecognized auth kind {kind!r} — fix connectors.json"
        after, akind, adetail, _al = classify_slot(n, c, stale_days)
        results.append((after, akind, n, adetail, note))

    print("\n" + "-" * 70)
    print("# after warming:")
    for after, akind, n, adetail, note in results:
        print(f"  {_MARK.get(after, '[?]')} {after:<7}  "
              f"{_KIND_LABEL.get(akind, akind):<8}  {n:<14}  {adetail}")
        print(f"        ↳ {note}")
    still = [r for r in results if r[0] != 'filled']
    print(f"\n# {len(results) - len(still)} warmed | {len(still)} still cold")
    if any(r[1] in _ENV_KINDS for r in results):
        print(f"# Saved to {DOTENV_PATH}. The CHECK board injects that file into")
        print("# every connector it runs, so type `warm` again RIGHT NOW to watch")
        print("# these go green -- no shell restart needed to play the game.")
        print("# Typing a connector yourself (`slack`, `jira`) reads the vault at")
        print("# shell entry instead, so that lane wants one fresh `nix develop`.")
    print("# Re-run the bare scoreboard for the whole board.")


# ---------------------------------------------------------------------------
# check — the LIVE lane. Every other verb here is offline; this one spends
# exactly one bounded API call per enrolled slot to answer the only question
# a stat() cannot: does the service accept this credential RIGHT NOW.
# ---------------------------------------------------------------------------
CHECK_TIMEOUT = 20      # each connector budgets 15s; this is the outer fence
CHECK_WORKERS = 8       # slots are subprocesses, so this is pure I/O overlap
_LIVE_MARK = {0: '🟢', 1: '🔴'}


def _dotenv_pairs():
    """NAME -> value from the vault. Quotes are stripped because _save_env
    prefers python-dotenv's set_key, which writes them.

    This function and _check_env are the ONLY places in this file that touch a
    secret's VALUE. Nothing here prints, logs, or returns one to the renderer.
    """
    pairs = {}
    try:
        for line in DOTENV_PATH.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            if name.lower().startswith('export '):
                name = name[len('export '):].strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if name:
                pairs[name] = value
    except OSError:
        pass
    return pairs


def _check_env():
    """The environment each `--check` subprocess inherits: this process's env
    with the vault layered UNDER it, so an already-exported value wins —
    matching the flake's own precedence exactly.

    Without this, a token pasted by `warm` sixty seconds ago is invisible to
    the very board that asked for it, and you would have to exit and re-enter
    the shell between every single credential. The whole point of the game is
    to type one word, fix a red, and type the word again.
    """
    return {**_dotenv_pairs(), **os.environ}


# ---------------------------------------------------------------------------
# browser_session — checked HERE, by auth kind, never by filename. A browser
# profile is not a gateway, so "no connector module (semrush.py)" was a message
# telling the human to go write a program that should not exist.
# ---------------------------------------------------------------------------
_CHROME_EPOCH_OFFSET = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def _apex(site):
    """Registrable-ish apex from a slot's defaults.site. Naive on multi-part
    TLDs (co.uk), which only ever WIDENS the match — never narrows it."""
    host = site.split('://')[-1].split('/')[0].split(':')[0].lower()
    if host.startswith('www.'):
        host = host[4:]
    labels = [part for part in host.split('.') if part]
    return '.'.join(labels[-2:]) if len(labels) > 2 else host


def _cookie_db(profile_dir):
    """Chrome has relocated this file before; try every layout we have seen."""
    for rel in ('Default/Network/Cookies', 'Default/Cookies',
                'Network/Cookies', 'Cookies'):
        candidate = profile_dir / rel
        if candidate.exists():
            return candidate
    return None


def check_browser_slot(name, cfg):
    """SELECT 1 for a browser_session slot, from cookie METADATA alone.

    Probe-witnessed 2026-07-23: the profile's Cookies SQLite opens read-only
    with the browser closed, host_key and expires_utc are PLAINTEXT, and every
    secret sits in encrypted_value while value is empty. So a login is
    checkable without decrypting anything, without CDP, and without launching a
    browser — which is the point, since a browser per row is the exact opposite
    of slamming through the board.

    THE HTTPONLY DISCRIMINATOR (a labeled heuristic, never a proof): that same
    probe found the ONLY cookies present for both domains were _ga, ttcsid, and
    kndctr_* — analytics, set by page JavaScript on a mere VISIT. Greening on
    "any unexpired cookie" would therefore report a login that never happened,
    the precise false-green this board exists to refuse. Page JavaScript cannot
    set an HttpOnly cookie; it arrives in a server's Set-Cookie header. That
    difference is readable in the same table, so GREEN requires at least one
    LIVE HttpOnly cookie for the slot's apex, and a profile that was browsed
    but never logged into reds with exactly that sentence.
    """
    profile = (cfg.get('paths') or {}).get('profile') or name
    site = (cfg.get('defaults') or {}).get('site')
    if not site:
        return 1, (f"{name} RED gate1: slot declares no defaults.site, so "
                   "there is no domain to check")
    profile_dir = REPO_ROOT / 'data' / 'uc_profiles' / profile
    db = _cookie_db(profile_dir)
    if db is None:
        return 1, (f"{name} RED gate1: no cookie store under {profile_dir} — "
                   f"run `python scripts/connectors/wallet.py warm {name}`")
    apex = _apex(site)
    now = int((time.time() + _CHROME_EPOCH_OFFSET) * 1_000_000)
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT host_key, is_httponly, has_expires, expires_utc "
                "FROM cookies"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        return 1, (f"{name} RED gate2: cookie store unreadable ({e}) — close "
                   "the browser, which locks a live profile")
    mine = [r for r in rows if str(r[0]).lstrip('.').endswith(apex)]
    if not mine:
        return 1, (f"{name} RED gate2: profile '{profile}' holds no cookies "
                   f"for {apex} at all — never visited, never logged in")
    live = [r for r in mine if not r[2] or r[3] > now]
    if not live:
        return 1, (f"{name} RED gate2: all {len(mine)} cookies for {apex} have "
                   f"expired — run `wallet.py warm {name}`")
    session = [r for r in live if r[1]]
    if not session:
        return 1, (f"{name} RED gate2: {len(live)} live cookies for {apex} but "
                   "none HttpOnly — the site was VISITED, not logged into")
    dated = [r[3] for r in session if r[2] and r[3] > now]
    when = ''
    if dated:
        days = (min(dated) / 1_000_000 - _CHROME_EPOCH_OFFSET - time.time()) / 86400
        when = f", soonest expiry {days:.0f}d"
    return 0, (f"{name} GREEN {len(session)} HttpOnly cookie(s) for {apex} in "
               f"profile '{profile}' ({len(live)} live total{when})")


def check_slot(name, cfg=None):
    """Check one slot. Returns (code, line).

    DISPATCH IS ON AUTH KIND, never on filename. A browser_session slot is a
    Chrome profile, not a gateway, and routing it through the connector lookup
    produced "no connector module (semrush.py)" — a message instructing the
    human to write a program that should never exist. File and env kinds shell
    out to a connector; browser kinds are answered here, by the file that
    already knows where the profile lives.

    THE EXIT-CODE PROTOCOL, one layer out: nothing here parses a connector's
    stdout to DECIDE anything — the exit code is the whole answer. A connector
    may reword its receipt freely, and this renderer can be swapped for Rich
    or Textual, and neither can ever come to disagree with the other.

    0 = GREEN, 1 = RED, anything else = this slot has no `--check` yet
    (argparse exits 2). An uninstrumented slot renders UNCHECKED, never red:
    a missing instrument is not a failing credential. It does block GOLD,
    because surfacing exactly that gap is what the board is for.

    stdin is /dev/null and the timeout is hard, so no connector can hang the
    board on a prompt or a stalled socket.
    """
    if (cfg or {}).get('auth') == _BROWSER_KIND:
        return check_browser_slot(name, cfg)
    script = Path(__file__).resolve().parent / f"{name}.py"
    if not script.exists():
        return 2, f"no connector module ({script.name})"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), '--check'],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=CHECK_TIMEOUT, env=_check_env(),
        )
    except subprocess.TimeoutExpired:
        return 1, f"{name} RED gate2: no answer within {CHECK_TIMEOUT}s"
    except OSError as e:
        return 2, f"could not run {script.name}: {e}"
    out = [ln for ln in (proc.stdout or '').strip().splitlines() if ln.strip()]
    err = [ln for ln in (proc.stderr or '').strip().splitlines() if ln.strip()]
    if proc.returncode == 0:
        return 0, out[-1] if out else f"{name} GREEN"
    if proc.returncode == 1:
        return 1, err[-1] if err else f"{name} RED (no diagnostic)"
    return 2, 'no --check yet — this connector has no health probe'


def board(wallet, slot_name):
    """The red/green game: one live call per enrolled slot, GOLD at all-green.

    ENROLLMENT is what keeps the game winnable. A slot nobody intends to use
    — a service account, an untested vendor — would otherwise sit red or
    unchecked forever, making GOLD unreachable and draining the color of all
    meaning. Set "enrolled": false on such a slot in connectors.json and it
    is benched: shown, never scored. An absent flag defaults to enrolled.

    Slots run in parallel because the whole point is to type one word, see
    what is red, fix it, and type the word again.
    """
    slots = [(n, c) for n, c in wallet.items()
             if not n.startswith('_') and isinstance(c, dict) and c.get('auth')]
    if slot_name:
        slots = [(n, c) for n, c in slots if n == slot_name]
        if not slots:
            die(f"No slot '{slot_name}' in {Path(WALLET_PATH).expanduser()}.")
    enrolled = [(n, c) for n, c in slots if c.get('enrolled', True)]
    benched = [(n, c) for n, c in slots if not c.get('enrolled', True)]

    print("# wallet check — LIVE credential board (one bounded call per slot)")
    print(f"# wallet: {Path(WALLET_PATH).expanduser()}")
    print("# green means the service accepted this credential just now, "
          "not merely that a token exists\n")

    results = {}
    if enrolled:
        with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
            futures = [(n, pool.submit(check_slot, n, c)) for n, c in enrolled]
            for n, fut in futures:
                results[n] = fut.result()

    width = max([len(n) for n, _ in slots] + [4])
    green = red = unchecked = 0
    for n, cfg in enrolled:
        code, line = results[n]
        kind = str(_KIND_LABEL.get(cfg.get('auth'), cfg.get('auth')))
        print(f"  {_LIVE_MARK.get(code, '⚪')} {n.ljust(width)}  {kind:<8}  {line}")
        if code == 0:
            green += 1
        elif code == 1:
            red += 1
        else:
            unchecked += 1
    for n, cfg in benched:
        kind = str(_KIND_LABEL.get(cfg.get('auth'), cfg.get('auth')))
        print(f"  ·  {n.ljust(width)}  {kind:<8}  benched "
              '("enrolled": false in the wallet)')

    total = len(enrolled)
    tally = f"\n# {green} green | {red} red | {unchecked} unchecked"
    if benched:
        tally += f" | {len(benched)} benched"
    print(tally)
    if total and green == total:
        print(f"# 🏆 GOLD — every enrolled credential ({green}/{total}) is live.")
        return 0
    if red:
        print("# Fix a red:  python scripts/connectors/wallet.py warm <slot>")
    if unchecked:
        print("# An unchecked slot blocks GOLD on purpose: give it a --check, "
              'or bench it with "enrolled": false.')
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Scoreboard, live check, and warmer for the Pipulate wallet.")
    parser.add_argument('command', nargs='?', default=None,
                        help="omit for the OFFLINE scoreboard; 'check [slot]' "
                             "plays the LIVE red/green game; 'warm [slot]' "
                             "warms what is cold; 'login <slot>' mints one "
                             "oauth slot.")
    parser.add_argument('slot', nargs='?', default=None,
                        help="slot name for 'login' / 'warm' (e.g. gmail).")
    parser.add_argument('-y', '--yes', action='store_true',
                        help="skip per-slot confirmations (still prompts for "
                             "values warm cannot invent).")
    parser.add_argument('--dry-run', action='store_true',
                        help="'warm' lists what it WOULD do, then stops.")
    parser.add_argument('-n', '--max', type=int, default=25,
                        help='Max slots to show per THE PROBE ECONOMY RULE '
                             '(default: 25).')
    parser.add_argument('--stale-days', type=int, default=7,
                        help='mtime age (days) above which oauth/browser slots '
                             'read stale (default: 7 — the Testing-mode cliff).')
    args = parser.parse_args()

    if args.command in (None, 'scoreboard', 'status'):
        scoreboard(load_wallet(), args.max, args.stale_days)
    elif args.command in ('check', 'board'):
        # GOLD is the ONLY exit-0 condition, so "green all the way down" is a
        # machine-checkable claim and not merely a nice-looking screen.
        sys.exit(board(load_wallet(), args.slot))
    elif args.command == 'login':
        login(args.slot, args.stale_days)
    elif args.command == 'warm':
        warm(args.slot, args.stale_days, assume_yes=args.yes, dry_run=args.dry_run)
    else:
        die(f"Unknown command: {args.command}\n"
            "Usage: wallet.py                 (offline scoreboard)\n"
            "       wallet.py check [slot]    (LIVE red/green board)\n"
            "       wallet.py warm [slot]     (warm every cold slot, per kind)\n"
            "       wallet.py login <slot>    (mint one oauth slot)")


if __name__ == '__main__':
    main()
