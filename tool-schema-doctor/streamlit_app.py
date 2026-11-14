"""Tool-Schema Doctor — evidence-first dashboard.

Answers three questions for a Composio engineer, in this order:
  1. What's broken, and how bad is it?          (verdict)
  2. What should I fix first, and why?          (prioritized fix list)
  3. Why should I believe it?                   (evidence under every claim)

Everything shown is read from files produced by the CLI (tool-schema-doctor/out/).
Each finding shows the exact CLI command and its verbatim output, a link to the
upstream code at the pinned commit, and the regression tests that pin it.

Generate the evidence, then run (from the project root):
    .venv-investigate/Scripts/python tool-schema-doctor/make_evidence.py
    .venv-investigate/Scripts/python -m streamlit run tool-schema-doctor/streamlit_app.py
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
EV = OUT / "evidence"
MOCK = "composio-upstream/ts/packages/cli/test/__mocks__/tools.json"
CATALOG = "composio-upstream/docs/public/data/toolkits.json"

st.set_page_config(page_title="Tool-Schema Doctor", page_icon="🩺", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 1.4rem;}
[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); border-radius: 14px; padding: .85rem 1rem;
  background: rgba(128,128,128,.05);}
[data-testid="stMetricValue"] {font-size: 2.1rem;}
.hero {border: 1px solid rgba(99,145,230,.35); border-radius: 18px; padding: 1.4rem 1.6rem 1.2rem;
  background: linear-gradient(120deg, rgba(64,120,220,.16), rgba(64,120,220,.03)); margin-bottom: 1.1rem;}
.hero .eyebrow {font-size: .74rem; letter-spacing: .14em; text-transform: uppercase; font-weight: 700; opacity: .7;}
.hero h1 {font-size: 2.15rem; margin: .15rem 0 .4rem; padding: 0;}
.hero p {font-size: 1.04rem; margin: 0 0 .9rem; opacity: .9; max-width: 860px;}
.chips {display: flex; flex-wrap: wrap; gap: .45rem;}
.chip {font-size: .8rem; padding: .22rem .65rem; border-radius: 999px; border: 1px solid rgba(128,128,128,.35);
  background: rgba(128,128,128,.08); color: inherit !important; text-decoration: none !important;}
a.chip:hover {border-color: rgba(99,145,230,.8);}
.chip.ok {border-color: rgba(46,160,67,.6); background: rgba(46,160,67,.14);}
.owner {font-size: .82rem; opacity: .75;}
.foot {font-size: .8rem; opacity: .65; text-align: center; padding-top: .4rem;}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data
def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@st.cache_data(show_spinner=False)
def load(mtimes: tuple):  # mtimes only invalidates the cache when files change
    return {
        "ev": read_json(EV / "evidence.json"),
        "full": read_json(OUT / "compat_full.json"),
        "mock_rep": read_json(OUT / "report-mock" / "report.json"),
        "cat_rep": read_json(OUT / "report-catalog" / "report.json"),
        "evals": {
            "gpt-oss-20b": read_json(OUT / "eval_report.json"),
            "qwen3.8-27b": read_json(OUT / "eval_report_qwen.json"),
            "allam-2-7b": read_json(OUT / "eval_report_allam.json"),
        },
    }


def _mt(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(show_spinner=False)
def mock_tags() -> dict:
    """slug -> tags, straight from the upstream schema fixture."""
    try:
        return {t["slug"]: t.get("tags") or [] for t in json.loads((ROOT / MOCK).read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return {}


D = load((_mt(EV / "evidence.json"), _mt(OUT / "compat_full.json"),
          _mt(OUT / "report-mock" / "report.json"), _mt(OUT / "report-catalog" / "report.json")))
EVD, FULL = D["ev"], D["full"]

if not EVD or not FULL:
    st.title("🩺 Tool-Schema Doctor")
    st.error("Evidence not generated yet. From the project root run:")
    st.code("python tool-schema-doctor/make_evidence.py", language="bash")
    st.stop()

PROV = EVD["provenance"]
SHA = PROV["upstream_commit"]
REPO = PROV["upstream_repo"]
CAUSES = EVD["causes"]
CMDS = EVD["commands"]
UPSTREAM = read_json(EV / "upstream_status.json") or {}
VFIX = UPSTREAM.get("findings", {}).get("vertex", {})
VERTEX_FIXED = VFIX.get("status") == "fixed_upstream"


def gh(path: str, lines: str = "") -> str:
    return f"{REPO}/blob/{SHA}/{path}" + (f"#{lines}" if lines else "")


# test outcomes straight from the JUnit XML pytest wrote
@st.cache_data(show_spinner=False)
def test_outcomes(_mtime: float) -> dict:
    out = {}
    try:
        root = ET.parse(EV / "test-results.xml").getroot()
        for tc in root.iter("testcase"):
            tags = {c.tag for c in tc}
            status = ("failed" if tags & {"failure", "error"} else "skipped" if "skipped" in tags else "passed")
            out[tc.get("name")] = status
    except (OSError, ET.ParseError):
        pass
    return out


TESTS = test_outcomes(_mt(EV / "test-results.xml"))
T = EVD["tests"]


def tests_line(names: list[str]) -> str:
    icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}
    parts = []
    for n in names:
        hits = {k: v for k, v in TESTS.items() if k == n or k.startswith(n + "[")}
        status = ("passed" if hits and all(v == "passed" for v in hits.values())
                  else "failed" if any(v == "failed" for v in hits.values())
                  else "skipped" if hits else "missing")
        parts.append(f"{icon.get(status, '❔')} `{n}`")
    return " · ".join(parts)


def cli_block(cid: str, max_lines: int = 40):
    """Show the exact command and its verbatim stdout (trimmed, full file downloadable)."""
    c = CMDS.get(cid)
    if not c:
        return
    st.markdown("**Reproduce it** (from the project root):")
    st.code(c["command"], language="bash")
    p = HERE / c.get("output_file", "")
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    lines = text.splitlines()
    shown = "\n".join(lines[:max_lines]) + (f"\n… {len(lines) - max_lines} more lines" if len(lines) > max_lines else "")
    st.markdown(f"**CLI output, verbatim** · exit code `{c['exit_code']}` · {c['seconds']}s")
    st.code(shown or "(no output)", language="json")
    if text:
        st.download_button("Download full output", text, file_name=f"{cid}.txt", key=f"dl-{cid}")


def link(label: str, url: str) -> str:
    return f"[{label}]({url})"


# ------------------------------------------------------------------ derived numbers
results = FULL["results"]
summary = FULL["summary"]
n_tools = FULL["tools"]
adapter_errors = CAUSES["adapter_errors"]
vertex_err = [r for r in adapter_errors if r["provider"] == "google_vertex"]
gemini_err = [r for r in adapter_errors if r["provider"] == "gemini"]
gem_drop = CAUSES["dropped_by_provider"]["gemini"]
enum_dropped, enum_total = gem_drop.get("enum", 0), CAUSES["tools_with_enum"]
strict_n = CAUSES["strict_unsupported_tools"]

mock_findings = (D["mock_rep"] or {}).get("lint", [])
cat_findings = (D["cat_rep"] or {}).get("lint", [])
missing_hint = [f for f in mock_findings if f["rule_id"] == "missing-action-hint"]
destructive = [f for f in mock_findings if f["rule_id"] == "destructive-verb-without-destructive-hint"]
repeats = [f for f in cat_findings if f["rule_id"] == "description-repeats-name"]


def dup_groups(findings):
    groups = {}
    for f in findings:
        if f["rule_id"] != "duplicate-display-name-in-toolkit":
            continue
        ev = f.get("evidence") or ""
        try:
            sib = ast.literal_eval(ev.split("siblings=", 1)[1])
            name = ev.split("name=", 1)[1].split("; siblings=", 1)[0].strip("'\"")
        except (IndexError, ValueError, SyntaxError):
            continue
        key = tuple(sorted([f["slug"], *sib]))
        groups[key] = (f.get("toolkit"), name)
    return groups


groups = dup_groups(cat_findings)

# ================================================================== HEADER
tests_ok = T.get("passed") == T.get("tests") and T.get("tests")
st.markdown(f"""
<div class="hero">
  <div class="eyebrow">Composio tool-schema QA</div>
  <h1>🩺 Tool-Schema Doctor</h1>
  <p>Runs every Composio tool schema through the <b>real</b> provider adapters and lints the tool metadata,
  to find what breaks, or silently loses information, <b>before an agent hits it</b>.</p>
  <div class="chips">
    <a class="chip" href="{REPO}/commit/{SHA}" target="_blank">Composio @ {SHA[:7]}</a>
    <span class="chip">{n_tools} tools × 6 adapters</span>
    <span class="chip">Offline · nothing executed</span>
    <span class="chip {'ok' if tests_ok else ''}">{'✓' if tests_ok else '!'} {T.get('passed', '?')}/{T.get('tests', '?')} tests passing</span>
    <span class="chip">Evidence {EVD['generated_at'][:16].replace('T', ' ')} UTC</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ================================================================== VERDICT
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tools that fail to convert", len(adapter_errors),
          help="The adapter raised an error: the tool cannot be sent to that provider.")
c1.caption(f"Vertex {len(vertex_err)}" + (f" (fixed upstream, #{VFIX['pr']})" if VERTEX_FIXED else "")
           + f" · Gemini {len(gemini_err)} · OpenAI/Anthropic/ADK 0")
c2.metric("No OpenAI strict mode", strict_n,
          help="Sent without strict mode instead (the SDK logs a warning).")
c2.caption(f"of {n_tools} tools; they still work, just unguarded")
c3.metric("Gemini drops enums", f"{enum_dropped} / {enum_total}",
          help="Tools whose `enum` is dropped from the Gemini declaration.")
c3.caption("tools that define an enum")
c4.metric("Missing action hints", f"{len(missing_hint)} / {n_tools}",
          help="None of readOnly/create/update/destructive — approval rules can't see intent.")
c4.caption(f"{len(missing_hint) / max(n_tools, 1):.1%} of the test fixture")

st.info(
    "**Scope:** schema checks use the 930-tool fixture shipped in Composio's CLI tests (GitHub-heavy). "
    "Name/description checks use the 84,004-tool docs catalog. The numbers describe these snapshots, "
    "not the live catalog.",
    icon="ℹ️",
)

# ================================================================== FIX LIST
st.header("What to fix, in priority order")
st.caption("Open **Evidence** on any item for the affected tools, raw errors, upstream code, "
           "the CLI command that reproduces it, and the tests that pin it.")

_card_no = iter(range(1, 100))


def card(sev: str, color: str, title: str, owner: str, impact: str, fix: str, body):
    with st.container(border=True):
        st.markdown(f"#### {next(_card_no)}. {title}")
        st.markdown(f":{color}-background[**{sev}**] &nbsp;<span class='owner'>Owner: {owner}</span>",
                    unsafe_allow_html=True)
        st.markdown(f"**Why it matters:** {impact}")
        st.markdown(f"**Fix:** {fix}")
        with st.expander("Evidence"):
            body()


# ---- 1. Vertex
def ev_vertex():
    if VERTEX_FIXED:
        st.success(
            f"**Fixed upstream:** {link('#' + str(VFIX['pr']), VFIX['pr_url'])} was merged "
            f"{VFIX['merged_at'][:10]}, replacing the top-level-only stripping with a recursive allowlist. "
            f"Ships in {VFIX['release']}. Checked {UPSTREAM.get('checked_at')} via the GitHub API; "
            "**not yet re-run locally against the fix.** The evidence below is from the pinned commit.",
            icon="✅")
    st.markdown(
        "**Cause, in the code:** the adapter removes `examples` only from top-level properties "
        f"({link('composio_google/provider.py L43–60', gh('python/providers/google/composio_google/provider.py', 'L43-L60'))}). "
        "Nested `examples` and `file_uploadable` reach Vertex's schema parser, which rejects unknown fields."
    )
    st.dataframe(pd.DataFrame([{"tool": r["slug"], "offending schema path": r["schema_path"],
                                "error": f"{r['error_type']}: {(r['message'] or '')[:110]}"} for r in vertex_err]),
                 hide_index=True, width="stretch")
    cli_block("vertex", 30)
    st.markdown("**Pinned by tests:** " + tests_line(["test_vertex_nested_examples_errors",
                                                       "test_vertex_file_uploadable_errors",
                                                       "test_vertex_top_level_examples_is_stripped_not_error"]))


def show_vertex_card():
    if VERTEX_FIXED:
        card("FIXED UPSTREAM", "green",
             f"The Vertex AI adapter rejected {len(vertex_err)} tools, now fixed upstream in #{VFIX['pr']}",
             "`composio_google` (SDK adapter)",
             f"On the pinned commit these {len(vertex_err)} tools can't be sent to Vertex AI: building the "
             "`FunctionDeclaration` raises `ParseError`. Composio has since merged a fix.",
             f"Nothing left to change in code. Upgrade to {VFIX['release'].split(' (')[0]} when it ships and re-run "
             "this check; expect 0 Vertex failures.",
             ev_vertex)
    else:
        card("HIGH", "red", f"The Vertex AI adapter rejects {len(vertex_err)} tools",
             "`composio_google` (SDK adapter)",
             f"These {len(vertex_err)} tools can't be sent to Vertex AI at all: building the `FunctionDeclaration` raises `ParseError`.",
             "Strip `examples` and `file_uploadable` at **every depth** (nested objects and array `items`), not just top-level properties.",
             ev_vertex)


if not VERTEX_FIXED:
    show_vertex_card()


# ---- 2. Gemini
def ev_gemini():
    st.markdown(
        "**Cause:** Gemini declarations are built from a Python function signature "
        "(`FunctionDeclaration.from_callable`), so only types survive. Dropping `enum` is intentional and pinned upstream "
        f"in {link('test_gemini_provider.py AFC_CASES', gh('python/tests/test_gemini_provider.py', 'L545'))}."
    )
    st.markdown("**Keywords Gemini drops** (number of tools affected):")
    st.dataframe(pd.DataFrame([{"keyword": k, "tools": v} for k, v in gem_drop.items()]),
                 hide_index=True, width="content")
    if gemini_err:
        r = gemini_err[0]
        st.markdown(f"**Hard failure:** `{r['slug']}` — `{r['error_type']}: {(r['message'] or '')[:160]}`")
    st.caption(f"The CLI run below uses two real tools: the one Gemini rejects and `{EVD.get('gemini_enum_example')}`, whose enum it drops.")
    cli_block("gemini", 45)
    st.markdown("**Pinned by tests:** " + tests_line(["test_gemini_drops_enum", "test_gemini_real_nested_object_failure"]))


card("MEDIUM", "orange", f"Gemini hides allowed values on {enum_dropped} of {enum_total} tools, and rejects {len(gemini_err)}",
     "`composio_gemini` (SDK adapter)",
     "The model never sees the allowed values (`enum`), defaults or examples, so it can send arguments the API then rejects. "
     f"`{gemini_err[0]['slug'] if gemini_err else '—'}` doesn't convert at all.",
     "The drop is by design, so treat it as a decision: e.g. list the allowed values in the parameter description. "
     "Separately, fix the nested `permission` object that `from_callable` can't parse.",
     ev_gemini)


# ---- 3. OpenAI strict
def ev_strict():
    st.markdown(
        "**Cause, in the SDK's own words** (`to_strict_json_schema`). The provider then falls back to non-strict and only logs a warning: "
        f"{link('_openai_responses.py L84–99', gh('python/composio/core/provider/_openai_responses.py', 'L84-L99'))}."
    )
    ex = CAUSES["strict_example"]
    st.dataframe(pd.DataFrame([{"unsupported": k, "tools": v, "what it means": ex.get(k, {}).get("detail", ""),
                                "example": f"{ex.get(k, {}).get('slug', '')} → {ex.get(k, {}).get('path', '')}"}
                               for k, v in CAUSES["strict_by_keyword"].items()]),
                 hide_index=True, width="stretch")
    cli_block("strict", 30)
    st.markdown("**Pinned by tests:** " + tests_line(["test_openai_strict_reports_sdk_reason_for_free_form_object"]))


kw = CAUSES["strict_by_keyword"]
card("MEDIUM", "orange", f"OpenAI strict mode can't be used for {strict_n} tools",
     "Tool schema authors (Composio tool definitions)",
     "With `OpenAIResponsesProvider(strict=True)` these tools are quietly sent **without** strict mode, "
     "so their arguments get no structured-output guarantee.",
     f"Declare the properties of free-form objects ({kw.get('properties', 0)} tools, e.g. array `items` typed as bare `object`). "
     f"Keep arbitrary-key maps ({kw.get('additionalProperties', 0)} tools) only where keys are truly dynamic.",
     ev_strict)


# ---- 4. Action hints
def ev_hints():
    st.markdown(
        f"**Why the tags matter, in the code:** Composio's Tool Router filters and gates tools by these tags "
        f"({link('ToolRouterTag', gh('python/composio/core/models/tool_router.py', 'L120-L127'))}). Its "
        f"{link('require_approval', gh('python/composio/core/models/tool_router.py', 'L247-L259'))} docstring reads: "
        "*\"Tools with any of these tags need the user's approval before they run.\"*"
    )
    st.markdown(f"**Destructive-sounding tools without `destructiveHint`** ({len(destructive)}; name-based heuristic, review each):")
    saved = CAUSES.get("destructive_hint_tags") or {}
    tags = saved or mock_tags()          # evidence first; upstream checkout only as a fallback
    hint_set = {"readOnlyHint", "createHint", "updateHint", "destructiveHint", "idempotentHint", "openWorldHint"}
    st.dataframe(pd.DataFrame([{"tool": f["slug"],
                                "hint tags it has today": ", ".join(t for t in tags.get(f["slug"], []) if t in hint_set) or "none"}
                               for f in destructive]),
                 hide_index=True, width="stretch")
    cli_block("hints", 30)
    st.markdown("**Pinned by tests:** " + tests_line(["test_missing_action_hint_positive_and_negative",
                                                       "test_destructive_verb_without_hint"]))


card("MEDIUM", "orange", f"{len(missing_hint)} of {n_tools} tools carry no action hint, so approval rules can't see their intent",
     "Tool metadata",
     f"A tool tagged with none of readOnly/create/update/destructive can't be targeted by `require_approval` or tag filters. "
     f"{len(destructive)} of them have destructive-sounding names (delete, remove, revoke…).",
     "Add the hint that matches each tool's effect. Start with the destructive-sounding ones.",
     ev_hints)


# ---- 5. Look-alikes
def ev_names():
    samples = sorted(groups.items(),
                     key=lambda kv: (not (kv[1][0] or "").lower().startswith(("slack", "github")), kv[1][0] or ""))[:6]
    st.markdown(f"**Same display name, same toolkit** ({len(groups)} groups in the catalog). Examples:")
    st.dataframe(pd.DataFrame([{"toolkit": tk, "display name": nm, "tools": " · ".join(slugs)}
                               for slugs, (tk, nm) in samples]), hide_index=True, width="stretch")
    st.markdown(f"**Descriptions that only repeat the name:** {len(repeats)}, e.g. "
                + ", ".join(f"`{f['slug']}`" for f in repeats[:3]))
    models = [(m, r["metrics"]) for m, r in D["evals"].items() if r]
    if models:
        st.markdown("**Does it confuse a model?** Our selection eval (27 hand-curated look-alike tasks, selection only):")
        st.dataframe(pd.DataFrame([{"model": m, "correct": f"{x['correct']}/{x['total']}",
                                    "missed": ", ".join(r["id"] for r in D["evals"][m]["results"] if not r["correct"]) or "—"}
                                   for m, x in models]), hide_index=True, width="content")
        st.caption("Exploratory: small curated set, model- and prompt-dependent. The one miss (t27) is a debatable case where both tools could set assignees.")
    cli_block("names", 25)
    st.markdown("**Pinned by tests:** " + tests_line(["test_duplicate_display_name_in_toolkit",
                                                       "test_description_repeats_name"]))


card("LOW", "blue", f"{len(groups)} groups of look-alike tools, and {len(repeats)} descriptions that just repeat the name",
     "Tool catalog",
     "Agents must choose between near-identical tools, usually a deprecated alias and its replacement. "
     "Capable models coped in our eval; a small model missed the hardest case.",
     "Hide or clearly mark deprecated aliases. Write descriptions that say what the tool does and when to use it.",
     ev_names)

if VERTEX_FIXED:
    show_vertex_card()

# ================================================================== DETAILS
st.header("Go deeper")
tab_tool, tab_all, tab_trust = st.tabs(["Check a tool", "All results", "How we know"])

with tab_tool:
    st.markdown("Pick any of the 930 tools to see what each adapter does with it. Results come from the saved full CLI run.")
    slugs = sorted({r["slug"] for r in results})
    default = slugs.index("GOOGLEDRIVE_UPLOAD_FILE") if "GOOGLEDRIVE_UPLOAD_FILE" in slugs else 0
    slug = st.selectbox("Tool", slugs, index=default)
    icon = {"ok": "✅ ok", "transformed": "⚠️ transformed", "error": "❌ error", "unavailable": "⏭️ unavailable"}
    rows = []
    for r in (x for x in results if x["slug"] == slug):
        if r["status"] == "error":
            what = f"{r['error_type']} at {r.get('schema_path') or '?'}: {(r.get('message') or '')[:120]}"
        elif r.get("dropped_keywords"):
            what = "dropped: " + ", ".join(r["dropped_keywords"])
        else:
            what = "unchanged"
        rows.append({"provider": r["provider"], "outcome": icon.get(r["status"], r["status"]), "what happened": what})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("✅ converts unchanged · ⚠️ converts but drops schema keywords the model would otherwise see · ❌ the adapter raises")
    for r in (x for x in results if x["slug"] == slug and x["status"] == "error"):
        st.markdown(f"**Full `{r['provider']}` error**, exactly as the adapter raised it:")
        st.code(f"{r['error_type']}: {r.get('message') or ''}", language="text", wrap_lines=True)

    st.markdown("**Don't trust the saved run? Re-run this tool live** through the real adapters with the CLI:")
    live_cmd = f"tool-schema-doctor compatibility --input tool-schema-doctor/out/evidence/live/{slug}.json --verbose"
    st.code(live_cmd, language="bash")
    live_ok = (ROOT / MOCK).is_file() and importlib.util.find_spec("tool_schema_doctor") is not None
    if not live_ok:
        st.caption("Live re-run needs the Composio checkout and the provider SDKs, so it's available when you run "
                   "this dashboard locally (see the README). The saved results above come from the same CLI.")
    elif st.button("Run it now", key="live"):
        mock = {t["slug"]: t for t in json.loads((ROOT / MOCK).read_text(encoding="utf-8"))}
        live = EV / "live" / f"{slug}.json"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_text(json.dumps([mock[slug]]), encoding="utf-8")
        with st.spinner("Running the CLI (the first run loads six provider SDKs, about a minute)…"):
            proc = subprocess.run(
                [sys.executable, "-m", "tool_schema_doctor.cli", "compatibility",
                 "--input", str(live.relative_to(ROOT)), "--verbose"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=900)
        st.markdown(f"Exit code `{proc.returncode}`")
        st.code(proc.stdout or proc.stderr, language="json")

with tab_all:
    st.markdown(f"**Every adapter on all {n_tools} tools** (`{CMDS['full']['command']}`)")
    st.dataframe(pd.DataFrame([{"provider": p, **{k: v.get(k, 0) for k in ("ok", "transformed", "error")}}
                               for p, v in summary.items()]).set_index("provider"), width="stretch")
    st.markdown("**Every adapter error**")
    st.dataframe(pd.DataFrame(adapter_errors)[["slug", "provider", "error_type", "schema_path", "message"]],
                 hide_index=True, width="stretch")
    st.markdown("**Metadata lint, by rule**")
    a, b = st.columns(2)
    for col, label, rep in ((a, f"Test fixture · {n_tools} tools", D["mock_rep"]),
                            (b, "Docs catalog · 84,004 tools", D["cat_rep"])):
        with col:
            st.markdown(label)
            by_rule = (rep or {}).get("meta", {}).get("lint_summary", {}).get("by_rule", {})
            st.dataframe(pd.Series(by_rule, name="findings").sort_values(ascending=False),
                         width="stretch")
    st.caption("Hint rules are skipped on the catalog (it has no tags) rather than counted as findings.")

with tab_trust:
    st.markdown("**Where the numbers come from**")
    fx = PROV["fixtures"]
    st.dataframe(pd.DataFrame([
        {"item": "Composio source", "value": f"{SHA} ({PROV.get('upstream_commit_date', '')[:10]})",
         "check": f"{REPO}/commit/{SHA}"},
        {"item": f"Upstream re-checked {UPSTREAM.get('checked_at', '—')}",
         "value": (f"next is {UPSTREAM.get('next_ahead_by')} commits ahead; in scope only the Vertex adapter changed"
                   if UPSTREAM else "not checked"),
         "check": f"{REPO}/compare/{SHA}...next"},
        {"item": "Local checkout modified?", "value": "no" if PROV.get("upstream_dirty_files") == 0 else f"{PROV['upstream_dirty_files']} files",
         "check": None},
        {"item": "Schema fixture (930 tools)", "value": f"git blob {fx.get(MOCK, '')[:12]}", "check": gh(MOCK.split('/', 1)[1])},
        {"item": "Name catalog (84,004 tools)", "value": f"git blob {fx.get(CATALOG, '')[:12]}", "check": gh(CATALOG.split('/', 1)[1])},
    ]), hide_index=True, width="stretch",
        column_config={"check": st.column_config.LinkColumn("verify")})

    st.markdown("**How the checks run**")
    st.markdown(
        "- **Real adapters, not copies:** each check imports the installed provider package (e.g. `composio_google.GoogleProvider`) "
        "and calls its own `wrap_tool`. See `tool-schema-doctor/src/tool_schema_doctor/providers.py`.\n"
        "- **Offline:** network sockets are blocked during conversion, and any attempt to execute a tool raises.\n"
        "- **One bad tool never stops a run.** A missing provider SDK is reported as *unavailable*, not as a failure."
    )
    st.markdown("**Adapter versions used**")
    st.dataframe(pd.DataFrame([{"package": k, "version": v or "not installed"} for k, v in PROV["versions"].items()]),
                 hide_index=True, width="content")

    st.markdown(f"**Tests:** {T.get('passed')}/{T.get('tests')} passed, {T.get('failed', T.get('failures', 0))} failed, "
                f"{T.get('skipped', 0)} skipped ({T.get('seconds')}s), from `{T.get('junit_file')}`")
    st.dataframe(pd.DataFrame([{"test": k, "result": v} for k, v in sorted(TESTS.items())]),
                 hide_index=True, width="stretch", height=240)

    st.markdown("**Reproduce everything**")
    st.code('pip install -e "tool-schema-doctor[all,dashboard]"\n'
            "python tool-schema-doctor/make_evidence.py   # every CLI command on this page + the tests + provenance\n"
            "python -m streamlit run tool-schema-doctor/streamlit_app.py",
            language="bash")
    st.markdown("**Limits:** the 930-tool fixture is a test mock and is GitHub-heavy; results reflect the adapter versions "
                "above; the selection eval is a small, curated, model-dependent check.")

st.divider()
st.markdown(
    f"<div class='foot'>Tool-Schema Doctor · every number on this page is read from saved CLI output in "
    f"<code>tool-schema-doctor/out/</code> · tool fixtures and adapter code from "
    f"<a href='{REPO}/tree/{SHA}' target='_blank'>ComposioHQ/composio</a> (MIT)</div>",
    unsafe_allow_html=True)
