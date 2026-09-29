# AGENTS.md — Pipulate

This repository carries Agent Skills under https://agentskills.io/specification
(`.agents/skills/*/SKILL.md`, a YAML head over a Markdown body, loaded on
demand), with this file as the nearest-ancestor signpost that points at
executable truth instead of duplicating it. Every tool call taught here runs
on localhost under the POSIX conventions of a command, stdin, stdout and an
exit code, so that its output lands in the sealed compile (`foo.zip`) as a
receipt; a cloud-side tool call that cannot be reconstructed here is
non-reproducible, non-portable, cannot be compiled into a cartridge, and is
out of scope by that rule, not by taste.

This repo predates those conventions and complies with them by *pointing*,
not duplicating. Do not add sibling status .md files; anything written here
that duplicates code will drift and is a bug.

## Setup (the executable version of "Dev environment tips")

- `nix develop` — full environment (server + JupyterLab). See `flake.nix`.
- `nix develop .#quiet` — minimal shell for agents and scripting.
- Python lives in `.venv/`; invoke as `.venv/bin/python`.

## Workspace (the layout `nix develop` materializes under `Workshop/`)

`Workshop/` is JupyterLab's root, not Pipulate's: three folders, corporate/, personal/ and shared/, and nothing else, with the starter notebooks under personal/Notebooks/. The tree below is GENERATED
between the sentinel comments by `prompt_foo.py` from the sealed `workspace_tree`
figurate asset — do not hand-edit it; edit the asset in
`imports/ascii_displays.py` and recompile. Empty here means the compiler has not
run since the sentinels landed.

<!-- --- START WORKSPACE TREE --- -->
```text
   Workshop/   — the JupyterLab root (NOT Pipulate's own root)
   │            FLAT siblings. Nothing nests. Nothing to get wrong.
   │
   ├── corporate/              the org's canon · gitignored · its own private repo
   ├── personal/               personal · gitignored · your own git repo goes here
   └── shared/                 the ONE folder for handing work to a teammate
       ├── alice/              one folder per person; you write ONLY your own
       └── bob/                single-writer partitions = zero merge conflicts
```
<!-- --- END WORKSPACE TREE --- -->

## Tools

- Discover: `.venv/bin/python cli.py mcp-discover`
- Execute:  `.venv/bin/python cli.py call <tool_name> --json-args '{...}'`
- Skills (Agent Skills spec, https://agentskills.io/specification): `.agents/skills/*/SKILL.md`, at the repo root beside this file
- The reasoning behind any piece of the machinery: the `journal` skill, whose `references/index.md` lists every journal entry newest first with a fetchable URL

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
