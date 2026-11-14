# Tool-Schema Doctor — Execution Plan

Adaptive plan. Updated after each milestone. Status: M0–M4 done; M5 is a decision gate; M6 next.

| Milestone | Goal | Key outputs | Status |
|---|---|---|---|
| M0 | Validate the investigation | `milestone-0-validation.md`, progress, decision log | **done** |
| M1 | Smallest CLI architecture | `architecture.md`, this plan, `next-task.md` | **done** |
| M2 | Compatibility checker (all offline adapters) | package, `providers/compat/loader/model`, JSON, regression tests | **done** |
| M3 | Metadata linter | `lint.py` + 6 rules, unit tests, findings in JSON/MD | **done** |
| M4 | Combine workflow + reports | `report` command, JSON+MD, CLI tests, README | **done** |
| M5 | Tool-selection eval (built: key supplied) | `milestone-5-eval.md`, 27-task dataset, 3-model run | **done** |
| M6 | Quality pass + demo | review, demo script, outreach summary, README | **next** |

## M2 task breakdown (next)
1. Scaffold `tool-schema-doctor/` package (pyproject, src layout, README stub).
2. `model.py` — dataclasses from architecture §4.
3. `loader.py` — load mock + catalog shapes → `ToolRecord`; malformed-input handling.
4. `providers.py` — real-adapter registry, offline guard, `_never_execute`, lazy optional imports, `unavailable` handling. **Port the validated calls from `investigation/repro_providers.py` as library code (reuse, not copy adapter logic).**
5. `compat.py` — corpus × provider runner with per-tool isolation + keyword diff + schema-path extraction for Vertex/Gemini.
6. `cli.py` — `inspect` and `compatibility` subcommands; JSON to stdout/`-o`.
7. Install into `.venv-investigate`; run `compatibility` on the 930-tool mock; assert Vertex=6, strict=114, gemini=1, adk=0, openai=0, anthropic=0 (reproduce the validated numbers through the shipped CLI).
8. Regression tests: nested `examples`→Vertex error, `file_uploadable`→Vertex error, nested-object→Gemini error, baseline passes all.

**M2 acceptance:** offline CLI runs; per-tool/provider results recorded; regression tests pass; JSON report generated; real adapter code reused; one failing tool doesn't stop the corpus; unavailable deps are skipped not failed.

## Guardrails (all milestones)
- Offline only; no live LLM/API/customer-tool calls.
- `composio-upstream/` read-only; investigation artifacts not overwritten.
- No secrets; no commit/push/deploy without explicit approval.
- Denominators never mixed (mock vs catalog).
- Label results verified / hypothesis / recommendation. No "fixed" claim without a regression test.
