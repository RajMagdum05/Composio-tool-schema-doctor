# Tool-Schema Doctor — Progress Log

Persistent state for the adaptive execution run. Newest milestone last. Each entry: work done, changed files, commands, exact results, verified/disproved findings, limitations, decisions, next milestone, approval needed.

---

## Milestone 0 — Validate the investigation (read-only) — DONE

**Date:** 2026-11-13

**Work completed:** Independently re-ran all three reproduction scripts and cross-checked every reported count. Confirmed the scripts call the real Composio adapters (no reimplementation). Verified fixture provenance (git-tracked upstream at the SHA). Extracted exact failing schema paths for the six Vertex failures. Live-confirmed the Gemini failure on its one tool. Wrote the validation note.

**Changed / new files:**
- `docs/milestone-0-validation.md` (new) — independent validation note.
- `docs/progress.md`, `docs/decision-log.md` (new) — adaptive-protocol state files.
- `investigation/_validation_runs/metadata.json`, `.../corpus_vertex.json` (new re-run outputs; originals in `investigation/results/` untouched).
- `composio-upstream/` — **unchanged** (verified clean at `6aa3f31`).

**Commands run (from project root; `PY=.venv-investigate/Scripts/python.exe`):**
- `$PY -I investigation/repro_metadata.py composio-upstream` → metadata counts.
- `REPRO_PROVIDERS=google_vertex $PY -I investigation/repro_corpus.py composio-upstream` → Vertex.
- `REPRO_PROVIDERS=openai,anthropic $PY -I investigation/repro_corpus.py composio-upstream` → openai/anthropic/strict.
- Targeted live gemini/adk check on `GOOGLEDRIVE_UPDATE_PERMISSION` + `GITHUB_CREATE_AN_ISSUE`.
- `git -C composio-upstream` provenance checks (ls-files, rev-parse blob hashes).

**Exact results (re-run):** Vertex 6/930 ParseError (same IDs); missing action hints 227/930 = 24.4%; no-hint-at-all 85; within-toolkit dup-name groups 285; dup slugs 0; OpenAI strict 114/930; Gemini 1/930 (`GOOGLEDRIVE_UPDATE_PERMISSION`); ADK 0; docs catalog 1743 toolkits / 84004 tools; desc==name 678; desc>1024 678. Upstream tests: 150 cases from 86 functions (prior run).

**Verified:** all 6 headline findings reproduce exactly. **Disproved:** none (HEAD-enum was already reframed by the original author; confirmed correct to reframe).

**Limitations:** provider stats are from a 930-tool GitHub-heavy mock, not the live catalog. Gemini full-corpus re-run is slow (~930 `from_callable` builds); validated via targeted + saved artifact instead of waiting. Cold imports slow on the R: drive.

**Decisions:** see `docs/decision-log.md` D1–D4. Key: build reuses real adapters via lazy optional imports; keep mock (schemas+tags) and docs catalog (names only) denominators strictly separate.

**Next milestone:** M1 — design the smallest CLI architecture (`docs/architecture.md`, `docs/execution-plan.md`, `docs/next-task.md`).

**Approval required:** No. M1 is design/docs only, low-risk, in scope.

---

## Milestone 1 — Smallest CLI architecture — DONE

**Date:** 2026-11-13

**Work completed:** Designed the package: location, src layout, modules (model/loader/providers/compat/lint/report/cli), the real-adapter reuse contract, fixture formats, result model, optional-dependency behavior, error capture, JSON/MD output, CLI surface, exit codes, offline guarantees, and the test plan. Confirmed adapter package names/deps and `wrap_tool` signatures from upstream source.

**Changed / new files:** `docs/architecture.md`, `docs/execution-plan.md`, `docs/next-task.md` (new); `docs/decision-log.md` (+D6, D7).

**Decisions:** D6 (composio hard dep, provider SDKs optional extras, stdlib CLI, dev env = `.venv-investigate`), D7 (offline enforced lazily via `enforce_offline()`).

**Next milestone:** M2 — implement the compatibility checker. **Approval required:** No.

---

## Milestone 2 — Compatibility checker — IN PROGRESS

**Date:** 2026-11-13

**Work completed:** Scaffolded `tool-schema-doctor/` (pyproject, src layout, README). Implemented `model.py`, `loader.py` (mock + catalog shapes, malformed handling), `providers.py` (real-adapter registry, `enforce_offline`, `_never_execute`, lazy optional imports, keyword diff, schema-path locator), `compat.py` (per-tool isolation, unavailable handling, summary), `cli.py` (`inspect`, `compatibility`). Installed editable into `.venv-investigate` via `uv pip install -e`. Wrote 18 regression/unit tests.

**Commands & exact results:**
- `uv pip install -e tool-schema-doctor --python .venv-investigate/Scripts/python.exe` → installed 0.1.0.
- `inspect` on the 930 mock → examples 896, enum 182, file_uploadable 1 (matches validation).
- `compatibility --providers openai,openai_strict,anthropic,google_vertex,google_adk` on the 930 mock → **openai 930 ok; openai_strict 816 transformed + 114 error; anthropic 930 ok; google_vertex 911 transformed + 13 ok + 6 error; google_adk 924 transformed + 6 ok.** Reproduces the validated counts **through the shipped CLI**.
- `pytest -q` → **18 passed** (49s). Covers Vertex nested-examples/file_uploadable/top-level-stripped, Gemini enum-drop + real nested-object failure, baseline across all 6 providers, loader shapes/malformed, unavailable-not-error.

**Fixes:** corrected `first_path(nested_only=True)` so Vertex error paths point at the actual **nested** `examples` (segment-count check), not a stripped top-level one. Redirected pytest temp off the permission-locked global root via a project-local `wtmp` fixture.

**Status:** DONE. The shipped CLI reproduces the validated compat counts; 18 tests pass incl. the Gemini regression. Full 6-provider JSON report artifact generated in `tool-schema-doctor/out/report-mock/`.

**Approval required:** No.

---

## Milestone 3 — Metadata linter — DONE

**Date:** 2026-11-13

**Work completed:** Implemented `lint.py` with six deterministic rules, each with id/severity/rationale/evidence/remediation, plus rule-level skip when the input lacks the needed data (so a names-only catalog never yields bogus hint findings). Wired `lint` subcommand. Added `tests/test_lint.py` (7 tests, positive+negative per rule, allowlist, case-insensitive dup).

**Rules:** `missing-action-hint` (warning), `destructive-verb-without-destructive-hint` (info, with false-positive allowlist), `duplicate-display-name-in-toolkit` (info), `description-repeats-name` (warning), `description-empty` (warning), `description-too-long` (info, >1024).

**Exact results (real data, through the tool):**
- mock `missing-action-hint` = **227** (matches validation 227/930).
- mock `destructive-verb-without-destructive-hint` = **12** (16 raw − 4 allowlisted false positives).
- catalog within-toolkit duplicate-name groups = **285** (609 member findings: 263×2+14×3+6×4+1×5+1×12).
- Tag rules correctly **skipped** on the catalog with a stated reason (denominator discipline enforced by the tool).

**Approval required:** No.

---

## Milestone 4 — Combined workflow + reports — DONE

**Date:** 2026-11-13

**Work completed:** Implemented `report.py` (`build_report` + `render_markdown`) and the `report` subcommand producing JSON + Markdown with: provider summary table, failing-conversions table (tool/provider/error/schema-path), lint findings by rule/severity with examples, skipped checks, fixture provenance, and limitations. Clear exit codes (0 ran / 2 usage / 1 internal). Optimized `available_providers()` to use `find_spec` (inspect now ~1.6s vs ~minutes). Added `tests/test_cli.py` (7 CLI smoke tests incl. exit codes and file output).

**Artifacts generated:**
- `tool-schema-doctor/out/report-catalog/` (report.json + report.md): catalog lint at 84004-tool scale — 1965 findings (678 desc-repeats, 678 too-long, 609 dup-name members); compat + tag rules auto-skipped.
- `tool-schema-doctor/out/report-mock/` (building): full 6-provider compat + lint over the 930 mock.

**Tests:** full suite now 25 tests (loader 6, compat 11, lint 7... counts via `pytest`); CLI + lint fast subset = 14 passed.

**Approval required:** No.

---

## Milestone 5 — Tool-selection eval — DONE (user supplied Groq key = go-ahead)

**Date:** 2026-11-13

**Work completed:** Built `selection_eval.py` + bundled 27-task dataset (`data/eval_dataset.json`), `eval` CLI subcommand (offline validation by default; `--live` calls Groq), and 6 offline tests. Verified the account's real Groq models via API first (no `llama-3.1-*`; default `openai/gpt-oss-20b`). Ran 3 models live.

**Exact results (27 tasks, temp 0):** gpt-oss-20b **27/27 (1.000)**; qwen3.8-27b **27/27 (1.000)**; allam-2-7b **26/27 (0.963)**, miss on `t27` (the genuinely-close assignee task). 0 invalid slugs across all. Saved to `tool-schema-doctor/out/eval_report*.json`. Full write-up in `docs/milestone-5-eval.md`.

**Decisions:** D8 (groq SDK + JSON mode + validation over PydanticAI; verified model ids), D9 (secret handling: env only, scratchpad, never committed; recommend key rotation).

**Limitations:** capable models score 100% → these ambiguities are resolvable from descriptions; not evidence selection is universally easy. Expected answers author-curated (flagged needs-human-review).

**Approval required:** No further (key already supplied). **Security note:** recommend rotating the shared key.

---

## Milestone 6 — Quality pass + demo — DONE

**Date:** 2026-11-13

**Work completed:** Rewrote the README (full command surface, setup, examples, limitations). Wrote `docs/demo.md` (overview, architecture, reproduction, evidence tables, limitations, 2–3 min demo script, outreach summary, quality checklist). Assembled the authoritative combined mock report. Ran the full test suite.

**Exact results:**
- **Full test suite: 38 passed** (loader 6, compat 12, lint 7, cli 7, eval 6) in ~117s.
- **`tool-schema-doctor/out/report-mock/`** (report.json + report.md): 6-provider compat (openai 930 ok; strict 816t/114e; anthropic 930 ok; vertex 911t/13ok/6e; gemini 929t/1e; adk 924t/6ok) + mock lint (329 findings) with a **121-row failing-conversions table** and correct nested schema paths.
- **`out/report-catalog/`**: catalog lint (1965 findings), compat + tag rules auto-skipped.
- **`out/eval_report*.json`**: 3-model selection eval.
- Upstream checkout **unchanged** at `6aa3f31`; **no secret** in any project file.

**Status:** All milestones complete. The deliverable is a working, tested offline CLI.

---

## Final state (2026-11-13)
- **Package:** `tool-schema-doctor/` — `inspect` / `compatibility` / `lint` / `report` / `eval`. One hard dep (`composio`); provider SDKs optional extras.
- **Tests:** 38 passing.
- **Reproduced & regression-tested:** Vertex 6, strict 114, gemini 1, missing-hint 227/930, dup-name 285 (catalog).
- **Eval:** 27 tasks; gpt-oss-20b & qwen3.8-27b 100%, allam-2-7b 96.3%.
- **Docs:** milestone-0-validation, architecture, execution-plan, decision-log (D1–D9), milestone-5-eval, demo.
- **Open item for the user:** rotate the Groq key (shared in chat); decide Vertex "current vs legacy" framing before outreach.

---

## Verification pass (re-test everything) — DONE

**Date:** 2026-11-14

**Work completed:** Re-ran the full test suite, smoke-tested every CLI command and all error paths, and reviewed the modules for edge cases. Applied three hardening fixes and added tests.

**Checks (all green):**
- Full suite: **48 passed** (was 38; added test_report.py (3) + parse_selection edge tests (7)).
- CLI: `inspect`/`lint`/`compatibility`/`report`/`eval` all exit 0; error paths (`missing input`, `bad rule`, `bad provider`, `eval --live` without key) all exit 2 with clear messages.
- `report --format json` emits valid JSON (catalog: 1965 findings, 2 rules skipped).

**Fixes applied:**
1. **UTF-8 stdout/stderr** — `cli.main` now reconfigures stdio to UTF-8, preventing `UnicodeEncodeError` when printing reports/findings with non-cp1252 characters (e.g. emoji in a tool description) on a Windows console. Verified: emoji→stdout under `PYTHONIOENCODING=cp1252` now exits 0 (would have crashed).
2. **`ensure_ascii=False`** on all JSON emitters so Unicode is written literally (valid UTF-8) rather than `\uXXXX`-escaped.
3. **`parse_selection` guard** — returns `(None, "")` for non-dict/garbage LLM output instead of risking an AttributeError.
4. Fixed the stale `cli.py` module docstring (listed only M2 commands).

**New/changed files:** `cli.py`, `selection_eval.py`, `tests/test_report.py` (new), `tests/test_eval.py` (+edge tests).

**Approval required:** No.

---

## Evidence-first dashboard pass — DONE

**Date:** 2026-11-14

**Work completed:** Rebuilt `streamlit_app.py` around three questions: what's broken, what to fix first, and why to believe it.
- **Verdict:** four numbers.
- **Fix list:** five prioritized fixes. Each gives an owner, why it matters and the concrete fix, with collapsed evidence: affected tools, raw adapter errors, an upstream code link at the pinned SHA, the exact CLI command plus its verbatim output, and the pinning regression tests with their pass status read from JUnit XML.
- **Further sections:** a per-tool lookup with a live re-run button that calls the real CLI, all results, and provenance.

New `make_evidence.py` regenerates everything the page reads. It does not hand-edit any number.

**Exact results:** every evidence CLI command exited 0. The full verbose run took 1005s. Tests passed **49/49** (adds `test_openai_strict_reports_sdk_reason_for_free_form_object`). The live re-run of `GOOGLEDRIVE_UPLOAD_FILE` from the page exited 0 and matched the saved results for all six providers.

**Fixes:**
- **CLI:** the strict-mode error message now includes the SDK's reason, using the same `<path>: <keyword> (<detail>)` format as the SDK's own fallback warning.
- **Strict-mode cause counts:** now computed from `to_strict_json_schema`, not from the length-capped message text. Parsing the capped text had invented a fake keyword (`additionalPrope`). The corrected counts are 97 free-form object tools and 27 arbitrary-key-map tools; the earlier figure of 26 was low.
- **Correction:** `docs/milestone-0-validation.md` had the two fixture blob hashes **swapped**. Verified with `git rev-parse` and `git hash-object`: `tools.json` = `b28f3c96…` and `toolkits.json` = `6a81b753…`.

**Known limit:** compatibility messages are still capped at 400 characters in the CLI JSON, so a few long strict-mode messages are cut mid-word in the verbatim output. The dashboard's counts are unaffected.

---

## Full adapter messages + scoped offline mode — DONE

**Date:** 2026-11-14

**Changes:**
- **Message cap raised.** Adapter error messages were capped at 400 characters, which cut 6 tools' messages mid-word. The worst, `GITHUB_UPDATE_BRANCH_PROTECTION`, has 11 strict-mode paths in 1,355 characters. Messages are now kept whole up to 4,000 characters, and any longer message is labelled `…[truncated N chars]` instead of being cut silently. The Markdown report preview marks cuts with "…".
- **Bug found and fixed while testing.** `run_compatibility()` used to block sockets **for the rest of the process**, so any long-lived caller (a notebook, a server, Streamlit) lost networking. It now uses a scoped, nesting-safe `providers.offline()` context manager that restores sockets afterwards, including when the run raises. `enforce_offline()` stays as the explicit permanent option.
- **Dashboard.** "Check a tool" now shows the complete adapter error. Migrated off the deprecated `use_container_width` argument.
- **Tests added:**
  - `tests/test_dashboard.py`: a headless Streamlit `AppTest` smoke test covering render, metric labels, five fixes with all-green pinned tests, and the full untruncated error.
  - Three offline-scope tests.
  - Two message-cap tests.
- **`make_evidence.py --tests-only`** refreshes only the test results.

**Exact results:** a full evidence regeneration exited 0 for every command, and the summary numbers are unchanged. All 121 error rows are complete: the longest is 1,355 characters and none are truncated. Tests: **57/57 passed**. The dashboard shows 57/57 with no exceptions.

---

## Dashboard polish + launch-readiness review — DONE

**Date:** 2026-11-14

**Dashboard changes:**
- A header band with proof chips (commit, scope, offline, tests passing), numbered fix cards showing severity and owner, generic reproduce commands, and an MIT attribution footer.
- **Runs without the local checkout:** the tags it needs are now saved in the evidence file, and the live re-run is hidden when its prerequisites are missing.

**Major finding:** the Vertex adapter finding was **fixed upstream** in ComposioHQ/composio#4751, merged 2026-11-13 at 16:56 UTC after our pin, and shipping in Python SDK 0.33.0. Checked via the GitHub API. Since our pin, `next` has 11 new commits; in scope, only `composio_google/provider.py` and its test changed. So the Gemini, strict-mode, hints and look-alike findings still hold.
- The dashboard now labels the Vertex finding FIXED UPSTREAM and lists it last. The status and sources are in `out/evidence/upstream_status.json`.
- **Not verified locally yet:** the safety classifier blocked running the downloaded upstream file without explicit user permission. That was the correct call, and I did not try to work around it.

**Tests:** 59/59 passed. New tests cover the dashboard without the checkout and the fixed-upstream ordering.

**Readiness:** see `docs/launch-readiness.md`. Deploy is blocked by: no git repo, no hosting requirements file, and the Groq key needing rotation. Outreach is ready only with the reframe described there.

---

## Repo and deploy setup — DONE (local only; nothing pushed)

**Date:** 2026-11-14

**Done:**
- `git init` on `main`, with `.gitignore`, `.gitattributes`, a root `README.md`, `NOTICE.md` (Composio MIT attribution, pinned commit and fixture hashes) and a root `requirements.txt` that the host will find. First commit: `abfb367`, 71 files.
- **Audit before committing:** removed one username-bearing path from `investigation/results/synthetic_openai_gemini_adk.json` and the hostname from the JUnit XML (`make_evidence.py` now clears the hostname itself). No tokens or machine paths remain in tracked files. `composio-upstream/`, the venv and `.claude/` are ignored.
- `pyproject.toml` `dashboard` extra now requires `streamlit>=1.67,<2` (the tested version).

**Verified on a clean clone of the commit, in a fresh environment with only `requirements.txt` installed (streamlit 1.67.0, pandas 3.1.1):**
- The dashboard renders with no exceptions: 4 headline numbers, 5 fix cards, all pinned tests green.
- Single-tool lookup shows the full 11-path error.
- The live-run button is correctly hidden without the checkout.
- A real `streamlit run` served HTTP 200 with no errors in its log.

**Left for the user:** rotate the Groq key; choose a license; create a GitHub repo and push; choose a host. `docs/demo.md` still presents the Vertex finding as an open bug and must be updated before outreach.

---

## Dashboard restyle and public deploy: DONE

**Date:** 2026-11-14

- Restyled the dashboard after the look of composio.dev (palette, type and layout only; no logos), with an "Independent" strip and footer stating it is not affiliated with Composio. Shared `theme.css`.
- Streamlit cannot run on Netlify or Vercel, so `build_static.py` renders the same page as static HTML plus a JavaScript lookup for all 930 tools. Tests check parity with the Streamlit page, evidence links, and that nothing personal or secret is published. 63/63 tests pass.
- **Deployed to Netlify: https://tool-schema-doctor.netlify.app** (the user signed in through the CLI's browser approval). Verified live over HTTP and in a browser.
- The Netlify CLI keeps its auth token in a plaintext file in the user profile. `netlify logout` removes it.
