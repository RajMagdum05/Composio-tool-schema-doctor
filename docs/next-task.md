# Next Task

**Status:** All milestones (M0–M6) complete. Tool-Schema Doctor is a working, tested offline CLI.

**What exists:**
- `tool-schema-doctor/` package: `inspect` / `compatibility` / `lint` / `report` / `eval`; 38 tests passing.
- Reports in `tool-schema-doctor/out/` (report-mock, report-catalog, eval_report*).
- Docs in `docs/` (validation, architecture, decision-log, execution-plan, milestone-5-eval, demo, progress).

**No pending milestone.** Optional follow-ups the user may choose:
1. **Rotate the Groq API key** (it was shared in chat) — security hygiene.
2. Decide the **Vertex "current vs legacy"** framing vs google-genai before external outreach.
3. Optional extensions (only if asked): TypeScript provider coverage; a live `composio.tools.get()` path behind an API key to measure real-catalog prevalence; a larger/adversarial eval dataset to find model failure modes.

**To run the prototype:**
```
uv pip install -e tool-schema-doctor --python .venv-investigate/Scripts/python.exe
.venv-investigate/Scripts/python -m tool_schema_doctor.cli report --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o tool-schema-doctor/out/report-mock
```
Report: `tool-schema-doctor/out/report-mock/report.md`.
