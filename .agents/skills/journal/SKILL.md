---
name: journal
description: The journal behind Pipulate, indexed. More than a thousand dated articles explain why each piece of the machinery exists, and references/index.md lists them newest first with a fetchable raw-Markdown URL per entry. Use when a question asks why something in this repo is built the way it is, when a comment in the code cites a date or a deed number, or when a change needs reasoning that the git log does not carry.
---

# journal: the reasoning behind the machinery

This repository holds the machinery. The reasoning lives in a running journal
on a separate site, one entry per working session, and this skill is the
bridge to it. Nothing here duplicates the code; the index points and the site
holds. It is what a changelog would be if a changelog recorded why.

## What is here

- `references/index.md`, every entry newest first. The first twenty carry full
  URLs; the rest are bare slugs with a date and a size, and the file's own
  header prints the pattern that turns a slug into a page.

## How to use it

1. Find the entry in `references/index.md` by date, title or slug. A date in
   a code comment (`banked 2026-09-26`) or a deed number (`deed 1596`) names
   a session, and that day's entries carry the why.
2. Build the URL with the pattern at the top of the index (today it is
   `https://mikelev.in/futureproof/<slug>/index.md`); the site serves raw
   Markdown at that path.
3. Fetch only the entry the question needs. One entry can run to 200k
   tokens. The index is a menu, never a payload.
4. Inside a checkout, `scripts/xp.py` turns a pasted list of slugs into the
   next compile's context; `AGENTS.md` at the repo root names that grammar.

## What is not here

- Setup, tools and edit rules: `AGENTS.md`, and the code it points at.
- The reviewer's change-control questions and the artifacts that answer
  them: `AUDIT.md`.
- Article bodies. They never enter this repo; the URL is the whole promise.
