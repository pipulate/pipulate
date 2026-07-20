# AGENTS.md — Pipulate

This repo predates the AGENTS.md / Agent Skills / OKF conventions and complies
with them by *pointing*, not duplicating. The sources of truth here are
executable, so this file is a signpost. Do not add sibling status .md files;
anything written here that duplicates code will drift and is a bug.

## Setup (the executable version of "Dev environment tips")

- `nix develop` — full environment (server + JupyterLab). See `flake.nix`.
- `nix develop .#quiet` — minimal shell for agents and scripting.
- Python lives in `.venv/`; invoke as `.venv/bin/python`.

## Tools

- Discover: `.venv/bin/python cli.py mcp-discover`
- Execute:  `.venv/bin/python cli.py call <tool_name> --json-args '{...}'`
- Skills (Agent Skills spec): `Notebooks/.agents/skills/*/SKILL.md`

## Context (how this repo talks to AI)

- `prompt_foo.py` compiles context payloads; `foo_files.py` is its router.
- Each compile emits `foo.zip`, a portable AGENTS-class cartridge whose YAML
  frontmatter names its entrypoint. The actionable request is always in the
  final section labeled `--- START: Prompt ---`.

## Edits (the executable version of "PR instructions")

- Propose changes as SEARCH/REPLACE blocks (exact-match, `[[[SEARCH]]]` /
  `[[[DIVIDER]]]` / `[[[REPLACE]]]`) applied via `cat patch | python apply.py`.
- Never patch `.ipynb` directly; `nbstripout` and `jupytext` are in play
  (see `.gitattributes`) — patch helper modules or give cell instructions.
- Python edits are AST-checked and Nix edits are syntax-checked before write.
