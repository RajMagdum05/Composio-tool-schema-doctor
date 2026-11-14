# Tool-Schema Doctor

QA for [Composio](https://github.com/ComposioHQ/composio) tool schemas. It runs every tool
through the **real** provider adapters (OpenAI, Anthropic, Google Vertex, Gemini, Google ADK),
lints the tool metadata, and shows what breaks or silently loses information, with evidence
for every claim. Offline: nothing is executed and no network is used for the checks.

**Analyzed:** Composio commit [`6aa3f31`](https://github.com/ComposioHQ/composio/commit/6aa3f31ecf38fc5f9ea10d67e31a43ede2e2c693)
· 930 tools × 6 adapters · 63 tests.

## See the results
**Live:** https://tool-schema-doctor.netlify.app

The dashboard reads saved evidence, so it needs only Streamlit and pandas:

```bash
pip install -r requirements.txt
streamlit run tool-schema-doctor/streamlit_app.py
```

Each finding opens to its evidence: the affected tools, the raw adapter errors, a link to the
upstream code at the pinned commit, the exact CLI command with its verbatim output, and the
regression tests that pin it.

### Host it
Two forms of the same page, built from the same saved evidence and the same `theme.css`:

| Form | For | How |
|---|---|---|
| **Static site** in `site/` | Netlify, Vercel, GitHub Pages, any file host | `python tool-schema-doctor/build_static.py`, then publish `site/` (configs: `netlify.toml`, `vercel.json`) |
| **Streamlit app** | Streamlit Community Cloud, or locally | `streamlit run tool-schema-doctor/streamlit_app.py` |

Streamlit needs a running Python server, so it can't run on Netlify or Vercel. The static site has the
same findings and evidence, plus a lookup for any of the 930 tools in plain JavaScript.

### Findings at a glance
| Finding | Status on Composio `next` |
|---|---|
| Vertex adapter rejects 6 tools (nested `examples`, `file_uploadable`) | **Fixed upstream** in [#4751](https://github.com/ComposioHQ/composio/pull/4751) after our pinned commit; not yet re-verified with this tool |
| Gemini drops `enum` on 179 of 182 tools, rejects 1 | Open |
| OpenAI strict mode unavailable for 114 tools (silent fallback) | Open |
| 227 of 930 tools have no action hint, so `require_approval` can't target them | Open |
| 285 same-name look-alike groups in the docs catalog | Open |

Status and sources: `tool-schema-doctor/out/evidence/upstream_status.json`.

**Limits:** the 930 schema tools are Composio's own CLI test fixture (GitHub-heavy), not the live
catalog; results reflect the installed adapter versions; the 27-task selection eval is small,
hand-curated and model-dependent.

## Run the CLI and regenerate the evidence
Needs the Composio provider packages, and a checkout of Composio at the pinned commit
(see [NOTICE.md](NOTICE.md)) next to this folder as `composio-upstream/`.

```bash
pip install -e "tool-schema-doctor[all,dashboard]"
python tool-schema-doctor/make_evidence.py        # runs every CLI command shown on the page + the tests
tool-schema-doctor report --input composio-upstream/ts/packages/cli/test/__mocks__/tools.json -o out/report
```
Full command reference: [tool-schema-doctor/README.md](tool-schema-doctor/README.md).

## Layout
| Path | What |
|---|---|
| `tool-schema-doctor/` | CLI package, tests, dashboard, saved evidence (`out/`) |
| `docs/` | Validation of the original investigation, architecture, decisions, progress log, launch checklist |
| `investigation/` | Scripts and raw output from the first investigation |

## Secrets
The optional selection eval reads `GROQ_API_KEY` from the environment. No key is stored in this
repository.

Third-party attribution: [NOTICE.md](NOTICE.md).
