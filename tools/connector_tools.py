"""
connector_tools.py -- the registry face of scripts/connectors/*.py: one tool
per connector, SAME argument shape, SAME backend, SAME docstring.

This file exists for the two-arm experiment (shell verb vs registry tool) and
for nothing else yet. Arm S runs the connector as a command line; Arm R calls
the tool below through `cli.py call <name> --json-args '{...}'`. Both arrive at
the identical subprocess, so the only thing the experiment can measure is the
invocation grammar and the discovery surface, which is the variable under test.

THREE SURFACES, ONE SOURCE. sources_menu.py reads each connector's module
docstring with ast.get_docstring and prints its first line as the menu row;
the connector's own --help prints the same docstring (argparse
description=__doc__); this file reads the same docstring the same way and
installs it as the tool's __doc__ at import time, which is what
`cli.py mcp-discover --tool <name>` prints. A description that is better on
one arm than the other is the confound that would decide the experiment for
the wrong reason, so no hand-authored description is allowed to exist here.

PARAMS MIRROR ARGPARSE DESTS, deliberately, so the JSON a model must write is
readable off the same --help text the other arm reads: query (the single
positional; omit it for the identity walk), org, project, max, check.

KNOWN SEAM: the AST-derived Tool Roster in prompt_foo.py cannot see a __doc__
assigned at runtime; it shows the literal placeholder on the function. Named
here rather than papered over with a copied sentence that would drift.
"""
import ast
import asyncio
import sys
from pathlib import Path

from tools import auto_tool

REPO_ROOT = Path(__file__).resolve().parent.parent
CONNECTORS = REPO_ROOT / "scripts" / "connectors"
TIMEOUT = 120
KEY_TRAILER = (
    "\n\nRegistry form: --json-args keys mirror the connector's argument names --"
    " query (the positional; omit for the identity walk), org, project, max, check."
)


def _connector_doc(name):
    """The connector's module docstring, read the way sources_menu.py reads it."""
    path = CONNECTORS / f"{name}.py"
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return f"(could not read {path}: {exc.__class__.__name__})"
    return (doc or f"(NO MODULE DOCSTRING in {path})") + KEY_TRAILER


async def _run_connector(name, params):
    """Run scripts/connectors/<name>.py as a subprocess; return its three channels."""
    if not isinstance(params, dict):
        return {"success": False, "error": "params must be a JSON object"}
    argv = [sys.executable, str(CONNECTORS / f"{name}.py")]
    if params.get("query") is not None:
        argv.append(str(params["query"]))
    for flag in ("org", "project"):
        if params.get(flag):
            argv += [f"--{flag}", str(params[flag])]
    if params.get("max") is not None:
        try:
            argv += ["--max", str(int(params["max"]))]
        except (TypeError, ValueError):
            return {"success": False, "error": "max must be an integer"}
    if params.get("check"):
        argv.append("--check")
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"success": False, "error": f"timed out after {TIMEOUT}s", "argv": argv[1:]}
    except OSError as exc:
        return {"success": False, "error": str(exc), "argv": argv[1:]}
    return {
        "success": proc.returncode == 0,
        "argv": argv[1:],
        "exit_code": proc.returncode,
        "stdout": out.decode("utf-8", errors="replace"),
        "stderr": err.decode("utf-8", errors="replace"),
    }


@auto_tool
async def botify(params: dict) -> dict:
    """Registry face of scripts/connectors/botify.py; __doc__ is replaced at
    import with that file's own docstring so both arms read one description."""
    return await _run_connector("botify", params)


botify.__doc__ = _connector_doc("botify")
