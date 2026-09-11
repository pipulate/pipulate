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
8. THE FIRST DOCSTRING LINE IS A LIVE DISPLAY, not prose. `scripts/sources_menu.py`
   reads it with `ast.get_docstring` (never an import) and prints it verbatim
   beside the command word in the `sources` roster, so it must read as an
   instruction to a newcomer who has never opened the file:
   `name.py — <verb phrase, one sentence, 61 chars or fewer>`, e.g. "List your
   open Jira tickets, or fetch one by key." The 61 is MEASURED, not
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
weblogin.py, not a token), and mcp_oauth (botify_mcp — a remote MCP bearer
whose token file is DERIVED from the slot's defaults.resource and minted or
refreshed by mcp_warm.py; the durable credential scored is the refresh
token). Every future connector copies one of these six.

`warm <URL>` needs no slot at all: wallet.py synthesizes a browser_session
slot from the address -- profile = the host's apex label (`botify.atlassian.net`
-> `atlassian`), the same per-domain name the `?URL` lane resolves under
data/uc_profiles/ -- opens it in weblogin.py, reads the cookie verdict, and
prints the connectors.json slot to add if the site should stay on the check
board. The wallet is neither read nor written for an ad-hoc warm, and
`check <URL>` re-reads that cookie verdict offline any time after -- the
crawl-side pre-check before a `?URL` line goes into adhoc.txt.

Credential paths are DERIVED, never chosen. A connector that talks to more than
one server of the same kind — MCP is the first — computes its token path from
the server URL rather than from a constant, so the credential a client sends is
structurally the credential that server minted. mcp.py and mcp_warm.py each
carry an identical `token_path_for()` mapping a resource URL to
`~/.config/pipulate/mcp/<host>.json`, appending a quoted path slug when the
server lives under a path rather than at a host root. Collision is
unrepresentable, an Nth server costs zero configuration lines, and a bearer
scoped to one resource can never be handed to another. The pre-derivation file
`mcp_botify_token.json` is read as a fallback and is never moved by a read path;
the next browser warm writes the derived location and the fallback stops firing.
Duplicating the derivation rather than sharing it is deliberate — each connector
stays self-contained — so the two copies are compared by probe, not trusted.

## Current connectors

- gmail.py       LIST by address / FETCH by hex id or web-URL / SEARCH by "subject" -> full thread(s), --list for snippets (OAuth token file)
- botify.py      identity walk / org / org/project / org/project/analysis (verdict: status, pages done/known, rate, ETA by cadence, then crawl statistics; a RUNNING crawl is absent from the list and present here) / org/project/<resource>[/<id>] and org/project/<slug>/<sub> drill any raw API path, rendered by shape, --grep narrowing a list or printing every matching leaf path in one object / any app.botify.com URL, reduced to its slug path / BQL query (BOTIFY_API_TOKEN)
- confluence.py  spaces / space pages / page id / CQL search (CONFLUENCE_* envs)
- jira.py        bare = your open issues (the For You tab; any /jira/for-you URL too) / projects / project issues / issue key (PROJ-123; prints populated custom fields, link hrefs, attachments) / raw JQL (basic_auth; JIRA_* first, CONFLUENCE_* as a fallback -- a convenience, never a shared identity)
- gsc.py         properties / top queries / raw searchanalytics JSON (service_account_file)
- sheets.py      identity / bare URL-or-ID STACKS every tab's actual data rectangle with sentinel separators and per-tab #gid= URLs, budget-governed / --list metadata gauge / bounded --sheet and --range values (oauth_token_file, gmail pattern; own sheets_token.json; data extents from values responses, never gridProperties)
- slack.py       identity + channels / channel id-or-#name history / message-permalink thread FETCH / whitespace=SEARCH (bearer_token; SLACK_BOT_TOKEN reads, SLACK_USER_TOKEN required for search.messages; -w NAME reads the SLACK_USER_TOKEN_NAME / SLACK_BOT_TOKEN_NAME pair instead, no fallback to the bare pair)

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
name in the `sources` roster, which is how `gong.py` came to introduce itself
as `wallet.py`.

## Drill by shape, find by needle (botify.py, 2026-09-10)

Beyond its golden-path modes a connector should let the positional argument
be a raw API path: `org/project/<resource>[/<id>]` GETs that path and renders
the reply by SHAPE -- a list as `ident | date | name` rows with a `# Next:`
naming the FETCH, one object as scalars plus each container's JSON -- and
`--grep` narrows a list by substring or, on one object, prints every leaf
whose dotted path or value matches. No object path is hardwired (the
operator's rule): every sub-resource the app's own frame was seen calling,
and every one it was not, is one argument away, and 667 saved explorers
become the few about links without anyone reading 667 names. Two limits are
known and earmarked in botify.py: a string leaf that is itself serialized
JSON is opaque to the leaf grep, and a subtree that echoes the parent (an
analysis carries its `previous`) can spend most of a `-n` cap.

THE MOMENT TO REACH FOR A CONNECTOR is the moment a lens shows less than the
wire does: the `?URL` optics of a logged-in page rendered a shell with an
`[Iframe]` leaf while the wire truth showed the frame's own XHR, and that
XHR's path became the connector's next mode. A LIST that omits the thing you
want (a running crawl, absent from /light) is the same signal one rung
lower: FETCH it by id, then DRILL.
