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
8. THE FIRST DOCSTRING LINE IS A LIVE DISPLAY, not prose. `scripts/mcp_menu.py`
   reads it with `ast.get_docstring` (never an import) and prints it verbatim
   beside the command word in the `mcp` roster, so it must read as an
   instruction to a newcomer who has never opened the file:
   `name.py — <verb phrase, one sentence, 61 chars or fewer>`, e.g. "Bring a
   Jira project, issue, or JQL search into context." The 61 is MEASURED, not
   chosen: at 80 columns Rich leaves the panel a 74-character body (2 for
   borders, 4 for padding), and every row spends the command column (10
   today, the width of `confluence`) plus 3 spaces of gutter, leaving 61.
   One character over and the row wraps, stranding a word on a line by
   itself. A command word longer than `confluence` lowers this ceiling for
   every row at once. The `name.py — `
   self-label is stripped before display, so the sentence must stand alone.
   Architecture notes ("a Unix-philosophy gateway to...") belong in the SECOND
   paragraph, where the reader is a developer rather than a menu. A connector
   with no module docstring still lists, wearing a loud placeholder that names
   its own fix; a connector whose first line describes a DIFFERENT file ships
   a lying menu row the moment it enters the roster.

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
(confluence), service_account_file (gsc), browser_session (botify_browser,
semrush — a persistent Chrome profile under data/uc_profiles/<name>, warmed by
weblogin.py, not a token). Every future connector copies one of these five.

## Current connectors

- gmail.py       LIST by address / FETCH by hex id or web-URL / SEARCH by "subject" -> full thread(s), --list for snippets (OAuth token file)
- botify.py      identity walk / org / org/project / BQL query (BOTIFY_API_TOKEN)
- confluence.py  spaces / space pages / page id / CQL search (CONFLUENCE_* envs)
- jira.py        projects / project issues / issue key (PROJ-123) / raw JQL (basic_auth; shares CONFLUENCE_* token)
- gsc.py         properties / top queries / raw searchanalytics JSON (service_account_file)
- sheets.py      identity / bare URL-or-ID STACKS every tab's actual data rectangle with sentinel separators and per-tab #gid= URLs, budget-governed / --list metadata gauge / bounded --sheet and --range values (oauth_token_file, gmail pattern; own sheets_token.json; data extents from values responses, never gridProperties)
- slack.py       identity + channels / channel id-or-#name history / message-permalink thread FETCH / whitespace=SEARCH (bearer_token; SLACK_BOT_TOKEN reads, SLACK_USER_TOKEN required for search.messages)

## Downstream stages (deliberately not connectors)

- `scripts/map_sheet.py` consumes timestamped, sentinel-fenced Sheets STACK
  output and emits a draft `SheetApiMapping` JSON artifact. It exposes header
  ambiguity, records lookup columns by index and normalized name, samples their
  values to reject false URL matches, and proposes API correspondences for
  human confirmation before QA or automation.

## Minting a new connector

Copy the closest existing connector, keep the docstring shape, keep the
disambiguation table, keep the breadcrumbs. If an API's paging differs,
write that API's paging — do not generalize another connector's. Then REWRITE
the first docstring line before anything else (contract item 8): a copied
connector that keeps its template's first line will display the template's
name in the `mcp` roster, which is how `gong.py` came to introduce itself as
`wallet.py`.
