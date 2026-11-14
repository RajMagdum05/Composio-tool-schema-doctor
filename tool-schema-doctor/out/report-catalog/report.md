# Tool-Schema Doctor — Report

- Generated: `2026-11-13T18:03:14+00:00`
- Input: `composio-upstream/docs/public/data/toolkits.json` (source: **catalog**)
- Tools: **84004** · with schema: 0 · with tags: 0

## Provider compatibility
_No compatibility run (input has no schemas, or it was disabled)._
## Metadata lint
Total findings: **1965**

| Rule | Count |
|---|---|
| `description-repeats-name` | 678 |
| `description-too-long` | 678 |
| `duplicate-display-name-in-toolkit` | 609 |

### Examples
- **description-repeats-name** (warning): `AMBIGUOUS_MCP_LIST_SHARED_DRIVE_MEMBERS`, `ASANA_ADD_CUSTOM_FIELD_SETTING_FOR_PROJECT`, `ASANA_CREATE_BUDGET`
- **description-too-long** (info): `AHREFS_MCP_RENDER_SCORECARD`, `AHREFS_MCP_RENDER_TIME_SERIES_CHART`, `AIROPS_MCP_ADD_AEO_REGION`
- **duplicate-display-name-in-toolkit** (info): `ALCHEMY_IS_AIRDROP`, `ALCHEMY_IS_AIRDROP_NFT`, `ALPACA_CREATE_WATCHLIST`

## Skipped checks
- lint:missing-action-hint: no tags in input (names-only catalog): hint rules not applicable
- lint:destructive-verb-without-destructive-hint: no tags in input: cannot check destructiveHint

## Limitations
- Offline only: results reflect the installed adapter versions; no live API/LLM calls.
- One failing tool does not stop the run; adapter errors are reported per tool.
- Input is the docs catalog (names/descriptions only, no tags/schemas). Provider compatibility and hint lint do not apply here.
