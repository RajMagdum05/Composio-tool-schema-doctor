# Milestone 0 — Independent Validation of the Investigation

**Date:** 2026-11-13
**Validator:** Claude Code (second, independent pass over the Milestone 0 investigation)
**Upstream:** `ComposioHQ/composio` @ `6aa3f31ecf38fc5f9ea10d67e31a43ede2e2c693` (branch `next`), checkout `composio-upstream/`, **unchanged** (verified clean).
**Env:** `.venv-investigate/` (Python 3.12): composio 0.32.0, composio-client 2.1.32, openai 3.50.0, anthropic 2.8.0, google-genai 2.34.0, google-cloud-aiplatform 2.9.0, google-adk 2.14.1, pydantic 2.14.3.

This note **re-runs** the reproduction scripts from scratch and checks each reported count against a fresh result. Raw re-run outputs are saved in `investigation/_validation_runs/` (they do **not** overwrite the originals in `investigation/results/`). Labels: **CONFIRMED** = independently reproduced this pass; **CORRECTED/CLARIFIED** = reported statement adjusted.

---

## 1. Result table

| # | Reported finding | Reported value | Re-run value | Status |
|---|---|---|---|---|
| 1 | Vertex (`composio_google`) failures | 6/930 | **6/930**, same tool IDs, all `ParseError` | **CONFIRMED (exact)** |
| 2 | Missing action hints (mock corpus) | 227/930 = 24.4% | **227/930 = 24.4%** | **CONFIRMED (exact)** |
| 3 | Within-toolkit duplicate display-name groups | 285 | **285** | **CONFIRMED (exact)** |
| 4 | Gemini (`composio_gemini`) failure | 1/930 `GOOGLEDRIVE_UPDATE_PERMISSION` | **1/930**, live ValueError on nested `permission` object | **CONFIRMED (exact)** |
| 5 | OpenAI strict-schema incompatibility | 114/930 | **114/930** | **CONFIRMED (exact)** |
| 6 | HEAD enum claim | not verified / reframed | no tool has `HEAD` in an `enum`; reframed to a general enum-loss finding | **CONFIRMED (correct to reframe)** |
| 7 | Upstream tests | 150 passed | 86 test functions in 4 files → **150 cases** via parametrization; none cover nested `examples`/`file_uploadable` | **CLARIFIED** |
| 8 | Scripts use real adapters | claimed | confirmed: scripts import `composio_openai/anthropic/google/gemini/google_adk`, real `google.genai`, and SDK `to_strict_json_schema` — no adapter logic reimplemented | **CONFIRMED** |
| 9 | Fixture provenance | offline repo files | both fixtures are git-tracked upstream at the SHA (blob hashes below) | **CONFIRMED** |

No reported count was contradicted. One wording clarification (row 7) and one framing already corrected by the original author (row 6).

---

## 2. Reproducible commands

All commands run from the project root `R:\Internship_Outreach_prototype\Composio`. `PY=.venv-investigate/Scripts/python.exe`.

### 2.1 Metadata (stdlib, fast, deterministic)
```
$PY -I investigation/repro_metadata.py composio-upstream > investigation/_validation_runs/metadata.json
```
Re-run output:
- mock corpus: **930** tools (823 GITHUB, 56 GOOGLE, 51 GOOGLEDRIVE)
- `tools_with_no_action_hint` (none of readOnly/create/update/destructive) = **227** → **24.4%**
- `tools_with_no_hint_tag` (no hint at all) = **85**
- mock duplicate slugs = **0**; mock duplicate display-names = **41**
- destructive-verb slug without `destructiveHint` = **16** (includes false positives like `*_ARCHIVE_*`)
- docs catalog: **1743** toolkits, **84004** tools
- within-toolkit duplicate-name groups = **285**; cross-toolkit = **6201**; duplicate slugs global = **0**
- description == name/slug = **678**; empty = **0**; over 1024 chars = **678**

### 2.2 Vertex corpus (real `composio_google` adapter, network blocked)
```
REPRO_PROVIDERS=google_vertex $PY -I investigation/repro_corpus.py composio-upstream > investigation/_validation_runs/corpus_vertex.json
```
Re-run: **6 failures, all `ParseError`**, identical tool IDs to the report.

### 2.3 OpenAI / Anthropic / strict corpus (live this pass)
```
REPRO_PROVIDERS=openai,anthropic $PY -I investigation/repro_corpus.py composio-upstream
```
Re-run: openai **0**, openai_responses_strict **114**, anthropic **0**. (Gemini full-corpus pass is slow — ~930 `from_callable` builds — so gemini/adk were validated by a targeted single-tool live run plus the saved artifact; see §3.)

---

## 3. The six Vertex failures — exact schema paths (independently extracted)

Five fail because `GoogleProvider.wrap_tool` (`python/providers/google/composio_google/provider.py:44-51`) strips `examples` **only from top-level properties**; a `ParseError` is then raised by the proto `Schema` parser on the first **nested** `examples`. One fails on `file_uploadable`.

| Tool | Cause | First offending path (nested, below top level) |
|---|---|---|
| `GOOGLEDRIVE_FILES_MODIFY_LABELS` | nested `examples` | `/properties/label_modifications/items/properties/field_modifications/items/properties/set_date_values/examples` |
| `GOOGLEDRIVE_UPDATE_PERMISSION` | nested `examples` | `/properties/permission/properties/role/examples` |
| `GOOGLEDRIVE_UPLOAD_FILE` | `file_uploadable` | `/properties/file_to_upload/file_uploadable` |
| `GOOGLE_ANALYTICS_CREATE_EXPANDED_DATA_SET` | nested `examples` | `/properties/expandedDataSet/properties/dimensionNames/examples` |
| `GOOGLE_CLASSROOM_COURSE_WORK_PATCH` | nested `examples` | `/properties/dueDate/properties/day/examples` |
| `GOOGLE_MAPS_MAPS_EMBED_API` | nested `examples` | `/properties/directions_params/properties/avoid/examples` |

Note: several of these tools *also* carry top-level `examples` (e.g. `GOOGLEDRIVE_UPDATE_PERMISSION./properties/fileId/examples`); those are stripped successfully, so they are not the failure cause. This confirms the "top-level only" stripping diagnosis.

**Gemini failure (live, targeted):** `GOOGLEDRIVE_UPDATE_PERMISSION` → `ValueError: Failed to parse the parameter permission: composio.utils.schema_converter.Permission …` — the nested `permission` object defeats `FunctionDeclaration.from_callable`. ADK converts the same tool without error. Baseline `GITHUB_CREATE_AN_ISSUE` passes on both. So `GOOGLEDRIVE_UPDATE_PERMISSION` fails on **both** Google paths, for **different** reasons (Vertex: nested `examples`; Gemini: nested object parse).

---

## 4. What the scripts and fixtures actually are (provenance)

- **`repro_providers.py`** imports and calls the real provider classes — `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider`, `GeminiProvider`, `GoogleAdkProvider` — plus real `google.genai.types.FunctionDeclaration.from_callable` and the SDK's `composio.utils.strict_schema.to_strict_json_schema`. It blocks `socket.connect`/`getaddrinfo` and hard-fails any tool execution (`_never_execute`). **No adapter conversion logic is copied.** This is the reuse pattern the build must follow.
- **`repro_corpus.py`** runs every tool in the mock through those same functions; one failing tool does not stop the run (per-tool try/except).
- **`repro_metadata.py`** is stdlib-only and reads the two catalogs read-only.
- **Fixtures are git-tracked upstream at the SHA:**
  - `ts/packages/cli/test/__mocks__/tools.json` → blob `b28f3c96499276f5ee0bfde7fc2c8e8021fb45a3` — 930 tools with full `slug/name/description/tags/input_parameters`. **GitHub-heavy test mock**, not a live catalog.
  - `docs/public/data/toolkits.json` → blob `6a81b753b2679cddae499cdd0019a4c89c4afbe6` — 84004 tools with `slug/name/description` only (**no tags, no schemas**).
  - *Correction (2026-11-14):* the first version of this note had these two hashes swapped. Re-verified with both `git rev-parse HEAD:<path>` and `git hash-object <path>`; `make_evidence.py` now records them per file automatically.

---

## 5. Denominator discipline (carried into the build)

- **227/24.4%** and the 285 groups come from **different files** and must never be mixed:
  - 227 missing-hint and all provider-compatibility counts → the **930-tool mock** (has tags + schemas).
  - 285 duplicate-name groups, 678 desc==name, 678 >1024 → the **84004-tool docs catalog** (names/descriptions only).
- 24.4% is a **fixture statistic on a GitHub-heavy sample**, not a live-catalog rate. Reports must say so.
- Duplicate **display names** ≠ duplicate **slugs/IDs** (0 duplicate slugs). Slugs are the function names the LLM sees, so duplicate display names are an ambiguity signal, not a provider collision.

---

## 6. Corrections / clarifications to the investigation report

1. **"150 passed"** → clarified: 150 pytest *cases* from **86 test functions** across `test_google_provider.py` (6), `test_gemini_provider.py` (44), `test_google_adk_provider.py` (1), `test_strict_schema.py` (35); many are parametrized. Grep confirms **none** of the provider test files reference `file_uploadable` or nested `examples`, so §4 findings are genuine coverage gaps.
2. **Vertex failure "6" is corpus-specific** — on synthetic inputs the Vertex path also rejects integer enums, `anyOf`-null, `type:[...]`, `oneOf`, `const`. Confirmed; the "6" applies only to this 930-tool mock.
3. No numeric correction required; the investigation's counts stand.

---

## 7. Acceptance check (Playbook Milestone 0)

- [x] Every count has a reproducible command (§2).
- [x] Fixture-specific results are labelled as such, not as live-catalog statistics (§5).
- [x] Failures have tool IDs and useful errors (§1, §3).
- [x] Unsupported/inaccurate statements corrected in this validation note (§6; HEAD reframed).
- [x] Upstream files unchanged (checkout clean at the SHA).

**Conclusion:** the Milestone 0 investigation is **validated**. All headline findings reproduce exactly. Proceed to Milestone 1 (architecture) with the denominator rules in §5 and the real-adapter reuse pattern in §4 as hard constraints.
