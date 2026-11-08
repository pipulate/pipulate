---
title: "Levinix: The Nix Flake Magic-Cookie Bootstrap (WORA Without Electron)"
canonical_url: "https://levinix.org/"
description: "How Levinix packages local-first Python/FastHTML web apps with Nix Flakes and the Magic Cookie bootstrap across Linux, macOS, and WSL."
---

# Levinix: Write Once, Run Anywhere Without Electron

> **RFC 9110 Content Negotiation Active**: You are reading the clean Markdown specification of `https://levinix.org/` served via `Accept: text/markdown` (`Vary: Accept`). Terminal clients (`curl`/`wget`) receive the installer script; browsers receive HTML.

## 1. Why Levinix Exists (From `LPvg` to `NPvg`)

A decade ago, **Levinux (`levinux.com`)** used QEMU + Tiny Core Linux (`LPvg`) to hand beginners a disposable Linux server on Mac and Windows. Today, shipping a local-first application usually traps developers into bundling a 300 MB Chromium binary per app via **Electron** or fighting host-OS Python dependency drift.

**Levinix (`levinix.org`)** solves the bootstrap paradox using **Nix Flakes** and the **Magic Cookie** pattern:

1. **Zero Pre-Installed Git Required**: `curl -fsSL https://levinix.org | bash` downloads a deterministic release archive and a read-only deploy key into `~/levinix`.
2. **Self-Assembly on First `nix develop`**: Entering the Nix flake environment provides the pinned `git`, `python312`, `uv`, `neovim`, and C libraries, converting the directory into a live git repository that auto-updates on future launches.
3. **Your Browser Is the UI**: Instead of shipping redundant Electron shells, local FastHTML/HTMX apps bind to `localhost` and use the browser already on your machine.

## 2. Inspect or Install

    # 1. Inspect the unexecuted installer in less:
    curl -fsSL https://levinix.org | less

    # 2. Run the bootstrap:
    curl -fsSL https://levinix.org | bash

## 3. The 3-Repo Nix Flake Trilogy & Ecosystem

- **Levinix Standalone Extraction (`pip` + Magic Cookie WORA App Wrapper)**: [https://github.com/pipulate/levinix](https://github.com/pipulate/levinix)
- **Python Nix Flake (`uv` + Python 3.13 Data Science & AI Agent Starter)**: [https://github.com/miklevin/python_nix_flake](https://github.com/miklevin/python_nix_flake)
- **Project Pipulate (The Full Forever Machine Workshop)**: [https://github.com/pipulate/pipulate](https://github.com/pipulate/pipulate) ([https://pipulate.com/](https://pipulate.com/))
- **Classic Levinux (`LPvg` Slide Deck)**: [https://levinux.com/](https://levinux.com/)
- **NPvg (Timeless Mastercraft)**: [https://npvg.org/](https://npvg.org/)
- **QA My AI (Flight Data Recorder)**: [https://qamy.ai/](https://qamy.ai/)
- **MikeLev.in (24/7 Web Bot AI Observatory)**: [https://mikelev.in/](https://mikelev.in/)
