---
name: sheets_readonly
description: Read-only Google Sheets access for bounded context pulls. Trigger when a Google Sheets URL or spreadsheet ID needs to become compiled context. Executable truth lives at scripts/connectors/sheets.py; this skill is a signpost, never a second implementation.
---

# sheets_readonly — signpost to scripts/connectors/sheets.py

The executable is the specification. Run it; do not reimplement it.

## The three moves

1. Identity and mint (one-time, interactive):
   `python scripts/connectors/sheets.py`
   Prints the OAuth wiring status (credentials.json path, its project_id,
   token path) and, in a real terminal, mints ~/.config/pipulate/sheets_token.json
   via the browser handshake. After that, every run is headless.

2. LIST with size gauge:
   `python scripts/connectors/sheets.py "<URL-or-ID>"`
   Every tab's rows x cols x ~cells prints BEFORE any fetch; overflow-shaped
   tabs are flagged. A #gid= fragment in a pasted URL selects that tab and
   performs a bounded fetch of it directly.

3. Bounded FETCH:
   `--sheet "<Tab>"` (row-bounded server-side) or `--range "'Tab'!A1:F50"`,
   capped by -n/--max (default 25), `--format tsv|json|markdown` (tsv default).

## Rules inherited from the connector contract

- THE PROBE ECONOMY RULE: read the LIST size gauge before any fetch.
- Client URLs and spreadsheet IDs live in adhoc.txt, never in tracked source.
- Auth is OAuth as YOUR account (gmail.py pattern): no sharing gate, no
  service accounts. A separate sheets_token.json exists because token files
  are scope-scoped — never reuse gmail's token.
- 403 SERVICE_DISABLED means the Sheets API toggle in the OAuth client's
  Cloud project (identity mode prints its project_id); any other 403/404
  means your own account cannot open that sheet.
- Errors and auth guidance ride stderr; stdout stays parseable.

See scripts/connectors/README.md for the full connector contract.
