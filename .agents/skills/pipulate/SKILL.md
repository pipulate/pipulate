---
name: pipulate
description: Installing Pipulate, the local-first context compiler, on a machine that does not have it, without taking the keyboard away from the person who owns the machine. Use when someone asks to install, start, stop, reset or remove Pipulate, or asks what the one-line installer will do before running it. Read the installer before running it, run the copy you read, and keep every step a command the human types.
---

# pipulate: install it without giving up the keyboard

The skill you keep is the one you can still use when the wrapper is gone.
Every step below is a command the human types and reads before it runs, so
the person doing it learns what their machine is doing instead of watching
a spinner.

Two doors serve one installer. `https://pipulate.com/install.sh` lands the
workshop in `~/pipulate`; `https://npvg.org` serves the same script to `curl`
with its default folder stamped to `~/npvg` (a browser at that address gets a
web page instead). The lines below use the npvg door; swap the URL and the
folder name for the other.

## 1. Look before you run

~~~bash
curl -fsSL https://npvg.org | less
~~~

Nothing runs. What appears is the installer as text: a comment block that
explains the design (a ZIP download and a read-only deploy key, then
`nix develop`, which turns the folder into a git checkout that updates
itself), then `main() {`, the whole body inside that function, and a last
line that calls it. `j` moves down, `k` up, `/nix` searches, `q` quits. The
function wrapper is deliberate: a download cut off partway cannot run half
an install.

## 2. Save it, read it, run the copy you read

~~~bash
curl -fsSL https://npvg.org -o install.sh
less install.sh
bash install.sh
~~~

The file read is the file run, byte for byte; that is the one thing the pipe
form skips. `bash install.sh myname` puts the workshop in `~/myname` and
names the app after it; with no argument the folder is the door's default.

## 3. The one line, once you have read it

~~~bash
curl -fsSL https://npvg.org | bash
~~~

What it does, in order (the script's own sequence; read it there):

1. Refuses to run under a shell that is not bash, prints one line naming the
   folder and the command that removes it, and stops if `curl` or `unzip`
   is missing.
2. If `nix` is missing, runs the Determinate Systems Nix installer and then
   STOPS: close this terminal, open a new one, run the line it prints. That
   stop is expected, not a failure. The line it prints goes through
   pipulate.com and, from the npvg door, carries the folder as an argument
   (`bash -s npvg`), so the app is then named after the folder; the plain
   npvg line names no folder and leaves the app named Pipulate.
3. Refuses if the target folder already exists. It never overwrites.
4. Downloads the repository as a ZIP from GitHub and unpacks it into the
   folder.
5. Fetches a ROT13-encoded deploy key into `.ssh/rot` inside the folder. It
   is pull-only: it lets the folder fetch updates without a GitHub account.
6. Writes a `run` file the flake deletes on its first entry (a leftover the
   repo has marked for removal), prints the come-back line, and hands off
   to `nix develop -L`. The first entry can take several minutes while
   packages download; the installer's last line says so, and a long wait
   after it is that download.

Inside `nix develop` the flake finishes the job: it clones the repository
over the ZIP so the folder becomes a real git checkout (the pre-transform
files are backed up to a temp directory and the path is printed), creates
`.venv`, installs the Python packages with `uv`, and prints one line of
readings (Nix version, Python version, Pipulate version, the folder)
followed by a short list of words to type.

## 4. Three ways in, after that

- `cd ~/npvg && nix develop` is the everyday door. On a terminal it stops at
  the short command list and a `(nix)` prompt; nothing has started. Every
  entry also pulls the latest commit, fast-forward only; a local change
  pauses the update and says so.
- `jn` starts JupyterLab at `http://localhost:8888` with the Onboarding
  notebook open and the app at `http://localhost:5001`, and prints the
  banner. Finishing that notebook is what unlocks the app tab on later
  starts. Ctrl+C stops the app; `pu` starts it again and is also the
  restart word. JupyterLab runs in a `tmux` session named `jupyter` and
  keeps running after the shell is left.
- `walk` is the first word to type: a guided walk over three public pages
  that teaches the loop. On its first run it shows a card asking whether it
  may read aloud and records the answer; it stays silent until that answer
  is yes, and `voice` changes it later. `menu` reprints the short list,
  `all` the long one, `about` the workspace tree, the three tiers and how
  to check what an AI said against what it was handed. `exit` leaves the
  shell.

## 5. What stays on the machine, and what leaves it

Stays: everything runs on localhost, ports 5001 and 8888. The folder holds
the code, `.venv`, the SQLite databases under `data/`, and the person's own
notebooks and files under `Workshop/personal/`, which git never tracks.
Outside the folder, three homes: `~/.config/pipulate/` (settings,
credentials the person adds by hand, the one-line answer to the voice
question), `~/.local/share/pipulate/` (two sound files) and
`~/.local/state/pipulate/` (the compile's own state: `context.txt` when
`PIPULATE_ADHOC_FILE` points there, and what a move sets aside under
`stale/`). The browser lanes may leave a driver cache under `~/.cache`; that
path was not read for this skill. The voice model lands inside the folder,
under `assets/piper_models/` (gitignored, so removing the folder removes
it), fetched on the first spoken line after the yes at the voice card.

Leaves, as the installer and the flake spell it: GitHub (the ZIP, then the
clone, then a `git pull` on every `nix develop`); pipulate.com (the deploy
key, from either door);
install.determinate.systems, only when Nix is missing; the Nix binary cache
and PyPI, for packages; Hugging Face once, for a small voice model, and only
after the person has answered yes at the voice card. No connector calls any
service until the person warms a credential for it themselves.

Two things it touches outside the folder, worth saying out loud: if
`~/.ssh/id_rsa` does not exist, the flake writes the decoded deploy key
there and adds a `Host github.com` block to `~/.ssh/config`; an existing key
is left alone. And Nix is a system-level install with its own uninstaller;
removing the folder does not remove Nix.

## 6. Stop, reset, remove

- Stop the app: Ctrl+C in the window running it. Stop JupyterLab:
  `tmux kill-session -t jupyter`. Leave the shell: `exit`.
- Reset the Python environment and nothing else: `rm -rf ~/npvg/.venv`, then
  `nix develop` rebuilds it.
- Remove: `rm -rf ~/npvg` (the installer prints this line itself), then
  `rm -rf ~/.config/pipulate ~/.local/share/pipulate ~/.local/state/pipulate`
  for the three homes outside the folder. If the flake wrote `~/.ssh/id_rsa`
  (the person had
  none before), that key and the `github.com` block in `~/.ssh/config` are
  theirs to remove. Nix stays unless its own uninstaller is run.

## What this skill does not do

- It never runs the installer on the person's behalf; it hands them the
  line and reads the script with them.
- It never edits files in the workshop by hand. Edits go through the
  protocol `AGENTS.md` names: SEARCH/REPLACE blocks, matched exactly once,
  applied by `apply.py`, which checks Python, Nix and JSON syntax before it
  writes. That protocol is always-on in `AGENTS.md` rather than a skill,
  because a skill loads on demand and the protocol is every turn.
- It was read against four sources: the installer's own text, the door page
  a browser gets at npvg.org, README's Quick Start and AUDIT.md; where the
  installer's text and a page disagreed, the installer's text won.
