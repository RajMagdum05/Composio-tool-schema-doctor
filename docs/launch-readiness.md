# Launch readiness: deploy & outreach (2026-11-14)

## TL;DR
- **Product quality:** ready. The CLI and dashboard work, every number on the page is backed by evidence, and 59/59 tests pass.
- **Deploy:** **not yet, but close.** Three blockers, none of them code: create a git repo, add a hosting requirements file, and rotate the Groq key. Publishing needs your account and your go-ahead.
- **Outreach:** **ready only with a reframe.** The original headline finding (Vertex rejects 6 tools) was **fixed upstream on 2026-11-13** in ComposioHQ/composio#4751. Lead with what's still open on the latest code.

---

## 1. What is solid now
- **Evidence-first dashboard.** Every claim links to:
  - the verbatim CLI output;
  - the upstream code at a pinned commit;
  - the regression tests behind it, with their pass status read from JUnit.

  A live per-tool re-run from the page matched the saved results.
- **Self-contained.** It renders with no `composio-upstream/` checkout present; a headless test pins this. The live re-run hides itself when its prerequisites are missing.
- **Data and licensing.** The data the app reads is 5.1 MB, with no secrets in any project file. The upstream fixtures are MIT-licensed and attributed in the footer.
- **Tests:** 59/59 passing.

## 2. Deploy: blockers
| # | Blocker | Why it matters | Who |
|---|---|---|---|
| 1 | **No git repo.** None of this work is under version control. | Hosts deploy from a repo, and outreach needs a link. | Me: `git init` + `.gitignore` + commit locally. You: push to GitHub. |
| 2 | **No requirements file for the host** (e.g. Streamlit Community Cloud). | The viewer only needs `streamlit` and `pandas`; the heavy provider SDKs are needed only for the local live re-run. | Me |
| 3 | **Rotate the Groq API key** that was pasted in chat. | It isn't in any file, but it was exposed in the conversation. | You |
| 4 | Choose a host and publish. | Publishing is public and outward-facing. | You decide; I can prepare everything |

**What goes in the repo:** `tool-schema-doctor/` (source, tests, `out/`) and `docs/`.

**Keep out:**
- `composio-upstream/` (third-party; it's referenced by commit instead);
- `.venv-investigate/`;
- `out/evidence/live/`;
- `build/`, `.pytest_cache/` and `tests/.wtmp/`.

## 3. Outreach: what changed and how to pitch it
**Upstream status** (checked 2026-11-14 via the GitHub API; recorded in `tool-schema-doctor/out/evidence/upstream_status.json`):
- **#1 Vertex adapter: fixed upstream.** [#4751](https://github.com/ComposioHQ/composio/pull/4751) was merged 2026-11-13 at 16:56 UTC, after our pin `6aa3f31`. It ships in Python SDK 0.33.0 ([#5394](https://github.com/ComposioHQ/composio/pull/5394), still open). It is **not yet verified with our own tool**: running the downloaded upstream code locally needs your explicit OK, or we can wait for the 0.33.0 release and rerun.
- **Still open on the latest `next`:** none of the code or data behind these findings changed since our pin.
  - **Gemini** drops `enum` on 179/182 tools and rejects `GOOGLEDRIVE_UPDATE_PERMISSION`. #4751 says `composio_gemini` is unaffected.
  - **OpenAI strict mode:** 114 tools silently fall back to non-strict.
  - **Missing action hints:** 227/930 tools, so `require_approval` can't target them; 12 of them have destructive-sounding names.
  - **Look-alikes:** 285 same-name groups in the catalog.

**How to pitch it (honest and stronger):**
1. *"My tool independently caught the bug class you just fixed in #4751, and here's what it still finds on `next`."* That proves the tool works, without claiming credit for a fix that already exists.
2. Lead with the **open** findings. The best hooks:
   - **The safety angle (hints → `require_approval`).**
   - **Gemini enum loss.** Your own #4751 already moves non-string enums into the description for Vertex; the same idea would fix Gemini.
3. **Better than a dashboard: send a small upstream contribution.** A focused issue or PR with a regression test, for example making the strict-mode fallback visible or proposing enum-in-description for Gemini, is the most convincing internship signal.
4. **Ask, don't assert:** Google deprecated `vertexai.generative_models` (June 24, 2025; removal scheduled June 24, 2026 — [Google deprecations page](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations)). It's worth asking whether `composio_google` is meant to stay on it. The installed 2.9.0 SDK shows no deprecation warning, so frame it as a question.
5. **State the limits up front:**
   - The 930 tools are a GitHub-heavy test fixture, not the live catalog.
   - The selection eval is exploratory: 27 curated tasks.

**Before sending anything:**
- [ ] Rotate the Groq key.
- [ ] Put the work in a public repo (see §2).
- [ ] Update `docs/demo.md`: its script and outreach blurb still present Vertex as an open bug.
- [ ] Optional: verify the Vertex fix with our tool (needs your OK), so the pitch can say "verified: 6 → 0".
- [ ] Record a 2–3 minute demo of the dashboard.
