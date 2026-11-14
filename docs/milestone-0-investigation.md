# Tool-Schema Doctor — Milestone 0: Repository Investigation

**Upstream:** `ComposioHQ/composio`, default branch `next`, commit `6aa3f31ecf38fc5f9ea10d67e31a43ede2e2c693` (2026-11-13, "fix(core): tolerate malformed tool schemas instead of failing the whole call (#4780)").
**Local checkout:** `composio-upstream/` is a shallow, read-only reference that is never edited.
**Repro env:** `.venv-investigate/` (Python 3.12) with these packages:
- `composio 0.32.0` and `composio-client 2.1.32`
- `openai 3.50.0` and `anthropic 2.8.0`
- `google-genai 2.34.0`, `google-cloud-aiplatform 2.9.0` and `google-adk 2.14.1`
- `pydantic 2.14.3`

**Method:** all reproductions run offline. Sockets are blocked, no API keys are used and no tool is ever executed. Tools are built with `Tool.model_construct(...)`, the same pattern as `python/tests/test_google_adk_provider.py`.

The labels used in this report mean the following:
- **FACT:** observed in code or reproduced.
- **INDICATED:** strongly suggested by a static trace but not run end-to-end.
- **ASSUMPTION / RECOMMENDATION:** marked explicitly where it appears.

---

## 1. Summary

| # | Preliminary claim | Classification | One-line result |
|---|---|---|---|
| 1 | "Six Google compatibility failures" | **VERIFIED** (exact) | All 930 tools in the repo's offline corpus went through `composio_google.GoogleProvider.wrap_tool`. Exactly **6** raise `ParseError`: 5 from nested `examples`, 1 from `file_uploadable`. |
| 2 | "Missing action hints in some tools" (24%) | **VERIFIED** (exact, scoped) | **227 / 930 = 24.4%** of the corpus tools have none of `readOnlyHint` / `createHint` / `updateHint` / `destructiveHint`. The corpus is a CLI test mock (GitHub-heavy), not the full catalog. |
| 3 | "Duplicate tool names across groups" (285) | **VERIFIED** (exact, scoped) | `docs/public/data/toolkits.json` has 1,743 toolkits and 84,004 tools. It contains **285** groups of tools in the *same toolkit* that share a display `name` (case-insensitive). No slug is duplicated. |
| 4 | "Issues with `examples` and `file_uploadable`" | **VERIFIED** for Vertex (`composio_google`); transformed elsewhere | The Vertex adapter strips `examples` from top-level properties only, and passes nested `examples` and `file_uploadable` to a proto parser that rejects them. The Gemini, ADK and OpenAI-strict paths drop them silently. |
| 5 | "HEAD enum conversion issue" | **NOT VERIFIED as stated → reframed** | No tool schema in the corpus has `"HEAD"` in an `enum`. The only `"HEAD"` is an `examples` value (`GITHUB_GET_A_TREE.tree_sha`), and the only HTTP-method `Literal` is the SDK's `Tools.proxy()` argument. A real *general* enum issue does exist (§4.5): the Gemini adapter drops **all** `enum` values, and Vertex rejects **integer** enums. |

---

## 2. Repository map (FACT)

- **Monorepo layout:**
  - `python/`: the Python SDK (`python/composio/`) and provider packages (`python/providers/*`).
  - `ts/`: the TypeScript SDK (`ts/packages/core`) and providers (`ts/packages/providers/*`).
  - `docs/`: the docs site.
  - Guidance lives in root `AGENTS.md`, plus nested `python/AGENTS.md`, `python/providers/AGENTS.md` and `ts/packages/providers/AGENTS.md`.
- **The Tool type:** `composio.client.types.Tool = composio_client.types.tool_list_response.Item`. It is generated, lives in the external `composio-client` package, and the SDK fetches it from the Composio API (`python/composio/core/models/tools.py: Tools.get_raw_composio_tools` / `_get`). The schema field is `input_parameters` (JSON Schema).
- **Action hints are `tags`, not dedicated fields.** The vocabulary is `ToolRouterTag` in `python/composio/core/models/tool_router.py:121`: `readOnlyHint`, `createHint`, `updateHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`. These mirror MCP tool annotations. The Tool Router uses them to filter tools and for `require_approval` (e.g. `{'require_approval': ['destructiveHint']}`, `tool_router.py:933`).
- **The SDK mutates schemas before handing them to a provider** (`Tools._get`, `tools.py:594-609`):
  1. `FileHelper.enhance_schema_descriptions` always appends text to descriptions, such as "Please provide a value of type string." and "This parameter is required."
  2. `FileHelper.process_file_uploadable_schema` runs only when `dangerously_allow_auto_upload_download_files=True`. It rewrites `file_uploadable` leaves to `{type: string, format: path, ..., file_uploadable: True}` (`_files.py:874`). The flag is **kept**.
- **Shared schema utilities** (`python/composio/utils/`):
  - `json_schema.py: dereference_json_schema` inlines `$ref` and, in `sentinel` mode, turns a dangling `$ref` into a permissive object.
  - `shared.py: json_schema_to_model`, `alias_tool_input_schema`, `get_pydantic_signature_format_from_schema_params`.
  - `openapi.py: function_signature_from_jsonschema`.
  - `strict_schema.py: to_strict_json_schema`, which returns `.schema`, `.changes[path, reason]` and `.unsupported[path, keyword, detail]`.

### 2.1 Offline data sources in the repo (key finding)

| Source | Size | Contains | Usable for |
|---|---|---|---|
| `ts/packages/cli/test/__mocks__/tools.json` | 930 tools (823 GITHUB, 56 GOOGLE*, 51 GOOGLEDRIVE) | Full objects: `slug`, `name`, `description`, `tags` (hints), `input_parameters`, `output_parameters` | Provider compatibility, hint lint, schema lint |
| `docs/public/data/toolkits.json` | 1,743 toolkits, 84,004 tools | Per tool: `slug`, `name`, `description` (+ `instant` on 2,390) only. **No schemas, no tags.** | Name and description lint at catalog scale, duplicate-name groups, eval candidate groups |
| `python/tests/fixtures/json-schema-conversion/{object,strict}-cases.json` | Synthetic | A cross-SDK JSON-Schema conversion corpus | Edge-case regression inputs |

Both catalog files are snapshots, so how fresh they are relative to the live API is **unknown** (ASSUMPTION). The mock is a test fixture and may lag production metadata.

---

## 3. Provider conversion paths (FACT, Python)

| Provider package | Target SDK object | Entry point | Schema transformation |
|---|---|---|---|
| `composio_openai` (`python/composio/core/provider/_openai.py`) | `ChatCompletionToolParam` | `OpenAIProvider.wrap_tool` | **None.** It passes `input_parameters` through verbatim with `strict=None`. |
| OpenAI Responses (`_openai_responses.py`) | Responses `FunctionTool` | `OpenAIResponsesProvider.wrap_tool(strict=…)` | With `strict=True`, it applies `to_strict_json_schema`. That strips `examples`/`default`, makes optionals nullable+required and sets `additionalProperties: false`. On `.unsupported` it falls back to `strict: false` and logs a warning. |
| `composio_anthropic` | `ToolParam` | `AnthropicProvider.wrap_tool` | It only aliases reserved names (`alias_tool_input_schema`) and inlines `$ref`. |
| `composio_google` | **Vertex AI** `vertexai.generative_models.FunctionDeclaration` | `GoogleProvider.wrap_tool` (`providers/google/composio_google/provider.py:37`) | `dereference_json_schema(sentinel)`, then it removes `examples` from **top-level properties only**. Everything else goes to Vertex's proto `Schema` parser, which rejects unknown keys. |
| `composio_gemini` | **google-genai** AFC (a Python callable) | `GeminiProvider.wrap_tool` | It builds a typed Python signature, and google-genai derives the declaration via `FunctionDeclaration.from_callable`. Only type information survives, so `enum`, `const`, `pattern`, `minimum`, `format`, `title`, `default`, `examples` and **per-parameter `description`** are dropped. This is test-pinned in `python/tests/test_gemini_provider.py:545` (`AFC_CASES`). |
| `composio_google_adk` | `google.adk.tools.FunctionTool` | `GoogleAdkProvider.wrap_tool` | `function_signature_from_jsonschema` builds the declaration. Parameter descriptions are moved into the docstring. Every parameter is treated as required (code comment at `provider.py:90`). |

These are **three different Google adapters** and must not be conflated:
- `composio_google` → Vertex AI SDK;
- `composio_gemini` → google-genai AFC;
- `composio_google_adk` → Google ADK.

The **TypeScript** `@composio/google` (`ts/packages/providers/google/src/index.ts:134`) targets `@google/genai` instead. It dereferences, dedupes `required` and adds missing object types, but does **not** strip `examples`. That is a cross-SDK divergence; it was not run, because this investigation is Python-only.

---

## 4. Claim-by-claim evidence

Repro scripts live in `investigation/`, outside the upstream checkout:
- `repro_providers.py`: 20 synthetic cases × 6 provider paths;
- `repro_corpus.py`: 930 corpus tools × provider;
- `repro_metadata.py`: catalog statistics, stdlib only.

Raw outputs are in `investigation/results/`. To run a script, use `.venv-investigate/Scripts/python -I investigation/<script> [composio-upstream]`. The environment variable `REPRO_PROVIDERS=openai,gemini,…` limits the providers.

### 4.1 Six Google failures — VERIFIED

- **Code path:** `composio_google/provider.py:44-51`. It strips `examples` only at depth 1, then `FunctionDeclaration(parameters=…)` goes to the proto parser of `google.cloud.aiplatform.v1beta1.Schema`.
- **Repro:** `REPRO_PROVIDERS=google_vertex python -I repro_corpus.py composio-upstream` → `6 failures, all ParseError`:

| Tool | Failing key | Path |
|---|---|---|
| `GOOGLEDRIVE_FILES_MODIFY_LABELS` | `examples` | nested `items.properties.items…` |
| `GOOGLEDRIVE_UPDATE_PERMISSION` | `examples` | `properties[permission].properties[role]` |
| `GOOGLEDRIVE_UPLOAD_FILE` | `fileUploadable` | `properties[file_to_upload]` |
| `GOOGLE_ANALYTICS_CREATE_EXPANDED_DATA_SET` | `examples` | `properties[expandedDataSet].properties[dimensionNames]` |
| `GOOGLE_CLASSROOM_COURSE_WORK_PATCH` | `examples` | `properties[dueDate].properties[day]` |
| `GOOGLE_MAPS_MAPS_EMBED_API` | `examples` | `properties[directions_params].properties[avoid]` |

- **Synthetic cases:** the Vertex adapter also **raises** on integer `enum`, `anyOf` containing `{type: null}`, `type: ["string", "null"]` (as an `AttributeError: 'list' object has no attribute 'upper'`), `oneOf` and `const`. None of those occur in the 930-tool corpus, so the "6" figure is corpus-specific.
- **Existing tests:** `python/tests/test_google_provider.py` covers `$ref` dereferencing and execution routing only. There is no test for nested `examples` or `file_uploadable`.
- **End-to-end via `composio.tools.get(…)`:** INDICATED, not run, because that needs the API. `Tools._get` never strips `file_uploadable` (§2), so the same `ParseError` should occur.

### 4.1b Full corpus matrix (930 tools × provider path, FACT)

| Provider path | Hard failures | Most-dropped keywords (number of tools affected) |
|---|---|---|
| OpenAI (chat) | 0 | none (passthrough) |
| OpenAI Responses `strict=True` | **114 unsupported**. The provider would send these non-strict. Mostly `items` that are free-form objects. | `examples` 807, `default` 321 |
| Anthropic | 0 | none (`$ref` is inlined) |
| Google Vertex (`composio_google`) | **6 `ParseError`** (§4.1) | `examples` 890 (top level) |
| Gemini genai AFC (`composio_gemini`) | **1**: `GOOGLEDRIVE_UPDATE_PERMISSION`. `from_callable` fails with "Failed to parse the parameter permission … for automatic function calling" on a nested object with `additionalProperties: false` and nullable fields. | `title` 915, `examples` 895, `default` 355, **`enum` 179 of 182 tools that use it**, `format` 19 |
| Google ADK | 0 | `examples` 896, `default` 356, `enum` 3, `items` 1 |

`GOOGLEDRIVE_UPDATE_PERMISSION` fails on **both** Google paths, for different reasons.

### 4.2 Missing action hints — VERIFIED (scoped to the mock corpus)

- **Definition:** a tool has none of the four *action* hints `readOnlyHint`, `createHint`, `updateHint` and `destructiveHint`. `idempotentHint` and `openWorldHint` are modifiers, not actions.
- **Result:** **227 / 930 (24.4%).** 85 tools have no hint tag at all. Samples include `GITHUB_CREATE_AN_ISSUE`, `GITHUB_CREATE_AN_ISSUE_COMMENT` and `GITHUB_CREATE_A_BLOB`. Many are create-verb tools without `createHint`.
- **Destructive-verb slugs without `destructiveHint`: 16.** Examples: `GOOGLE_ADMIN_DELETE_USER`, `GOOGLE_CLASSROOM_COURSES_DELETE`, `GOOGLEDRIVE_DELETE_COMMENT`. Some are false positives, such as `GITHUB_DOWNLOAD_A_REPOSITORY_ARCHIVE_ZIP` (matches ARCHIVE) and `GITHUB_CREATE_A_REMOVE_TOKEN…`, so a lint rule here needs care.
- **No contradictory tags:** no tool is tagged both `readOnlyHint` and `destructiveHint`.
- **Caveats:**
  - The catalog-scale docs file has no tags, so the 24% applies to a GitHub-heavy 930-tool sample, not to all 84k tools.
  - Why hints matter is a FACT: `require_approval` and tag filters depend on them.

### 4.3 Duplicate tool names — VERIFIED (scoped)

- **Same toolkit, same display name** (case-insensitive) gives **285 groups**. Group sizes are 263×2, 14×3, 6×4, 1×5 and 1×12. These are typically legacy and alias slugs:
  - `SLACK_SEND_MESSAGE` vs `SLACK_CHAT_POST_MESSAGE` ("send message");
  - `GITHUB_SEARCH_ISSUES` vs `GITHUB_SEARCH_ISSUES_AND_PULL_REQUESTS`;
  - `COMPOSIO_WAIT_FOR_CONNECTION` vs `…_CONNECTIONS`.
- **Across toolkits:** 6,201 names are shared (e.g. "list users" in 112 toolkits). That's expected and is **not** a defect by itself.
- **The mock corpus shows the same pattern:** 41 duplicate names, e.g. `GITHUB_CREATE_AN_ISSUE` vs `GITHUB_ISSUES_CREATE`.
- **Slugs:** 0 duplicated anywhere.
- **Meaning:** slugs are what reach the LLM as function names, so a duplicate *display name* does not cause a provider collision. It does signal **near-duplicate tools** that an LLM must choose between. That makes these groups the natural, real-world input for the selection eval (Component C).

### 4.4 `examples` and `file_uploadable` — VERIFIED

Synthetic-case matrix from `repro_providers.py` (✗ = raises, "dropped" = silently removed, ✓ = preserved):

| Case | OpenAI | OpenAI strict | Anthropic | Google (Vertex) | Gemini (genai) | ADK |
|---|---|---|---|---|---|---|
| `examples` top level | ✓ | dropped | ✓ | dropped | dropped | dropped |
| `examples` nested / in `items` | ✓ | dropped | ✓ | **✗ ParseError** | dropped | dropped |
| `file_uploadable` top / nested | ✓ | ✓ | ✓ | **✗ ParseError** | dropped | dropped |

- **Corpus prevalence:** `examples` appears in 896 / 930 tools and `file_uploadable` in 1 (`GOOGLEDRIVE_UPLOAD_FILE`).

### 4.5 HEAD enum — NOT VERIFIED as stated; reframed as a general enum-handling finding

- **Where "HEAD" actually appears:**
  - `"HEAD"` appears in one corpus schema, as an **`examples`** value: `GITHUB_GET_A_TREE.properties.tree_sha.examples = ["master", "HEAD", …]`.
  - `Literal["GET", …, "HEAD"]` exists only as the `method` argument of the SDK method `Tools.proxy` (`tools.py:995`). That is not a tool schema.
  - `url_safety.py:224` handles HEAD for redirects. Again, not a tool schema.
- **Enum handling in a synthetic `{"type": "string", "enum": [... "HEAD"]}` case:**
  - **Preserved:** by OpenAI, Anthropic, Vertex and ADK. Nothing is HEAD-specific.
  - **Gemini (genai AFC):** **drops every `enum`**, string or integer alike, emitting only `{"type": "STRING"}`. This is **intentional and test-pinned** (`AFC_CASES` ids `enum` and `typeless-enum`). It is still semantic loss: the model is no longer told the allowed values, and the SDK rejects invalid values only *after* the call.
  - **ADK, untyped enum** (`{"enum": ["GET", "HEAD"]}` with no `type`): emits `{"title": "Method"}`, with neither type nor values.
  - **Vertex, integer enum:** **raises** (`expected string or bytes-like object, got 'int'`).
- **Possible origin of the claim (ASSUMPTION):** it may have come from the `HEAD` example value or from the proxy `Literal`. Neither is a conversion bug.

### 4.6 Other findings worth carrying forward (FACT)

- **Optional → required:** the Gemini and ADK declarations mark optional, non-nullable parameters as **required**. For example, `{limit (default 10), since}` with no `required` list becomes `required: ["limit", "since"]`. For ADK this is documented; for Gemini it is observed in the harness.
- **ADK and `oneOf`:** ADK collapses a `oneOf` of objects to a free-form `{"type": "object", "additionalProperties": true}`.
- **OpenAI strict mode reports** `additionalProperties` maps and unresolved `$ref` as `unsupported`. The provider then sends the tool non-strict. The checker can reuse the `.changes` / `.unsupported` output as-is.
- **Description statistics** (docs catalog, 84,004 tools):
  - 0 empty descriptions;
  - 678 whose description equals the name or slug after normalising (e.g. `GITHUB_GET_AN_ORGANIZATION`: "Get an organization");
  - 678 longer than 1,024 characters (a coincidence: the two sets do not overlap);
  - length p50 = 160, p95 = 537, p99 = 943, max = 60,023.

---

## 5. Existing tests and conventions (FACT)

- **Python tests** live in `python/tests/`, more than 80 files. Directly relevant:
  - `test_google_provider.py`, `test_gemini_provider.py` (`AFC_CASES` pins the AFC declarations), `test_google_adk_provider.py` (an offline, network-blocked pattern we reuse);
  - `test_strict_schema*.py`, `test_json_schema*.py`, `test_schema_*parity.py`, `test_provider_ref_contract.py`.
- **Commands** (from `python/`): `make tst` (pytest via nox), `make chk` (ruff + mypy), `make fmt`.
- **Conventions:** Ruff and mypy, pytest markers `unit` / `schema`, providers are optional imports via `pytest.importorskip`, and network access is blocked in schema tests.
- **Upstream tests in our env:** `pytest tests/test_google_provider.py tests/test_gemini_provider.py tests/test_google_adk_provider.py tests/test_strict_schema.py` gives **150 passed** in 37 s. The baseline is green, so the failures in §4 are gaps in test coverage, not broken tests.

---

## 6. Recommendation for Milestone 1 (RECOMMENDATION — not decided)

**Smallest useful architecture:** a standalone Python package (`tool_schema_doctor/`) that **imports the real adapters** rather than reimplementing them.

1. **Input loader:** reads `tools.json`-shaped files (the mock corpus format: slug, name, description, tags, input_parameters). The docs catalog can be an optional "names only" input.
2. **Compatibility checker:** runs each tool through the provider adapters under the network-blocked harness above and classifies the outcome as `ok` / `transformed` (with a keyword diff) / `error`. For OpenAI strict it reuses `to_strict_json_schema(...).unsupported` and `.changes`.
3. **Metadata linter:** first-pass rules, each backed by evidence above:
   - `missing-action-hint`;
   - `destructive-verb-without-destructiveHint` (warning, with an allowlist for known false positives);
   - `duplicate-display-name-in-toolkit`;
   - `description-repeats-name`;
   - `description-too-long` (threshold to be decided; p99 = 943).
4. **Report:** JSON plus Markdown.
5. **Selection eval (later milestone):** seed it from the 285 same-toolkit duplicate groups.

**Explicitly not recommended:**
- live API fetching (offline corpora suffice for the MVP);
- the TypeScript providers (a possible follow-up for cross-SDK divergence).

---

## 7. Limitations and open questions

- **Corpus scope:** the provider results come from a 930-tool, GitHub-heavy test mock. Real-catalog prevalence would need a live `tools.get` with an API key. That is optional and was not done.
- **Real-world impact of Gemini/ADK drops:** INDICATED from the declarations. No live model calls were made.
- **The six Vertex failures** are reproduced with `vertexai` from `google-cloud-aiplatform 2.9.0`. Other versions may behave differently.
- **Environment:** imports are slow on first run (Vertex about 70 s cold) because of the Windows R: drive. This does not affect correctness.
- **Open question:** should the Vertex adapter be treated as current or legacy? Google's own guidance has shifted from `vertexai.generative_models` toward `google-genai`. This needs checking against Google's current docs before any "this is a bug" framing in outreach.
