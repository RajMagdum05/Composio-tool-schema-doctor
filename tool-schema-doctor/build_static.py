"""Build the static site (site/index.html) from the saved evidence.

The Streamlit dashboard needs a running Python server. This builds the same page as plain
HTML, CSS and a little JavaScript so it can be hosted anywhere (Netlify, Vercel, GitHub Pages).
It reads exactly the files the dashboard reads (tool-schema-doctor/out/) and shares its look
through tool-schema-doctor/theme.css.

Usage, from the repository root:
    python tool-schema-doctor/build_static.py
Output: site/index.html and site/evidence/cli/*.txt (the verbatim CLI output the page links to).
"""

from __future__ import annotations

import ast
import html
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
EV = OUT / "evidence"
SITE = Path(os.environ.get("TSD_SITE_DIR") or ROOT / "site")     # override is for tests
MOCK = "composio-upstream/ts/packages/cli/test/__mocks__/tools.json"
CATALOG = "composio-upstream/docs/public/data/toolkits.json"

e = html.escape


def rj(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


EVD, FULL = rj(EV / "evidence.json"), rj(OUT / "compat_full.json")
MOCK_REP, CAT_REP = rj(OUT / "report-mock" / "report.json"), rj(OUT / "report-catalog" / "report.json")
UP = rj(EV / "upstream_status.json") or {}
EVALS = {"gpt-oss-20b": rj(OUT / "eval_report.json"), "qwen3.8-27b": rj(OUT / "eval_report_qwen.json"),
         "allam-2-7b": rj(OUT / "eval_report_allam.json")}
if not (EVD and FULL and MOCK_REP and CAT_REP):
    raise SystemExit("Evidence is missing. Run: python tool-schema-doctor/make_evidence.py")

PROV, CAUSES, CMDS, T = EVD["provenance"], EVD["causes"], EVD["commands"], EVD["tests"]
SHA, REPO = PROV["upstream_commit"], PROV["upstream_repo"]
VFIX = UP.get("findings", {}).get("vertex", {})
VERTEX_FIXED = VFIX.get("status") == "fixed_upstream"

# ------------------------------------------------------------------ derived numbers (same as the dashboard)
results, summary, n_tools = FULL["results"], FULL["summary"], FULL["tools"]
adapter_errors = CAUSES["adapter_errors"]
vertex_err = [r for r in adapter_errors if r["provider"] == "google_vertex"]
gemini_err = [r for r in adapter_errors if r["provider"] == "gemini"]
gem_drop = CAUSES["dropped_by_provider"]["gemini"]
enum_dropped, enum_total = gem_drop.get("enum", 0), CAUSES["tools_with_enum"]
strict_n = CAUSES["strict_unsupported_tools"]
mock_findings, cat_findings = MOCK_REP.get("lint", []), CAT_REP.get("lint", [])
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
        groups[tuple(sorted([f["slug"], *sib]))] = (f.get("toolkit"), name)
    return groups


groups = dup_groups(cat_findings)


def test_outcomes() -> dict:
    out = {}
    try:
        for tc in ET.parse(EV / "test-results.xml").getroot().iter("testcase"):
            tags = {c.tag for c in tc}
            out[tc.get("name")] = ("failed" if tags & {"failure", "error"} else "skipped" if "skipped" in tags else "passed")
    except (OSError, ET.ParseError):
        pass
    return out


TESTS = test_outcomes()


# ------------------------------------------------------------------ small HTML helpers
def md(text: str) -> str:
    """Tiny markdown subset used in the copy: `code`, **bold**, *italic*, [text](url)."""
    t = e(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return t


def gh(path: str, lines: str = "") -> str:
    return f"{REPO}/blob/{SHA}/{path}" + (f"#{lines}" if lines else "")


def table(headers: list[str], rows: list[list[str]], raw: bool = False) -> str:
    th = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c if raw else e(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class='scroll'><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def lbl(text: str) -> str:
    return f"<div class='lbl'>{text}</div>"


def tests_line(names: list[str]) -> str:
    glyph = {"passed": "✓", "failed": "✗", "skipped": "–", "missing": "?"}
    parts = []
    for n in names:
        hits = {k: v for k, v in TESTS.items() if k == n or k.startswith(n + "[")}
        st = ("passed" if hits and all(v == "passed" for v in hits.values())
              else "failed" if any(v == "failed" for v in hits.values()) else "skipped" if hits else "missing")
        parts.append(f"{glyph[st]} <code>{e(n)}</code>")
    return lbl("Pinned by tests") + "<p>" + " &nbsp;·&nbsp; ".join(parts) + "</p>"


def cli_block(cid: str, max_lines: int = 40) -> str:
    c = CMDS.get(cid)
    if not c:
        return ""
    src = HERE / c.get("output_file", "")
    text = src.read_text(encoding="utf-8") if src.is_file() else ""
    lines = text.splitlines()
    shown = "\n".join(lines[:max_lines]) + (f"\n… {len(lines) - max_lines} more lines" if len(lines) > max_lines else "")
    link = f" &nbsp;·&nbsp; <a href='evidence/cli/{cid}.txt'>full output</a>" if text else ""
    return (lbl("Reproduce it, from the repository root") + f"<pre>{e(c['command'])}</pre>"
            + lbl(f"Its output, verbatim &nbsp;·&nbsp; exit code {c['exit_code']} &nbsp;·&nbsp; {c['seconds']}s{link}")
            + f"<pre>{e(shown or '(no output)')}</pre>")


_SEV = {"high": ("d-high", "High"), "medium": ("d-med", "Medium"), "low": ("d-low", "Low"), "fixed": ("d-fixed", "Fixed upstream")}
TITLES: list[str] = []


def card(sev: str, title: str, owner: str, impact: str, fix: str, evidence: str) -> str:
    n = len(TITLES) + 1
    TITLES.append(title)
    dot, name = _SEV[sev]
    return (f"<article class='card'><div class='kicker'><span class='dot {dot}'></span>{name} &nbsp;·&nbsp; {e(owner)}</div>"
            f"<h3>{n}. {e(title)}</h3>{lbl('Why it matters')}<p>{md(impact)}</p>{lbl('Fix')}<p>{md(fix)}</p>"
            f"<details><summary>Evidence</summary>{evidence}</details></article>")


# ------------------------------------------------------------------ the five findings
def ev_vertex() -> str:
    note = ""
    if VERTEX_FIXED:
        note = (f"<div class='note'>Fixed upstream in <a href='{e(VFIX['pr_url'])}' target='_blank' rel='noopener'>#{VFIX['pr']}</a>, "
                f"merged {e(VFIX['merged_at'][:10])}, replacing the top-level-only stripping with a recursive allowlist. "
                f"It ships in {e(VFIX['release'])}. The results below reflect the analyzed Composio commit and adapter versions listed above.</div>")
    cause = md("**Cause, in the code.** The adapter removes `examples` only from top-level properties "
               f"([composio_google/provider.py, lines 43 to 60]({gh('python/providers/google/composio_google/provider.py', 'L43-L60')})). "
               "Nested `examples` and `file_uploadable` reach Vertex's schema parser, which rejects unknown fields.")
    rows = [[r["slug"], r["schema_path"], f"{r['error_type']}: {(r['message'] or '')[:110]}"] for r in vertex_err]
    return (note + f"<p>{cause}</p>" + table(["tool", "offending schema path", "error"], rows) + cli_block("vertex", 30)
            + tests_line(["test_vertex_nested_examples_errors", "test_vertex_file_uploadable_errors",
                          "test_vertex_top_level_examples_is_stripped_not_error"]))


def vertex_card() -> str:
    if VERTEX_FIXED:
        if vertex_err:
            title = f"Vertex still rejects {len(vertex_err)} tools with the analyzed adapter version"
            impact = (f"The current adapter package still raises while building the `FunctionDeclaration` for "
                      f"{len(vertex_err)} tools, although Composio merged the fix in #{VFIX['pr']}.")
        else:
            title = f"Vertex conversion passes for all {n_tools} tools in this run"
            impact = f"The fix from Composio PR #{VFIX['pr']} is reflected in the current adapter results."
        return card("fixed", title, "composio_google (SDK adapter)", impact,
                    "Keep the adapter package current and rerun this check when Composio schemas change.", ev_vertex())
    return card("high", f"The Vertex AI adapter rejects {len(vertex_err)} tools", "composio_google (SDK adapter)",
                f"These {len(vertex_err)} tools can't be sent to Vertex AI at all: building the `FunctionDeclaration` raises `ParseError`.",
                "Strip `examples` and `file_uploadable` at every depth (nested objects and array `items`), not just top-level properties.",
                ev_vertex())


def ev_gemini() -> str:
    cause = md("**Cause.** Gemini declarations are built from a Python function signature "
               "(`FunctionDeclaration.from_callable`), so only types survive. Dropping `enum` is intentional and pinned upstream "
               f"in [test_gemini_provider.py, AFC_CASES]({gh('python/tests/test_gemini_provider.py', 'L545')}).")
    hard = ""
    if gemini_err:
        r = gemini_err[0]
        hard = f"<p>{md('**Hard failure.** ' + '`' + r['slug'] + '`: `' + r['error_type'] + ': ' + (r['message'] or '')[:160] + '`')}</p>"
    return (f"<p>{cause}</p>" + lbl("Keywords Gemini drops, by number of tools")
            + table(["keyword", "tools"], [[k, v] for k, v in gem_drop.items()]) + hard
            + f"<p class='cap'>The run below uses two real tools: the one Gemini rejects, and <code>{e(str(EVD.get('gemini_enum_example')))}</code>, whose enum it drops.</p>"
            + cli_block("gemini", 45) + tests_line(["test_gemini_drops_enum", "test_gemini_real_nested_object_failure"]))


def ev_strict() -> str:
    cause = md("**Cause, in the SDK's own words** (`to_strict_json_schema`). The provider then falls back to non-strict and only logs a warning: "
               f"[_openai_responses.py, lines 84 to 99]({gh('python/composio/core/provider/_openai_responses.py', 'L84-L99')}).")
    ex = CAUSES["strict_example"]
    rows = [[k, v, ex.get(k, {}).get("detail", ""), f"{ex.get(k, {}).get('slug', '')} → {ex.get(k, {}).get('path', '')}"]
            for k, v in CAUSES["strict_by_keyword"].items()]
    return (f"<p>{cause}</p>" + table(["unsupported", "tools", "what it means", "example"], rows) + cli_block("strict", 30)
            + tests_line(["test_openai_strict_reports_sdk_reason_for_free_form_object"]))


def ev_hints() -> str:
    why = md("**Why the tags matter, in the code.** Composio's Tool Router filters and gates tools by these tags "
             f"([ToolRouterTag]({gh('python/composio/core/models/tool_router.py', 'L120-L127')})). Its "
             f"[require_approval]({gh('python/composio/core/models/tool_router.py', 'L247-L259')}) docstring reads: "
             "*\"Tools with any of these tags need the user's approval before they run.\"*")
    tags = CAUSES.get("destructive_hint_tags") or {}
    hint_set = {"readOnlyHint", "createHint", "updateHint", "destructiveHint", "idempotentHint", "openWorldHint"}
    rows = [[f["slug"], ", ".join(t for t in tags.get(f["slug"], []) if t in hint_set) or "none"] for f in destructive]
    return (f"<p>{why}</p>" + lbl(f"Destructive-sounding tools without destructiveHint ({len(destructive)}, a name-based heuristic: review each)")
            + table(["tool", "hint tags it has today"], rows) + cli_block("hints", 30)
            + tests_line(["test_missing_action_hint_positive_and_negative", "test_destructive_verb_without_hint"]))


def ev_names() -> str:
    samples = sorted(groups.items(), key=lambda kv: (not (kv[1][0] or "").lower().startswith(("slack", "github")), kv[1][0] or ""))[:6]
    out = lbl(f"Same display name, same toolkit ({len(groups)} groups in the catalog). Examples")
    out += table(["toolkit", "display name", "tools"], [[tk, nm, " · ".join(slugs)] for slugs, (tk, nm) in samples])
    out += "<p>" + md(f"**Descriptions that only repeat the name:** {len(repeats)}, for example "
                      + ", ".join(f"`{f['slug']}`" for f in repeats[:3]) + ".") + "</p>"
    models = [(m, r) for m, r in EVALS.items() if r]
    if models:
        out += lbl("Does it confuse a model? Selection eval, 27 hand-curated look-alike tasks, selection only")
        out += table(["model", "correct", "missed"], [[m, f"{r['metrics']['correct']}/{r['metrics']['total']}",
                     ", ".join(x["id"] for x in r["results"] if not x["correct"]) or "none"] for m, r in models])
        out += ("<p class='cap'>Exploratory: a small curated set, and results depend on the model and prompt. The one miss (t27) is "
                "a debatable case where both tools could set assignees.</p>")
    return out + cli_block("names", 25) + tests_line(["test_duplicate_display_name_in_toolkit", "test_description_repeats_name"])


kw = CAUSES["strict_by_keyword"]
CARDS = []
if not VERTEX_FIXED:
    CARDS.append(vertex_card())
CARDS.append(card("medium", f"Gemini hides allowed values on {enum_dropped} of {enum_total} tools, and rejects {len(gemini_err)}",
                  "composio_gemini (SDK adapter)",
                  "The model never sees the allowed values (`enum`), defaults or examples, so it can send arguments the API then rejects. "
                  f"`{gemini_err[0]['slug'] if gemini_err else 'none'}` doesn't convert at all.",
                  "The drop is by design, so treat it as a decision: for example, list the allowed values in the parameter description. "
                  "Separately, fix the nested `permission` object that `from_callable` can't parse.", ev_gemini()))
CARDS.append(card("medium", f"OpenAI strict mode can't be used for {strict_n} tools", "Tool schema authors (Composio tool definitions)",
                  "With `OpenAIResponsesProvider(strict=True)` these tools are quietly sent without strict mode, "
                  "so their arguments get no structured-output guarantee.",
                  f"Declare the properties of free-form objects ({kw.get('properties', 0)} tools, for example array `items` typed as bare `object`). "
                  f"Keep arbitrary-key maps ({kw.get('additionalProperties', 0)} tools) only where the keys are truly dynamic.", ev_strict()))
CARDS.append(card("medium", f"{len(missing_hint)} of {n_tools} tools carry no action hint, so approval rules can't see their intent",
                  "Tool metadata",
                  "A tool tagged with none of readOnly, create, update or destructive can't be targeted by `require_approval` or tag filters. "
                  f"{len(destructive)} of them have destructive-sounding names (delete, remove, revoke).",
                  "Add the hint that matches each tool's effect. Start with the destructive-sounding ones.", ev_hints()))
CARDS.append(card("low", f"{len(groups)} groups of look-alike tools, and {len(repeats)} descriptions that just repeat the name", "Tool catalog",
                  "Agents must choose between near-identical tools, usually a deprecated alias and its replacement. "
                  "Capable models coped in our eval; a small model missed the hardest case.",
                  "Hide or clearly mark deprecated aliases. Write descriptions that say what the tool does and when to use it.", ev_names()))
if VERTEX_FIXED:
    CARDS.append(vertex_card())

# ------------------------------------------------------------------ hero
tests_ok = bool(T.get("tests")) and T.get("passed") == T.get("tests")
tests_txt = f"All {T.get('tests')} tests passing" if tests_ok else f"{T.get('passed', '?')} of {T.get('tests', '?')} tests passing"
vertex_note = f", fixed upstream in #{VFIX['pr']}" if VERTEX_FIXED else ""
STATS = [
    ("Tools that fail to convert", str(len(adapter_errors)),
     f"Vertex {len(vertex_err)}{vertex_note} · Gemini {len(gemini_err)} · OpenAI, Anthropic, ADK 0",
     "The adapter raised an error: the tool cannot be sent to that provider."),
    ("No OpenAI strict mode", str(strict_n), f"of {n_tools} tools. They still work, just without the guarantee.",
     "Sent without strict mode instead (the SDK logs a warning)."),
    ("Gemini drops enums", f"{enum_dropped} / {enum_total}", "of the tools that define an enum",
     "Tools whose enum is dropped from the Gemini declaration."),
    ("Missing action hints", f"{len(missing_hint)} / {n_tools}", f"{len(missing_hint) / max(n_tools, 1):.1%} of the test fixture",
     "None of readOnly, create, update or destructive: approval rules cannot see intent."),
]
stat_html = "".join(f"<div class='stat' title='{e(tip, quote=True)}'><div class='stat-label'>{lab}</div>"
                    f"<div class='stat-num'>{val}</div><div class='stat-cap'>{cap}</div></div>" for lab, val, cap, tip in STATS)
HERO = f"""
<div class="strip"><div class="inner"><span class="tag">Independent</span><span>An analysis of Composio's tool schemas. Not affiliated with or endorsed by Composio.</span></div></div>
<div class="dark"><div class="inner">
<div class="nav"><div class="brand">Tool-Schema Doctor</div>
<div class="navr"><a href="{REPO}/commit/{SHA}" target="_blank" rel="noopener">Composio @ {SHA[:7]}</a><span>{n_tools} tools · 6 adapters</span><span>{tests_txt}</span><span>Evidence {EVD['generated_at'][:10]}</span></div></div>
<div class="hero"><h1>Find what breaks <span class="hl">before an agent does</span></h1>
<p>Every Composio tool, run through the real provider adapters, and the tool metadata, checked. Each finding opens to the evidence behind it.</p>
<div class="btns"><a class="btn" href="#fixes">See what to fix</a><a class="btn ghost" href="#tool-check">Check a tool</a></div></div>
<div class="stats">{stat_html}</div>
<div class="scope">Schema checks use the 930-tool fixture shipped in Composio's CLI tests, which is GitHub-heavy. Name and description checks use the 84,004-tool docs catalog. These numbers describe those snapshots, not the live catalog.</div>
</div></div>
"""

# ------------------------------------------------------------------ "check a tool" data (compact, embedded)
OUTCOME = {"ok": "OK", "transformed": "Changed", "error": "Error", "unavailable": "Unavailable"}
by_tool: dict[str, list] = {}
for r in results:
    if r["status"] == "error":
        detail = f"{r['error_type']}: {r.get('message') or ''}"
    elif r.get("dropped_keywords"):
        detail = "dropped: " + ", ".join(r["dropped_keywords"])
    else:
        detail = "unchanged"
    by_tool.setdefault(r["slug"], []).append([r["provider"], OUTCOME.get(r["status"], r["status"]), detail,
                                              r.get("schema_path") or ""])
TOOLS_JSON = json.dumps(by_tool, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
DEFAULT_TOOL = "GOOGLEDRIVE_UPLOAD_FILE" if "GOOGLEDRIVE_UPLOAD_FILE" in by_tool else sorted(by_tool)[0]
TOOL_CHECKER = f"""
<section class="tool-check" id="tool-check"><div class="inner">
<div class="sec">Check a tool</div>
<p class="sub">Choose a tool to compare how all six provider adapters handle its schema. Results come from the saved full CLI run.</p>
<label class="tool-picker-label" for="q">Select a tool to inspect adapter behavior</label>
<select id="q" class="mono" aria-label="Select a tool to inspect adapter behavior">
{''.join(f'<option value="{e(s, quote=True)}"{" selected" if s == DEFAULT_TOOL else ""}>{e(s)}</option>' for s in sorted(by_tool))}
</select>
<div id="out"></div>
<p class="cap">OK: converts unchanged. Changed: converts, but drops schema keywords the model would otherwise see. Error: the adapter raises.</p>
<div class="h3">Don't trust the saved run? Re-run this tool live</div>
<p class="cap">Run it yourself from the repository root with the CLI (needs the Composio checkout and provider SDKs):</p>
<pre id="cmd"></pre>
</div></section>
"""

# ------------------------------------------------------------------ go deeper
fx = PROV["fixtures"]
prov_rows = [
    ["Composio source", f"{SHA} ({PROV.get('upstream_commit_date', '')[:10]})", f"<a href='{REPO}/commit/{SHA}' target='_blank' rel='noopener'>commit</a>"],
    ["Local checkout modified?", "no" if PROV.get("upstream_dirty_files") == 0 else f"{PROV['upstream_dirty_files']} files", ""],
    ["Schema fixture (930 tools)", f"git blob {fx.get(MOCK, '')[:12]}", f"<a href='{gh(MOCK.split('/', 1)[1])}' target='_blank' rel='noopener'>file</a>"],
    ["Name catalog (84,004 tools)", f"git blob {fx.get(CATALOG, '')[:12]}", f"<a href='{gh(CATALOG.split('/', 1)[1])}' target='_blank' rel='noopener'>file</a>"],
]
prov_rows = [[e(a), e(b), c] for a, b, c in prov_rows]


def by_rule(rep):
    return (rep or {}).get("meta", {}).get("lint_summary", {}).get("by_rule", {})


all_summary = table(["provider", "ok", "changed", "error"], [[p, v.get("ok", 0), v.get("transformed", 0), v.get("error", 0)] for p, v in summary.items()])
all_errors = table(["tool", "provider", "error", "schema path"], [[r["slug"], r["provider"], r["error_type"], r["schema_path"] or ""] for r in adapter_errors])
lint_tables = ("<div class='two'><div>" + lbl(f"Test fixture, {n_tools} tools")
               + table(["rule", "findings"], sorted(by_rule(MOCK_REP).items(), key=lambda kv: -kv[1]))
               + "</div><div>" + lbl("Docs catalog, 84,004 tools")
               + table(["rule", "findings"], sorted(by_rule(CAT_REP).items(), key=lambda kv: -kv[1])) + "</div></div>")
versions = table(["package", "version"], [[k, v or "not installed"] for k, v in PROV["versions"].items()])
test_rows = table(["test", "result"], [[k, v] for k, v in sorted(TESTS.items())])

DEEPER = f"""
<div class="tabs" role="tablist">
<button class="tab on" role="tab" data-t="all">All results</button><button class="tab" role="tab" data-t="how">How we know</button>
</div>
<section class="pane on" id="pane-all">
<div class='h3'>Every adapter on all {n_tools} tools</div><p class="cap">{e(CMDS['full']['command'])}</p>{all_summary}
<div class='h3'>Every adapter error</div><p class="cap">Plus {strict_n} OpenAI strict-mode fallbacks, listed in finding 2.</p>{all_errors}
<div class='h3'>Metadata lint, by rule</div>{lint_tables}
<p class="cap">Hint rules are skipped on the catalog (it has no tags) rather than counted as findings.</p>
</section>
<section class="pane" id="pane-how">
<div class='h3'>Where the numbers come from</div>{table(['item', 'value', 'check'], prov_rows, raw=True)}
<div class='h3'>How the checks run</div>
<ul><li><strong>Real adapters, not copies.</strong> Each check imports the installed provider package (for example <code>composio_google.GoogleProvider</code>) and calls its own <code>wrap_tool</code>.</li>
<li><strong>Offline.</strong> Network sockets are blocked during conversion, and any attempt to execute a tool raises.</li>
<li><strong>One bad tool never stops a run.</strong> A missing provider SDK is reported as unavailable, not as a failure.</li></ul>
<div class='h3'>Adapter versions used</div>{versions}
<div class='h3'>Tests</div><p class="cap">{T.get('passed')} of {T.get('tests')} passed, {T.get('failed', T.get('failures', 0))} failed, {T.get('skipped', 0)} skipped ({T.get('seconds')}s).</p>{test_rows}
<div class='h3'>Reproduce everything</div>
<pre>pip install -e "tool-schema-doctor[all,dashboard]"
python tool-schema-doctor/make_evidence.py   # every command on this page, the tests, and the provenance above
python tool-schema-doctor/build_static.py    # rebuild this page</pre>
<p><strong>Limits.</strong> The 930-tool fixture is a test mock and is GitHub-heavy; results reflect the adapter versions above; the selection eval is a small, curated, model-dependent check.</p>
</section>
"""

STATIC_CSS = """
*{box-sizing:border-box} html{scroll-behavior:smooth} body{margin:0;background:#fff;color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased;line-height:1.5}
.wrap{max-width:1040px;margin:0 auto;padding:0 1.6rem}
.card{border:1px solid var(--line);border-radius:16px;padding:1.2rem 1.4rem .9rem;margin:0 0 1.2rem;background:#fff}
.card h3{font-size:1.3rem;font-weight:500;letter-spacing:-.02em;line-height:1.25;margin:.15rem 0 .7rem}
.card p,.pane p,li{line-height:1.62;margin:.2rem 0 .6rem} .cap{color:var(--muted);font-size:.88rem}
details{border-top:1px solid var(--line);margin-top:1rem;padding-top:.8rem}
summary{font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;cursor:pointer;padding-bottom:.3rem}
.scroll{overflow-x:auto} table{border-collapse:collapse;width:100%;font-size:.86rem;margin:.5rem 0 1rem}
th{font-family:var(--mono);font-size:.64rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);text-align:left;font-weight:500}
th,td{padding:.5rem .8rem .5rem 0;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
pre{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:.9rem 1rem;overflow:auto;font-family:var(--mono);font-size:.76rem;line-height:1.55;margin:.4rem 0 1rem;white-space:pre-wrap;overflow-wrap:anywhere}
code{font-family:var(--mono);font-size:.86em;background:rgba(0,0,0,.06);border-radius:4px;padding:.05em .3em;overflow-wrap:anywhere}
a{color:var(--blue);text-underline-offset:2px} .navr a,.btn,.footer a{color:inherit}
.btn{color:var(--ink)} .btn.ghost{color:#fff} .footer a{color:#cfcfcf}
.tabs{display:flex;gap:1.6rem;border-bottom:1px solid var(--line);margin:0 0 1.4rem}
.tab{font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;background:none;border:none;border-bottom:2px solid transparent;padding:.7rem 0;cursor:pointer;color:var(--muted)}
.tab.on{color:var(--ink);border-bottom-color:var(--blue)} .pane{display:none} .pane.on{display:block}
#q{display:block;width:100%;max-width:670px;font-size:.85rem;padding:.8rem 2.8rem .8rem .9rem;border:1px solid var(--ink);border-radius:2px;background-color:#fff;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'%3E%3Cpath d='m3 6 5 5 5-5' fill='none' stroke='%230f0f0f' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .9rem center;background-size:1rem;margin:.35rem 0 1.1rem;cursor:pointer;appearance:none;-webkit-appearance:none}
#q:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.tool-picker-label{display:block;font-family:var(--mono);font-size:.7rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:.9rem 0 .2rem}
.two{display:grid;grid-template-columns:1fr 1fr;gap:2rem} @media(max-width:760px){.two{grid-template-columns:1fr}}
.ok{color:#17a368}.err{color:#e5484d}.chg{color:#b7791f} td.o{font-family:var(--mono);font-size:.78rem;white-space:nowrap}
.sec{scroll-margin-top:1rem}
"""

JS = """
const DATA = JSON.parse(document.getElementById('data').textContent);
const q = document.getElementById('q'), out = document.getElementById('out'), cmd = document.getElementById('cmd');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function show(){
  const slug = q.value.trim(), rows = DATA[slug];
  cmd.textContent = 'tool-schema-doctor compatibility --input tool-schema-doctor/out/evidence/live/' + (slug || '<tool>') + '.json --verbose';
  if(!rows){ out.innerHTML = slug ? '<p class="cap">No tool with that exact name. Pick one from the list.</p>' : ''; return; }
  const cls = {OK:'ok', Changed:'chg', Error:'err'};
  let h = '<div class="scroll"><table><thead><tr><th>provider</th><th>outcome</th><th>what happened</th></tr></thead><tbody>';
  for(const [prov, outcome, detail, path] of rows){
    const short = outcome === 'Error' ? (path ? 'at ' + path + ': ' : '') + detail.slice(0, 140) + (detail.length > 140 ? '…' : '') : detail;
    h += '<tr><td class="o">' + esc(prov) + '</td><td class="o ' + (cls[outcome] || '') + '">' + esc(outcome) + '</td><td>' + esc(short) + '</td></tr>';
  }
  h += '</tbody></table></div>';
  for(const [prov, outcome, detail] of rows){
    if(outcome === 'Error') h += '<div class="lbl">Full ' + esc(prov) + ' error, exactly as the adapter raised it</div><pre>' + esc(detail) + '</pre>';
  }
  out.innerHTML = h;
}
q.addEventListener('change', show); show();
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.pane').forEach(p => p.classList.toggle('on', p.id === 'pane-' + b.dataset.t));
}));
"""

THEME = (HERE / "theme.css").read_text(encoding="utf-8")
DESC = (f"Composio's tool schemas, run through the real provider adapters: {len(adapter_errors)} tools fail to convert, "
        f"{strict_n} lose OpenAI strict mode, Gemini drops enums on {enum_dropped} of {enum_total}, {len(missing_hint)} of {n_tools} lack action hints. "
        "An independent analysis with evidence for every claim.")
PAGE = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tool-Schema Doctor: what breaks before an agent does</title>
<meta name="description" content="{e(DESC, quote=True)}">
<meta property="og:title" content="Tool-Schema Doctor"><meta property="og:description" content="{e(DESC, quote=True)}"><meta property="og:type" content="website">
<meta name="robots" content="index,follow">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230007cd'/%3E%3C/svg%3E">
<style>{THEME}{STATIC_CSS}</style>
</head><body>
{HERO}
{TOOL_CHECKER}
<main class="wrap">
<div class="sec" id="fixes" style="margin-top:4.4rem">What to fix, <span class="acc">in priority order</span></div>
<div class="sub">Open Evidence on any item for the affected tools, the raw errors, the upstream code, the command that reproduces it, and the tests that pin it.</div>
{''.join(CARDS)}
<div class="sec" id="deeper">Go <span class="acc">deeper</span></div>
{DEEPER}
</main>
<div class="footer" style="margin-top:4.5rem"><div class="inner">Every number on this page is read from saved CLI output. Tool fixtures and adapter code are from <a href="{REPO}/tree/{SHA}" target="_blank" rel="noopener">ComposioHQ/composio</a> (MIT). This is an independent project and is not affiliated with or endorsed by Composio.</div></div>
<script type="application/json" id="data">{TOOLS_JSON}</script>
<script>{JS}</script>
</body></html>
"""

# ------------------------------------------------------------------ write
if SITE.exists():
    shutil.rmtree(SITE)
(SITE / "evidence" / "cli").mkdir(parents=True)
(SITE / "index.html").write_text(PAGE, encoding="utf-8")
for c in CMDS.values():
    f = HERE / c.get("output_file", "")
    if f.is_file():
        shutil.copy(f, SITE / "evidence" / "cli" / f.name)
print(f"wrote {SITE / 'index.html'} ({len(PAGE) // 1024} KB), {len(list((SITE / 'evidence' / 'cli').glob('*.txt')))} evidence files")
