# Connectors — Unix-philosophy API gateways for Prompt Fu context

Each connector is ONE self-contained `.py` file. That is the point. No shared
imports, no package coupling: a connector must survive being curl'd, gisted,
or dropped into a skills registry as a single artifact. Duplication between
connectors is deliberate (WET). Extract to a kit.py only when the same bug
has been fixed in the same helper in two files.

## The Contract (every connector obeys all of these)

1. ONE positional argument, mode auto-detected from its shape:
   - no argument        -> identity walk / top-level LIST
   - bare token         -> LIST within that scope (org, space key, ...)
   - id-shaped token    -> FETCH one object in full (thread id, page id)
   - whitespace or '{'  -> QUERY / SEARCH mode
2. `-n/--max` output cap, default 25 (THE PROBE ECONOMY RULE). stdout is
   destined for compiled context payloads; the bound is a feature.
3. Every LIST mode ends with a `# Next:` breadcrumb showing the exact command
   for the next drill-down step. The connector teaches its own use.
4. Auth resolves from env vars and/or ~/.config/pipulate, never from files
   inside this repo. Fail with a message that names the missing variable and
   shows an example value. A clean failure is a valid receipt.
5. Errors go to stderr and exit nonzero; stdout stays parseable.
6. First interactive run may open a browser (OAuth); every subsequent run
   must work headless under prompt_foo's captured, no-TTY pipe.
7. COMPILE-LANE CAUTION in the docstring: if LIST/FETCH output can contain
   client identifiers, say so, and rely on pii_substitutions.txt coverage
   before any `!` invocation rides to a cloud chat window.

## The Wallet (~/.config/pipulate/connectors.json)

The tracked key-val parity layer: connector name -> auth kind, required env
var NAMES, token file PATHS, and non-secret defaults. Names and paths only —
never secret values — which is what makes it safe to track in the (scrubbed)
~/.config/pipulate repo. Resolution order in every connector: explicit CLI
flag -> env var -> connectors.json default -> clean failure naming the
missing variable. Only the `defaults` block is machine-consumed; `env`
blocks are documentation-as-data. Eventually a connectors.nix emits this
file blogs.nix-style: mechanism in the Nix store, data at runtime, secrets
in neither.

Auth kinds: oauth_token_file (gmail), bearer_token (botify), basic_auth
(confluence), service_account_file (gsc, planned). Every future connector
copies one of these four.

## Current connectors

- gmail.py       LIST by address / FETCH by thread id (OAuth token file)
- botify.py      identity walk / org / org/project / BQL query (BOTIFY_API_TOKEN)
- confluence.py  spaces / space pages / page id / CQL search (CONFLUENCE_* envs)

## Minting a new connector

Copy the closest existing connector, keep the docstring shape, keep the
disambiguation table, keep the breadcrumbs. If an API's paging differs,
write that API's paging — do not generalize another connector's.
