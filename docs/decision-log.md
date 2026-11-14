# Tool-Schema Doctor — Decision Log

Records material decisions and their reasons. Append-only; newest last.

---

### D1 — Build location: `tool-schema-doctor/` as a sibling package (M0)
**Decision:** Build the CLI in `R:\Internship_Outreach_prototype\Composio\tool-schema-doctor\`, a new sibling of `composio-upstream/`, `docs/`, `investigation/`.
**Reason:** Playbook §3.5 says use a separate directory; keeps upstream read-only and investigation artifacts intact. Workspace confirms the parent dir is the real project root.
**Status:** adopted.

### D2 — Reuse real adapters via lazy optional imports; never copy adapter logic (M0)
**Decision:** The compatibility checker imports and calls the real provider classes (`composio_openai`, `composio_anthropic`, `composio_google`, `composio_gemini`, `composio_google_adk`) and the SDK's `to_strict_json_schema`, exactly as `investigation/repro_providers.py` does. Each provider is imported lazily inside a try/except; if its SDK is missing, that provider is reported **unavailable/skipped**, not as a schema failure.
**Reason:** Playbook §3.6 + recovery rules. Each adapter pulls a heavy, sometimes conflicting SDK (`google-cloud-aiplatform`, `google-genai`, `google-adk`, `openai`, `anthropic`); forcing all of them would make the tool un-installable. The repro scripts already prove the reuse pattern works offline.
**Status:** adopted.

### D3 — Strict denominator separation (M0)
**Decision:** Never mix the two fixtures' counts. Mock (`ts/.../tools.json`, 930 tools, has tags+schemas) is the source for compatibility + hint lint. Docs catalog (`docs/public/data/toolkits.json`, 84004 tools, names/descriptions only) is the source for duplicate-name and description lint. Every reported stat names its source and notes the mock is GitHub-heavy, not the live catalog.
**Reason:** Playbook §5 Milestone 3 warning and validation §5. Prevents presenting a fixture rate as a catalog rate.
**Status:** adopted.

### D4 — Offline, network-blocked by default; no live LLM/API calls in the core tool (M0)
**Decision:** The CLI operates purely on local fixture/JSON inputs with no network. Any future tool-selection eval (M5) is opt-in, credential-gated via env vars, and never executes customer tools.
**Reason:** Playbook §2, §3.8, §5 M5. Matches the investigation harness (sockets blocked, execution hard-failed).
**Status:** adopted.

### D5 — Gemini full-corpus validation via targeted run, not full pass (M0)
**Decision:** For validation, confirmed Gemini's single corpus failure with a targeted live run on `GOOGLEDRIVE_UPDATE_PERMISSION` + a baseline, plus the saved artifact, instead of blocking on the slow 930-tool `from_callable` pass.
**Reason:** The full Gemini pass is minutes-long on this machine and adds no information beyond the one known failure; openai/anthropic/strict were already re-run live in full.
**Status:** adopted (validation only; the shipped checker still runs the full corpus per provider).

### D6 — Dev/demo environment & dependency strategy (M1)
**Decision:** The package declares `composio` as the only hard runtime dependency; the five provider SDKs are optional extras. CLI uses stdlib `argparse` + `dataclasses` + `json` (no new runtime dep). For running/testing the prototype now, install it editable into `.venv-investigate/` (which already has all adapters): `.venv-investigate\Scripts\python -m pip install -e tool-schema-doctor`.
**Reason:** Playbook wants a runnable, tested CLI with minimal deps. `.venv-investigate` already satisfies every adapter import, so the prototype is demonstrable immediately without a second heavy install. Optional extras keep a clean install usable with any subset of providers.
**Status:** adopted.

### D7 — Offline enforced lazily via `enforce_offline()` (M1/M2)
**Decision:** Instead of blocking sockets at package import (which would surprise any importer), expose `providers.enforce_offline()` that patches `socket.connect`/`getaddrinfo` to raise. The CLI calls it at startup and `compat.run()` calls it by default. Tool execution is hard-failed via `_never_execute`.
**Reason:** Same offline guarantee as the repro, without global side effects on import.
**Status:** adopted.

### D8 — Selection eval: Groq SDK + JSON mode + validation, not PydanticAI (M5)
**Decision:** Implement the tool-selection eval with the official `groq` SDK (OpenAI-compatible, `response_format={"type":"json_object"}`, temperature 0) plus explicit JSON parsing and candidate-set validation, instead of adding PydanticAI. Default model `openai/gpt-oss-20b` (verified available; **not** an assumed id). Dataset candidates reference real slugs; descriptions resolve from the real fixtures at runtime.
**Reason:** The task is a single structured call, not agent orchestration, so PydanticAI's weight isn't warranted (minimal-deps goal). The groq SDK is needed anyway because Groq sits behind Cloudflare, which 1010-blocks the default urllib User-Agent. Validation still enforces structured output. Verified the account's real model list via the API first (no `llama-3.1-*` present).
**Status:** adopted. (If PydanticAI is later desired, `selection_eval.run_eval` takes an injectable `selector`, so swapping the backend is a few lines.)

### D9 — Secret handling for the Groq key (M5)
**Decision:** The user-supplied `GROQ_API_KEY` is read only from the environment; for this run it was stored solely in the session scratchpad (outside the repo, auto-cleaned) and never written to any project file, report, or git. Live eval is opt-in (`--live`). Recommend the user rotate the key since it was shared in chat.
**Reason:** Playbook + global rules: never hardcode/commit secrets; keep credentials in env vars.
**Status:** adopted.
