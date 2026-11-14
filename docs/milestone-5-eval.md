# Milestone 5 — LLM Tool-Selection Evaluation

**Date:** 2026-11-13 · **Status:** built and run (user supplied a Groq key = go-ahead).

## Decision: build it (justified)
The Playbook makes M5 conditional on real selection ambiguity. The validated duplicate-name findings (285 within-toolkit groups in the catalog, mostly deprecated aliases; plus functional near-duplicates in the mock) are genuine ambiguity. So a selection eval is justified. It is **selection only** — it never executes a Composio tool.

## What it does
- A curated dataset of **27 ambiguous tasks** (`src/tool_schema_doctor/data/eval_dataset.json`). Each task: a natural-language user request, 2–3 **real** candidate tool slugs, a human-curated expected slug, rationale, ambiguity category, and difficulty. Every task is flagged `review: needs-human-review`.
- Candidate **descriptions are resolved from the real upstream fixtures at runtime** (mock + catalog), so nothing is hand-transcribed; the offline validator fails if any slug is unknown (all 27 resolve).
- Categories: `deprecated-alias`, `create-variant`, `read-vs-write`, `scope`, `functional-overlap`, `cross-toolkit`, `trap-keyword`.
- The model is asked for structured JSON `{chosen_slug, reasoning}`, parsed and validated against the candidate set (case-tolerant). Metrics: accuracy, incorrect-selection rate, invalid-slug count, and breakdowns by category and difficulty. Model id, prompt version, and a model/prompt-dependence disclosure are recorded in every report.

## Verified facts first (no assumed identifiers)
- Queried the Groq models API with the supplied key: **no `llama-3.1-8b-instant`** on this account. Usable instruction models: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `allam-2-7b` (others are audio/guard models). Default model: `openai/gpt-oss-20b`.
- The Groq endpoint is behind Cloudflare, which 1010-blocks the default `Python-urllib` User-Agent; the `groq` SDK sends a proper UA, so the shipped tool uses the SDK.

## Results (live, temperature 0, 27 tasks)
| Model | Accuracy | Correct | Invalid slugs | Misses |
|---|---:|---:|---:|---|
| `openai/gpt-oss-20b` | **1.000** | 27/27 | 0 | — |
| `qwen/qwen3.8-27b` | **1.000** | 27/27 | 0 | — |
| `allam-2-7b` (weak baseline) | **0.963** | 26/27 | 0 | `t27` |

- **Representative success:** the two capable models select correctly on every task, including keyword traps (e.g. "remove only the 'bug' label" → `REMOVE_A_LABEL`, not `SET_LABELS`; "download source as zip" → archive tool, not `GET_A_REPOSITORY`).
- **Representative failure:** `allam-2-7b` misses `t27` ("add octocat as an assignee without changing other fields") — it picks `GITHUB_UPDATE_AN_ISSUE` instead of `GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE`. This is the task flagged as genuinely close (UPDATE_AN_ISSUE's own description says it can set assignees), so the miss is interpretable, not a harness bug.
- All models produced **well-formed structured output** (0 invalid slugs), so the JSON-mode + validation path is reliable here.

## Honest limitations (hypothesis vs verified)
- **Verified:** the counts and misses above, reproducible with the saved reports in `tool-schema-doctor/out/eval_report*.json`.
- **Interpretation (hypothesis):** 100% on the capable models suggests these particular ambiguities are resolvable from descriptions + explicit cues; it is **not** evidence that tool selection is universally easy. A larger/adversarial dataset would likely find failure modes.
- Results depend on model + prompt (disclosed in every report). Re-running may vary slightly despite temperature 0.
- Expected answers are author-curated; `t27`'s expected is defensible but debatable, which is why it is the one that discriminates.

## Safety
- Opt-in: `--live` only; otherwise the command just validates the dataset offline (no network).
- `GROQ_API_KEY` is read from the environment and **never written to any project file or committed** (verified: no Groq key token appears anywhere under `tool-schema-doctor/`, `docs/`, or `investigation/`). The key lived only in the session scratchpad for this run and was deleted afterward. **Recommend rotating the key** since it was shared in chat.
- The evaluator sends only tool slugs + descriptions; it never calls a Composio tool.

## How to reproduce
```
# offline (no network): validate the dataset
tool-schema-doctor eval

# live (needs GROQ_API_KEY): run the selection eval
set GROQ_API_KEY=...            # PowerShell: $env:GROQ_API_KEY="..."
tool-schema-doctor eval --live --model openai/gpt-oss-20b -o out/eval_report.json
```
