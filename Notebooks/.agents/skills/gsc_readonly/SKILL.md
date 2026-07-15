# GSC Read-Only Connector Guide

## Your Role

Use `scripts/connectors/gsc.py` as the only executable surface for Google Search Console work. Keep this skill as an instruction layer: do not copy the connector into the skill, reimplement its API calls, or broaden its OAuth scope.

## Safety and Preconditions

1. Run from the Pipulate repository root and confirm `scripts/connectors/gsc.py` exists.
2. Keep the Google scope at `https://www.googleapis.com/auth/webmasters.readonly`.
3. Treat the service-account file as opaque. Never open, print, quote, upload, summarize, or embed its JSON, private key, tokens, or other credential values.
4. Refer only to the credential-routing names and paths:
   - `PIPULATE_GSC_KEY`
   - `~/.config/pipulate/connectors.json` at `gsc.paths.service_account`
   - `~/.config/pipulate/service-account-key.json`
5. Do not claim the wallet contains secrets. It records routing metadata; secret material lives in the referenced environment or credential file.

## Choose the Connector Mode

Use the connector's existing argument disambiguation. An argument beginning with `{` or containing whitespace is FETCH mode. Any other bare token is a property coordinate. No argument lists properties.

### List visible properties

```bash
python scripts/connectors/gsc.py
```

Use this to discover property coordinates available to the configured service account. The default output cap is 25.

### List bounded top queries for one property

```bash
python scripts/connectors/gsc.py sc-domain:example.com
```

Treat this as a bounded top-query view, not a complete export. Keep the default cap of 25 unless the user explicitly needs a different small bound.

### Run a bounded raw Search Analytics request

```bash
python scripts/connectors/gsc.py \
  '{"startDate":"2026-06-01","endDate":"2026-06-28","dimensions":["page","query"]}' \
  --site sc-domain:example.com
```

`--site` may be omitted only when `PIPULATE_GSC_SITE` is already set. The connector applies `rowLimit` when absent and slices returned rows to `-n/--max`.

### Change the cap deliberately

```bash
python scripts/connectors/gsc.py -n 10 sc-domain:example.com
```

Keep outputs small because stdout may be compiled into Prompt Fu context. Never describe the result as exhaustive or guaranteed complete; call it bounded Search Analytics rows or a capped top-query view.

## Compile-Lane Privacy

Property-list output contains domains and can reveal client identities. Before placing a `! python scripts/connectors/gsc.py ...` command in `adhoc.txt` or sending its captured output to a cloud model, confirm `pii_substitutions.txt` covers every real client identifier. Redact or omit sensitive coordinates when that coverage is uncertain.

## Failure Handling

- When FETCH mode lacks a property coordinate, request `--site` or `PIPULATE_GSC_SITE`.
- When credential routing fails, report the missing routing name or path without inspecting the service-account JSON.
- When Google returns an API error, report the bounded error context and preserve read-only scope.
- Do not patch `scripts/connectors/gsc.py` merely to work around missing configuration; fix routing metadata or the local credential file outside the repository.

## Reporting Results

State the mode, property coordinate when applicable, requested cap, and returned row count. End with the caveat that the output is bounded and not a guaranteed complete Search Console export. Preserve or strengthen privacy redaction for any compile-lane result.
