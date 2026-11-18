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
DEFAULT_EXTRA_PATHS = (REPO_ROOT / "scripts", REPO_ROOT / "scripts/articles", REPO_ROOT / "remotes/honeybot/scripts", REPO_ROOT)


def setup_sys_path() -> None:
    for _extra in reversed(DEFAULT_EXTRA_PATHS):
        if str(_extra) not in sys.path:
            sys.path.insert(0, str(_extra))

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


_MOD_DUNDERS = frozenset({"__all__", "__annotations__", "__builtins__", "__cached__", "__dict__", "__doc__", "__file__", "__loader__", "__name__", "__package__", "__path__", "__spec__"})
_INNER_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    elts = node.elts if isinstance(node, (ast.Tuple, ast.List)) else ([node.value] if isinstance(node, ast.Starred) else [])
    return {n for e in elts for n in _target_names(e)}


def _scan_module_symbols(py_path: Path) -> tuple[bool, set[str], dict[str, tuple[str, int]]]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except Exception:
        return False, set(), {}
    attrs, func_defs, complete = set(_MOD_DUNDERS), {}, True

    def _walk(node: ast.AST) -> None:
        nonlocal complete
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                attrs.add(ch.name)
                complete = complete and (ch.name != "__getattr__")
                for sub in ast.walk(ch):
                    if sub is not ch and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        func_defs.setdefault(sub.name, (ch.name, sub.lineno))
                    elif isinstance(sub, (ast.Assign, ast.AnnAssign)):
                        for t in (sub.targets if isinstance(sub, ast.Assign) else ([sub.target] if sub.target else [])):
                            for n in _target_names(t):
                                func_defs.setdefault(n, (ch.name, sub.lineno))
                continue
            if isinstance(ch, _INNER_SCOPES):
                attrs.update((ch.name,) if isinstance(ch, ast.ClassDef) else ())
                continue
            if isinstance(ch, ast.Import):
                attrs |= {al.asname or al.name.split(".", 1)[0] for al in ch.names}
            elif isinstance(ch, ast.ImportFrom):
                complete = complete and all(al.name != "*" for al in ch.names)
                attrs |= {al.asname or al.name for al in ch.names if al.name != "*"}
            elif isinstance(ch, ast.Assign):
                attrs |= {n for t in ch.targets for n in _target_names(t)}
            elif isinstance(ch, (ast.AnnAssign, ast.NamedExpr, ast.For, ast.AsyncFor)) and getattr(ch, "target", None):
                attrs |= _target_names(ch.target)
            elif isinstance(ch, (ast.With, ast.AsyncWith)):
                attrs |= {n for it in ch.items if it.optional_vars for n in _target_names(it.optional_vars)}
            elif isinstance(ch, ast.ExceptHandler) and isinstance(ch.name, str):
                attrs.add(ch.name)
            elif isinstance(ch, ast.Call) and isinstance(ch.func, ast.Name) and ch.func.id in ("exec", "setattr", "globals"):
                complete = False
            _walk(ch)

    _walk(tree)
    if py_path.name == "__init__.py":
        attrs |= {c.stem for c in py_path.parent.glob("*.py") if c.stem != "__init__"}
        attrs |= {c.name for c in py_path.parent.iterdir() if c.is_dir() and (c / "__init__.py").is_file()}
    return complete, attrs, func_defs


def _extract_extra_dirs(tree: ast.AST, repo_root: Path) -> list[Path] | None:
    def _rp(ex: ast.AST) -> Path | None:
        ex = ex.args[0] if isinstance(ex, ast.Call) and isinstance(ex.func, ast.Name) and ex.func.id == "str" and len(ex.args) == 1 else ex
        lhs = _rp(ex.left) if isinstance(ex, ast.BinOp) and isinstance(ex.op, ast.Div) and isinstance(ex.right, ast.Constant) and isinstance(ex.right.value, str) else None
        return repo_root if (isinstance(ex, ast.Name) and ex.id == "REPO_ROOT") else ((lhs / ex.right.value) if lhs else None)

    dirs: list[Path] = []
    for sub in ast.walk(tree):
        ex_list = [sub.args[-1]] if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Attribute) and isinstance(sub.func.value.value, ast.Name) and sub.func.value.value.id == "sys" and sub.func.value.attr == "path" and sub.func.attr in ("insert", "append") and sub.args) else ((list(sub.value.elts) if isinstance(sub.value, (ast.List, ast.Tuple)) else [sub.value]) if (isinstance(sub, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) and isinstance(t.value.value, ast.Name) and t.value.value.id == "sys" and t.value.attr == "path" for t in sub.targets)) else None)
        for e in (ex_list or ()):
            p = _rp(e)
            if p is None:
                return None
            dirs.append(p)
    return dirs


def check_local_module_attrs(code: str, repo_root: Path = REPO_ROOT, is_pyprobe: bool = True, label: str = "pyprobe") -> str | None:
    """AST-verify imported local repo module attribute accesses without importing modules."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    extra_dirs = _extract_extra_dirs(tree, repo_root)
    if extra_dirs is None:
        return None
    rebound, mutated_mods, mod_map = set(), set(), {}
    for sub in ast.walk(tree):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rebound |= {sub.name, *(a.arg for a in sub.args.args + sub.args.kwonlyargs)}
        elif isinstance(sub, ast.ClassDef):
            rebound.add(sub.name)
        elif isinstance(sub, ast.Assign):
            rebound |= {n for t in sub.targets for n in _target_names(t)}
            mutated_mods |= {t.value.id for t in sub.targets if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)}
        elif isinstance(sub, (ast.For, ast.AsyncFor, ast.comprehension)):
            rebound |= _target_names(sub.target)
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "setattr" and sub.args and isinstance(sub.args[0], ast.Name):
            mutated_mods.add(sub.args[0].id)
    search_dirs = [d for d in dict.fromkeys([*extra_dirs, *(DEFAULT_EXTRA_PATHS if is_pyprobe else (repo_root,))]) if d.is_dir()]
    for st in tree.body:
        pairs = [(al.asname or al.name, al.name) for al in st.names if "." not in al.name or al.asname] if isinstance(st, ast.Import) else ([(al.asname or al.name, f"{st.module}.{al.name}") for al in st.names if al.name != "*"] if isinstance(st, ast.ImportFrom) and st.module and st.level == 0 else [])
        for bind, mname in pairs:
            if mname.split(".", 1)[0] not in sys.builtin_module_names:
                rel = mname.replace(".", "/")
                p = next((cand for d in search_dirs for cand in (d / f"{rel}.py", d / rel / "__init__.py") if cand.is_file()), None)
                if p:
                    mod_map[bind] = None if bind in mod_map and mod_map[bind] != p else p
    cache: dict[Path, tuple[bool, set[str], dict[str, tuple[str, int]]]] = {}
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load) and isinstance(sub.value, ast.Name):
            alias, py_p = sub.value.id, mod_map.get(sub.value.id)
            if not py_p or alias in rebound or alias in mutated_mods:
                continue
            if py_p not in cache:
                cache[py_p] = _scan_module_symbols(py_p)
            complete, attrs, fdefs = cache[py_p]
            if complete and sub.attr not in attrs:
                rel = py_p.relative_to(repo_root) if py_p.is_relative_to(repo_root) else py_p
                hint = f" (defined inside def {fdefs[sub.attr][0]}() at line {fdefs[sub.attr][1]}, not module scope)" if sub.attr in fdefs else ""
                return f"{label} local module attribute error: '{alias}' ({rel}) has no module-level attribute '{sub.attr}'{hint}"
    return None


def main(argv: list[str] | None = None) -> int:
    setup_sys_path()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python scripts/pyprobe.py [--check] [-c] '<python_code>' [args...]")
        return 0 if args else 2
    check_only = args[0] == "--check"
    args = args[1:] if check_only else args
    if not args or (args[0] == "-c" and len(args) < 2):
        print("pyprobe error: missing code argument", file=sys.stderr)
        return 2
    code, rest = (args[1], args[2:]) if args[0] == "-c" else (args[0], args[1:])
    if err := check_local_module_attrs(code, repo_root=REPO_ROOT, is_pyprobe=True, label="pyprobe"):
        print(err, file=sys.stderr)
        return 1
    if check_only:
        ast.parse(code)
        print("OK")
        return 0
    sys.argv = ["<pyprobe>", *rest]
    exec(compile(code, "<pyprobe>", "exec"), build_namespace())
    return 0


if __name__ == "__main__":
    sys.exit(main())
