#!/usr/bin/env python3
"""Stdlib-preloaded one-liner probe runner for bounded '! ' behavioral straddles."""

import ast
import atexit
import contextlib
import hashlib
import io
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra in (
    REPO_ROOT,
    REPO_ROOT / "remotes" / "honeybot" / "scripts",
    REPO_ROOT / "scripts" / "articles",
    REPO_ROOT / "scripts",
):
    _s = str(_extra)
    if _s not in sys.path:
        sys.path.insert(0, _s)

SEARCH_MARK = "[" * 3 + "SEARCH" + "]" * 3
DIVIDER_MARK = "[" * 3 + "DIVIDER" + "]" * 3
REPLACE_MARK = "[" * 3 + "REPLACE" + "]" * 3

RUFF_PRELUDE_STUB = (
    "import ast, contextlib, hashlib, io, json, math, os, pathlib, re, shlex, shutil, sqlite3, subprocess, subprocess as sp, sys, tempfile, time\n"
    "from pathlib import Path\n"
    "REPO_ROOT = Path('.'); SEARCH_MARK = DIVIDER_MARK = REPLACE_MARK = ''\n"
    "def quiet_call(*a, **k): return None\n"
    "def capture_call(*a, **k): return (None, '')\n"
    "def temp_dir(*a, **k): return Path('.')\n"
    "def with_env(*a, **k): return None\n"
    "def ruff_check(*a, **k): return 0\n"
    "def make_patch_block(*a, **k): return ''\n"
)


def quiet_call(fn, *args, **kwargs):
    """Call fn(*args, **kwargs) with stdout captured and discarded; restores stdout on error."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def capture_call(fn, *args, **kwargs):
    """Call fn(*args, **kwargs) and return (result, captured_stdout_str)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = fn(*args, **kwargs)
    return res, buf.getvalue()


def temp_dir(prefix: str = "pip_probe_") -> Path:
    """Create an auto-cleaned scratch directory under /tmp."""
    p = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, p, True)
    return p


def with_env(overrides: dict, fn, *args, **kwargs):
    """Temporarily apply env var overrides (None pops the key) around fn(*args, **kwargs)."""
    sentinel = object()
    saved = {k: os.environ.get(k, sentinel) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        return fn(*args, **kwargs)
    finally:
        for k, old in saved.items():
            if old is sentinel:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def ruff_check(*paths) -> int:
    """Run ruff check on paths and return its exit code."""
    exe = shutil.which("ruff") or "ruff"
    return subprocess.run([exe, "check", *(str(p) for p in paths)], capture_output=True, text=True).returncode


def make_patch_block(target, search: str, replace: str) -> str:
    """Build one surgical Target/SEARCH/DIVIDER/REPLACE car without literal markers in probes."""
    return f"Target: {target}\n{SEARCH_MARK}\n{search}\n{DIVIDER_MARK}\n{replace}\n{REPLACE_MARK}\n"


def build_namespace() -> dict:
    """Return the fresh execution globals dictionary preloaded for a probe snippet."""
    return {
        "__name__": "__pyprobe__",
        "ast": ast,
        "contextlib": contextlib,
        "hashlib": hashlib,
        "io": io,
        "json": json,
        "math": math,
        "os": os,
        "pathlib": pathlib,
        "re": re,
        "shlex": shlex,
        "shutil": shutil,
        "sqlite3": sqlite3,
        "subprocess": subprocess,
        "sp": subprocess,
        "sys": sys,
        "tempfile": tempfile,
        "time": time,
        "Path": Path,
        "REPO_ROOT": REPO_ROOT,
        "SEARCH_MARK": SEARCH_MARK,
        "DIVIDER_MARK": DIVIDER_MARK,
        "REPLACE_MARK": REPLACE_MARK,
        "quiet_call": quiet_call,
        "capture_call": capture_call,
        "temp_dir": temp_dir,
        "with_env": with_env,
        "ruff_check": ruff_check,
        "make_patch_block": make_patch_block,
    }


EXPORTED_NAMES = frozenset(k for k in build_namespace() if not k.startswith("__"))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python scripts/pyprobe.py [-c] '<python_code>' [args...]")
        return 0 if args else 2
    if args[0] == "-c":
        if len(args) < 2:
            print("pyprobe error: -c requires a code argument", file=sys.stderr)
            return 2
        code, rest = args[1], args[2:]
    else:
        code, rest = args[0], args[1:]
    sys.argv = ["<pyprobe>", *rest]
    ns = build_namespace()
    exec(compile(code, "<pyprobe>", "exec"), ns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
