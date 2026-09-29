# AGENTS.md — Pipulate

This repository carries Agent Skills under https://agentskills.io/specification
(`.agents/skills/*/SKILL.md`, a YAML head over a Markdown body, loaded on
demand), with this file as the nearest-ancestor signpost that points at
executable truth instead of duplicating it. Every tool call taught here runs
on localhost under the POSIX conventions of a command, stdin, stdout and an
exit code, so that its output lands in the sealed compile (`qamy.ai.zip`, the
QA archive zip) as a receipt; a cloud-side tool call that cannot be
reconstructed here is non-reproducible, non-portable, cannot be compiled into
that archive, and is out of scope by that rule, not by taste.

This repo predates those conventions and complies with them by *pointing*,
not duplicating. Do not add sibling status .md files; anything written here
that duplicates code will drift and is a bug.

## Setup (the executable version of "Dev environment tips")

- `nix develop` — the full environment. On a terminal it stops at a short
  list of words and a `(nix)` prompt with nothing started; `jn` starts
  JupyterLab and the server. Without a terminal it starts the app, so an
  agent takes the quiet shell below. See `flake.nix`.
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
- Skills (Agent Skills spec, https://agentskills.io/specification): `.agents/skills/*/SKILL.md`, at the repo root beside this file; `.claude/skills` is a symlink to the same folder, so Claude Code's project-skills path offers the same skills
- The reasoning behind any piece of the machinery: the `journal` skill, whose `references/index.md` lists every journal entry newest first with a fetchable URL

## Context (how this repo talks to AI)

- `prompt_foo.py` compiles context payloads; `foo_files.py` is its router.
- Each compile emits `qamy.ai.zip`, the QA archive zip: a portable
  AGENTS-class archive holding `payload.md`, `prompt.md` and `manifest.json`,
  whose YAML frontmatter (`type: qa-zip-archive`) names its entrypoint. The
  actionable request is always in the final section labeled
  `--- START: Prompt ---`. A rotated copy, `qamy.ai_<deed>-<hash8>.zip`, is
  minted beside it, the deed number first so a listing reads in order and the
  domain on the file so a recipient knows where it is explained;
  `python scripts/foo_cartridge.py <that zip>` verifies one with the standard
  library alone.

## Edits (the executable version of "PR instructions")

- Propose changes as SEARCH/REPLACE blocks (exact-match, `[[[SEARCH]]]` /
  `[[[DIVIDER]]]` / `[[[REPLACE]]]`) applied via `cat patch | python apply.py`.
- Never patch `.ipynb` directly; `nbstripout` and `jupytext` are in play
  (see `.gitattributes`) — patch helper modules or give cell instructions.
- Python edits are AST-checked and Nix edits are syntax-checked before write.
