---
name: sheets_readonly
description: Read-only Google Sheets access for bounded context pulls. Trigger when a Google Sheets URL or spreadsheet ID needs to become compiled context. Executable truth lives at scripts/connectors/sheets.py; this skill is a signpost, never a second implementation.
---

# sheets_readonly — signpost to scripts/connectors/sheets.py

The executable is the specification. Run it; do not reimplement it.

## The three moves

1. Identity (get the share target):
   `python scripts/connectors/sheets.py`
   Prints the service-account client_email. Share each target spreadsheet
   with that email as Viewer.

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
- TWO-GATE 403 DIAGNOSIS, in order: SERVICE_DISABLED (enable the Sheets API
  in the key's Cloud project, once per project) before PERMISSION_DENIED
  (share the document with the client_email, once per document).
- Errors and auth guidance ride stderr; stdout stays parseable.

See scripts/connectors/README.md for the full connector contract.
