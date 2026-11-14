# Tool-Schema Doctor

Offline developer QA for [Composio](https://github.com/ComposioHQ/composio) tool schemas.
It (1) checks whether tool schemas convert correctly for each **real** provider adapter,
(2) lints tool metadata with deterministic rules, and (3) runs an optional LLM
tool-selection evaluation. It **reuses the genuine Composio adapters** — it never
reimplements or copies their conversion logic — and the core tool makes no network
or LLM calls.

Built against upstream `ComposioHQ/composio` @ `6aa3f31` (branch `next`). See
`../docs/milestone-0-validation.md` for the verified findings this tool reproduces.

## Install

Use an environment that has the adapter SDKs. In this workspace that is `.venv-investigate`
(already has all five adapters + composio):

```
uv pip install -e tool-schema-doctor --python .venv-investigate/Scripts/python.exe
```

Fresh env with the providers you want (only `composio` is required; each adapter is an extra):

```
pip install -e "tool-schema-doctor[all]"
pip install -e "tool-schema-doctor[openai,anthropic]"   # subset
```

A provider whose SDK is not installed is reported **unavailable/skipped**, never as a failure.
The eval needs the `groq` extra: `pip install groq`.

### Streamlit evidence dashboard

Install the dashboard dependencies into an environment with the project package and provider SDKs, then run from the project root:

```
pip install -e "tool-schema-doctor[dashboard]"
python tool-schema-doctor/make_evidence.py        # runs the CLI commands + tests, records provenance
python -m streamlit run tool-schema-doctor/streamlit_app.py
```

The dashboard is evidence-first. It shows a short verdict and a prioritized fix list. Each fix includes:
- the affected tools and the raw adapter errors;
- a link to the upstream code at the pinned commit;
- the exact CLI command, with its verbatim output;
- the regression tests that pin the finding, with their pass status from the JUnit report.

`make_evidence.py` regenerates everything the page reads, under `tool-schema-doctor/out/evidence/`. Re-run it whenever the fixtures or adapter versions change.

## Commands

```
tool-schema-doctor inspect       --input <fixture.json>
tool-schema-doctor compatibility --input <fixture.json> [--providers ...] [--verbose] [-o out.json]
tool-schema-doctor lint          --input <fixture.json> [--rules ...] [--verbose] [-o out.json]
tool-schema-doctor report        --input <fixture.json> [--providers ...] [--rules ...] [--format json|markdown|both] [--no-compat] [--no-lint] [-o DIR]
tool-schema-doctor eval          [--dataset ...] [--corpus ...] [--model ...] [--live] [-o ...]
```

- **Providers:** `openai`, `openai_strict`, `anthropic`, `google_vertex`, `gemini`, `google_adk`.
- **Lint rules:** `missing-action-hint`, `destructive-verb-without-destructive-hint`,
  `duplicate-display-name-in-toolkit`, `description-repeats-name`, `description-empty`, `description-too-long`.
- **Exit codes:** `0` ran OK (findings are normal output); `2` bad usage/input; `1` internal error.

### Inputs
- **Mock shape** (full schemas + tags): `composio-upstream/ts/packages/cli/test/__mocks__/tools.json` (930 tools).
- **Catalog shape** (names/descriptions only): `composio-upstream/docs/public/data/toolkits.json` (84,004 tools).
  Compatibility and tag-based lint auto-skip on the catalog (it has no schemas/tags).

## Examples

```
# Compatibility over the 930-tool mock (all installed providers)
tool-schema-doctor compatibility --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o out/compat.json

# One combined JSON + Markdown report
tool-schema-doctor report --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o out/report-mock

# Catalog-scale metadata lint (no adapters needed)
tool-schema-doctor report --input composio-upstream/docs/public/data/toolkits.json --no-compat -o out/report-catalog

# Tool-selection eval — offline validation (no network), then live
tool-schema-doctor eval
tool-schema-doctor eval --live --model openai/gpt-oss-20b -o out/eval_report.json   # needs GROQ_API_KEY
```

## What it reproduces (verified)
- **Vertex (`composio_google`) fails on 6/930** tools: 5 on nested `examples`, 1 on `file_uploadable`.
- **OpenAI strict mode: 114/930** schemas unsupported (provider would fall back to non-strict).
- **Gemini: 1/930** (`GOOGLEDRIVE_UPDATE_PERMISSION`, nested object).
- **OpenAI / Anthropic / ADK: 0 hard failures** (ADK/Gemini/strict silently drop keywords — reported as `transformed`).
- **Missing action hints: 227/930 (24.4%)** on the mock; **285** within-toolkit duplicate display-name groups in the catalog.

## Limitations
- Offline results reflect the **installed adapter versions**; no live API/LLM calls in the compat/lint core.
- The 930-tool mock is **GitHub-heavy**; its percentages are fixture statistics, not live-catalog rates. The tool keeps the two fixtures' denominators separate.
- The eval depends on model + prompt (disclosed in every eval report); it only **selects** a tool and never executes one.

## Tests
```
.venv-investigate/Scripts/python -m pytest        # from tool-schema-doctor/
```
Covers loader shapes, the validated provider failures (regression tests), lint rules (positive+negative),
CLI exit codes, and the eval metrics/dataset integrity.

## Project docs
`../docs/`: `milestone-0-validation.md` (verified findings), `architecture.md`, `execution-plan.md`,
`decision-log.md`, `progress.md`, `milestone-5-eval.md`, `demo.md`.
