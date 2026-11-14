# Tool-Schema Doctor — Architecture (Milestone 1)

**Date:** 2026-11-13 · **Status:** design, grounded in inspected code at upstream `6aa3f31`.

A small, offline, developer-facing Python CLI that (1) checks whether Composio tool schemas convert correctly for each real provider adapter, and (2) lints tool metadata. It **reuses the real adapters** and never reimplements or copies their logic.

---

## 1. Location & packaging

```
tool-schema-doctor/                 # new sibling of composio-upstream/, docs/, investigation/
  pyproject.toml                    # package: tool-schema-doctor ; import: tool_schema_doctor
  README.md
  src/tool_schema_doctor/
    __init__.py
    model.py                        # dataclasses: ToolRecord, CompatResult, LintFinding, Report
    loader.py                       # fixture JSON -> list[ToolRecord]
    providers.py                    # real-adapter registry, lazy optional imports, offline guard
    compat.py                       # corpus x provider -> list[CompatResult]
    lint.py                         # deterministic metadata rules -> list[LintFinding]  (M3)
    report.py                       # JSON + Markdown emitters
    cli.py                          # argparse entrypoint: inspect | compatibility | lint | report
  tests/
    fixtures/                       # tiny hand-written schemas for positive/negative unit tests
    test_*.py
```

- **Runtime deps:** `composio` only (hard). Provider SDKs are **optional extras**: `openai`, `anthropic`, `google-cloud-aiplatform` (Vertex), `google-genai` (Gemini), `google-adk`. CLI uses **stdlib `argparse` + `dataclasses` + `json`** — no new runtime dependency beyond composio + whichever provider SDKs are installed. (`pydantic` is available transitively but the tool uses dataclasses to stay decoupled.)
- **Extras:** `pip install -e "tool-schema-doctor[openai,anthropic,google,gemini,adk]"` or `[all]`.
- **Dev/demo environment:** `.venv-investigate/` already has all five adapters + composio 0.32.0. Decision D6: install the package into that env for running/testing now (`\.venv-investigate\Scripts\python -m pip install -e tool-schema-doctor`), so the prototype is runnable immediately. A fresh env works too via the extras.

## 2. Adapter reuse (the core contract)

`providers.py` holds a registry; each provider is a lazy callable mirroring `investigation/repro_providers.py` (the validated pattern), but packaged. On import, `providers.py` blocks the network (`socket.connect`/`getaddrinfo`) and defines a `_never_execute` callback that raises if any tool execution is attempted.

| id | import | conversion call (real code) | wrap_tool arity |
|---|---|---|---|
| `openai` | `composio_openai.OpenAIProvider` | `.wrap_tool(tool)["function"]["parameters"]` | `(tool)` |
| `openai_strict` | `composio.utils.strict_schema.to_strict_json_schema` | `to_strict_json_schema(tool.input_parameters)`; `.unsupported` → incompatible | n/a |
| `anthropic` | `composio_anthropic.AnthropicProvider` | `.wrap_tool(tool)["input_schema"]` | `(tool)` |
| `google_vertex` | `composio_google.GoogleProvider` | `.wrap_tool(tool).to_dict()["parameters"]` | `(tool)` |
| `gemini` | `composio_gemini.GeminiProvider` + `google.genai` | `.wrap_tool(tool, _never_execute)` → `FunctionDeclaration.from_callable(...)` | `(tool, execute)` |
| `google_adk` | `composio_google_adk.GoogleAdkProvider` | `.wrap_tool(tool, execute_tool=_never_execute)._get_declaration()` | `(tool, execute)` |

A `Tool` is built exactly as the tests/repro do: `composio.client.types.Tool.model_construct(slug=…, description=…, input_parameters=…)`. **No schema is mutated** by the tool itself; transformations come only from the adapters.

**Optional-dependency rule (Playbook recovery):** each provider call is wrapped so that `ImportError`/`ModuleNotFoundError` on its SDK → status `unavailable` (reported as *skipped*), **never** counted as a schema `error`.

## 3. Input (fixture) format

Two shapes, auto-detected by fields present:
- **Full mock shape** (`ts/packages/cli/test/__mocks__/tools.json`): JSON array of `{slug, name, description, tags[], input_parameters{}, output_parameters{}, available_versions}`. Drives compatibility + hint/schema lint.
- **Catalog shape** (`docs/public/data/toolkits.json`): `{toolkits:[{slug, tools:[{slug, name, description}]}]}` — names/descriptions only. Drives name/description lint at scale; compatibility is **skipped** (no schemas) with a clear note.

`loader.py` normalizes both into `list[ToolRecord]` and records which capabilities each record supports (has_schema, has_tags).

## 4. Result model (`model.py`, dataclasses)

```
ToolRecord(slug, name, description, tags: list[str], input_parameters: dict|None, source: str)
CompatResult(slug, provider, status, error_type=None, message=None, schema_path=None,
             dropped_keywords: list[str]=[], added_keywords: list[str]=[])
    status ∈ {ok, transformed, error, unavailable, skipped}
LintFinding(rule_id, severity, slug, toolkit=None, field=None, message, evidence, remediation)
    severity ∈ {error, warning, info}
Report(meta{generated_at, upstream_sha, input_path, input_source, counts},
       compatibility: list[CompatResult], lint: list[LintFinding], skipped: list[str], limitations: list[str])
```

- `transformed` = converted OK but dropped/added schema keywords (keyword diff, as in the repro) — informational, not a failure.
- `schema_path` is filled for Vertex/Gemini where the offending path is derivable (first nested `examples`/`file_uploadable`/parse target).

## 5. Error capture per provider

`compat.py` runs each `ToolRecord` × selected provider inside try/except:
- success → `ok` or `transformed` (keyword diff non-empty).
- `ImportError`/`ModuleNotFoundError` for the SDK → `unavailable` (once per provider, short-circuits the rest).
- any other exception → `error` with `error_type`, truncated `message`, and `where` (last traceback frame under site-packages).
One failing tool never stops the run (per-tool isolation). No hardcoded expected totals; counts are computed.

## 6. Output (`report.py`)

- **JSON:** the `Report` dataclass serialized (documented structure) — machine-readable, deterministic ordering (sorted by slug, provider).
- **Markdown:** human-readable — summary counts by provider (ok/transformed/error/unavailable), a failures table (tool, provider, error, path), lint findings grouped by rule+severity, skipped checks, unavailable deps, **fixture provenance**, and limitations.

## 7. CLI surface (`argparse`)

```
tool-schema-doctor inspect       --input <fixture>                      # load+summary, no adapters
tool-schema-doctor compatibility --input <fixture> [--providers a,b]    # per-tool compat (JSON to stdout/-o)
tool-schema-doctor lint          --input <fixture> [--rules ...]        # metadata findings
tool-schema-doctor report        --input <fixture> [--format json|markdown|both] [-o DIR]
```

- `--providers` defaults to all available; unavailable ones are listed as skipped.
- **Exit codes:** `0` = ran successfully (findings/failures are normal output, not a crash); `2` = bad usage / invalid input file; `1` = unexpected internal error. This keeps "tools have issues" distinct from "the CLI broke".

## 8. Offline & safety guarantees

- No network: sockets blocked in `providers.py`; no live LLM/API/customer-tool calls anywhere.
- `composio-upstream/` is never imported-from-source or edited; the installed adapter packages are used.
- No secrets; nothing read from env except (future, M5) an opt-in eval key.

## 9. Testing plan

- `loader`: both fixture shapes, malformed input → clear error.
- `providers`/`compat`: tiny hand-written schemas reproducing the validated cases — nested `examples` → Vertex error; `file_uploadable` → Vertex error; `GOOGLEDRIVE_UPDATE_PERMISSION`-like nested object → Gemini error; baseline passes all. Regression tests assert these specific behaviors.
- `lint` (M3): positive + negative cases per rule.
- `cli`: smoke tests for each subcommand on a 3–5 tool fixture; exit codes.

## 10. Acceptance (M1)

- [x] Architecture backed by inspected paths and real import behavior (§2 table).
- [x] No copied adapter logic (reuse-only contract).
- [x] Inputs (§3), outputs (§4/§6), errors (§5), tests (§9) defined.
- [x] Minimal dependencies, offline operation (§1, §8).

No unresolved material decision → proceed to M2 (vertical-slice compatibility checker, Vertex first).
