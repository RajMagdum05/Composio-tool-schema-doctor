# Tool-Schema Doctor — Demo & Technical Summary (Milestone 6)

**Date:** 2026-11-13

## 1. Project overview
Tool-Schema Doctor is a small offline CLI that QA-checks Composio tool schemas. Three capabilities:
1. **Provider compatibility** — run each tool's schema through the *real* Composio adapters and record what each provider accepts, silently transforms, or rejects.
2. **Metadata lint** — six deterministic rules (missing hints, duplicate display names, weak descriptions, …), each with evidence and a suggested fix.
3. **Tool-selection eval** (optional) — measure whether an LLM picks the right tool from an ambiguous candidate set.

It reuses the genuine adapters (never copies their logic) and the compat/lint core is fully offline.

## 2. Architecture (how it works)
```
fixture JSON ──> loader ──> ToolRecord[] ──┬─> compat  ─(real adapters, offline)─> CompatResult[]
                                           ├─> lint    ─(deterministic rules)─────> LintFinding[]
                                           └─> report  ─> report.json + report.md
eval_dataset.json + corpus ─> selection_eval ─(Groq, opt-in)─> metrics
```
- `providers.py` imports the real `composio_openai/anthropic/google/gemini/google_adk` classes and the SDK's `to_strict_json_schema`, builds a `Tool` via `model_construct` (as upstream tests do), blocks the network, and hard-fails any tool execution. Missing SDKs → `unavailable` (skipped), not failures.
- Only `composio` is a hard dependency; each provider SDK is an optional extra.
- Details: `architecture.md`; decisions: `decision-log.md`.

## 3. Reproduction of the key findings
From the project root (`PY=.venv-investigate/Scripts/python.exe`):

```
# Compatibility over the 930-tool mock (reproduces the verified counts)
$PY -m tool_schema_doctor.cli compatibility --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o out/compat.json

# Combined report (JSON + Markdown)
$PY -m tool_schema_doctor.cli report --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o out/report-mock

# Catalog-scale lint (names/descriptions only)
$PY -m tool_schema_doctor.cli report --input composio-upstream/docs/public/data/toolkits.json --no-compat -o out/report-catalog

# Tool-selection eval
$PY -m tool_schema_doctor.cli eval                              # offline dataset validation
$PY -m tool_schema_doctor.cli eval --live --model openai/gpt-oss-20b   # needs GROQ_API_KEY
```

## 4. Evidence (expected vs actual)
Compatibility over the 930-tool mock, **through the shipped CLI** (status `transformed` = converted but dropped tracked keywords):

| Provider | ok | transformed | error | meaning |
|---|---:|---:|---:|---|
| `openai` | 930 | 0 | 0 | passthrough |
| `openai_strict` | 0 | 816 | **114** | 114 can't be strict → provider falls back to non-strict |
| `anthropic` | 930 | 0 | 0 | `$ref` inlined |
| `google_vertex` | 13 | 911 | **6** | 5 nested `examples` + 1 `file_uploadable` |
| `gemini` | 0 | 929 | **1** | `GOOGLEDRIVE_UPDATE_PERMISSION` nested object |
| `google_adk` | 6 | 924 | 0 | drops enums/examples silently |

Lint: mock `missing-action-hint` **227/930 (24.4%)**; catalog within-toolkit duplicate-name groups **285**, `description-repeats-name` **678**, `description-too-long` **678**. (Each stat names its fixture; denominators are never mixed.)

Eval (27 ambiguous tasks, temp 0): `gpt-oss-20b` **27/27**, `qwen3.8-27b` **27/27**, `allam-2-7b` **26/27** (miss on the genuinely-close assignee task `t27`).

Every reported bug has a **regression test**; see `pytest`.

## 5. Known limitations
- Results reflect installed adapter versions; the mock is GitHub-heavy (fixture stats ≠ live-catalog rates).
- Capable models score 100% on the eval → these ambiguities are resolvable from descriptions, not proof selection is universally easy.
- The eval depends on model + prompt (disclosed per report) and only selects a tool.
- Open question (from M0): whether the Vertex adapter is "current" or "legacy" vs google-genai — affects whether the 6 failures are framed as a bug.

## 6. Two–three minute demo script
1. **"Here's the problem."** Composio exposes 84k tools across providers; schemas that work for OpenAI can silently break or lose information on Google. (10s)
2. **Run compatibility** on the mock → show the summary table: OpenAI/Anthropic clean, Vertex 6 hard failures, strict mode 114 unsupported, Gemini drops all enums. (40s)
3. **Open `report.md`** → point at the failing-conversions table with exact tool IDs and schema paths (e.g. `GOOGLEDRIVE_UPLOAD_FILE` → `/properties/file_to_upload/file_uploadable`). (30s)
4. **Run lint on the catalog** → 285 duplicate-name groups, 678 descriptions that just repeat the name. (20s)
5. **Run the eval** → 3 models, one interpretable failure on the hardest task; the harness measures accuracy and catches invalid picks. (30s)
6. **"Everything is offline, reuses the real adapters, and every bug has a regression test."** (10s)

## 7. Technical summary (for outreach)
> I built **Tool-Schema Doctor**, a small offline CLI that reuses Composio's real provider adapters to check tool-schema compatibility and lint tool metadata, plus an optional Groq-backed tool-selection eval. I independently reproduced five reported issues from source — e.g. the Vertex adapter rejects nested `examples`/`file_uploadable` on exactly 6 of the 930 mock tools, OpenAI strict mode can't express 114 of them, and Gemini drops every enum — each pinned by a regression test. The linter quantifies metadata gaps (24.4% of the mock lack action hints; 285 within-toolkit duplicate display names in the catalog) while keeping fixture denominators separate. The selection eval (27 curated ambiguous tasks) scores capable Groq models at 100% and a 7B baseline at 96.3%, with the single failure landing on the one genuinely-ambiguous task. The whole thing is ~700 lines, `composio` + optional provider extras, no network in the core, and ships with tests.

## 8. Quality checklist
- [x] Reuses real adapters (no copied logic); upstream checkout unchanged.
- [x] Every reproduced bug has a regression test; counts reproducible via documented commands.
- [x] Offline core; eval opt-in and credential-safe (env only; key never committed).
- [x] Fixture provenance stated; denominators not mixed.
- [x] JSON + readable Markdown reports; clear exit codes.
- [x] README with setup/run/examples/limitations.
