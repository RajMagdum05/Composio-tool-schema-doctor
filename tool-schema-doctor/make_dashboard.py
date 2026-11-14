"""Generate a self-contained HTML dashboard from the report artifacts in out/.

No external dependencies, no server needed to build. Reads the JSON the CLI
produced and inlines it into a single HTML file with vanilla-JS rendering.

Usage:  python make_dashboard.py            # writes out/dashboard.html
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def load(p):
    fp = OUT / p
    return json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else None


def build_data() -> dict:
    compat = load("compat_full.json")
    mock = load("report-mock/report.json")
    catalog = load("report-catalog/report.json")
    evals = {
        "openai/gpt-oss-20b": load("eval_report.json"),
        "qwen/qwen3.8-27b": load("eval_report_qwen.json"),
        "allam-2-7b": load("eval_report_allam.json"),
    }

    data: dict = {}

    # --- compatibility ---
    if compat:
        order = ["openai", "openai_strict", "anthropic", "google_vertex", "gemini", "google_adk"]
        summ = compat["summary"]
        data["compat"] = {
            "tools": compat.get("tools"),
            "summary": [{"provider": p, **{k: summ.get(p, {}).get(k, 0)
                                           for k in ("ok", "transformed", "error", "unavailable")}}
                        for p in order if p in summ],
            "failures": [
                {"slug": r["slug"], "provider": r["provider"],
                 "error_type": r.get("error_type"), "schema_path": r.get("schema_path"),
                 "message": (r.get("message") or "")[:140]}
                for r in compat.get("results", []) if r.get("status") == "error"
            ],
        }

    # --- lint (mock + catalog) ---
    data["lint"] = {}
    for name, rep in (("mock", mock), ("catalog", catalog)):
        if rep:
            ls = rep["meta"].get("lint_summary", {})
            data["lint"][name] = {
                "tools": rep["meta"]["counts"]["tools"],
                "total": ls.get("total", 0),
                "by_rule": ls.get("by_rule", {}),
                "skipped": rep.get("skipped", []),
            }

    # --- eval ---
    data["eval"] = {"models": [], "tasks": None}
    for model, rep in evals.items():
        if not rep:
            continue
        m = rep["metrics"]
        data["eval"]["models"].append({
            "model": model,
            "accuracy": m["accuracy"], "correct": m["correct"], "total": m["total"],
            "invalid": m["invalid_slug_count"],
            "by_difficulty": {k: v["accuracy"] for k, v in m.get("by_difficulty", {}).items()},
            "wrong": [r["id"] for r in rep["results"] if not r["correct"]],
        })
    # per-task table from the primary model, annotated with who missed it
    primary = evals.get("openai/gpt-oss-20b")
    if primary:
        missed_by = {}
        for model, rep in evals.items():
            if rep:
                for r in rep["results"]:
                    if not r["correct"]:
                        missed_by.setdefault(r["id"], []).append(model)
        data["eval"]["tasks"] = [
            {"id": r["id"], "category": r["category"], "difficulty": r["difficulty"],
             "expected": r["expected"], "missed_by": missed_by.get(r["id"], [])}
            for r in primary["results"]
        ]

    # --- worked example #1: a real schema that breaks a provider ---
    data["walkthrough"] = _walkthrough(compat)

    # --- worked example #2: a real ambiguous selection task ---
    data["eval_example"] = _eval_example(evals)

    return data


ROOT = HERE.parent  # the project root (sibling of composio-upstream/)
MOCK_PATH = ROOT / "composio-upstream" / "ts" / "packages" / "cli" / "test" / "__mocks__" / "tools.json"
DATASET_PATH = HERE / "src" / "tool_schema_doctor" / "data" / "eval_dataset.json"


def _walkthrough(compat, slug="GOOGLEDRIVE_UPLOAD_FILE"):
    """Show one real tool: the offending schema fragment + each provider's outcome."""
    if not MOCK_PATH.exists() or not compat:
        return None
    mock = {t["slug"]: t for t in json.loads(MOCK_PATH.read_text(encoding="utf-8"))}
    tool = mock.get(slug)
    if not tool:
        return None
    props = (tool.get("input_parameters") or {}).get("properties", {})
    key = "file_to_upload" if "file_to_upload" in props else (next(iter(props), None))
    fragment = {key: props.get(key)} if key else {}
    # per-provider outcome for this tool (from the full compat results)
    full = load("compat_full.json") or {}
    order = ["openai", "openai_strict", "anthropic", "google_vertex", "gemini", "google_adk"]
    by_prov = {r["provider"]: r for r in full.get("results", []) if r["slug"] == slug}
    outcomes = []
    for p in order:
        r = by_prov.get(p)
        if not r:
            continue
        outcomes.append({
            "provider": p, "status": r["status"],
            "detail": (r.get("error_type") and f"{r['error_type']} @ {r.get('schema_path') or '?'}")
                      or (", ".join(r.get("dropped_keywords") or []) and
                          "dropped: " + ", ".join(r.get("dropped_keywords"))) or "clean",
        })
    return {"slug": slug, "description": (tool.get("description") or "")[:200],
            "fragment": fragment, "outcomes": outcomes}


def _eval_example(evals, task_id="t27"):
    """Show one real selection task: request, candidates (+descriptions), expected, each model's pick."""
    if not DATASET_PATH.exists():
        return None
    ds = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    task = next((t for t in ds["tasks"] if t["id"] == task_id), None)
    if not task:
        return None
    # resolve candidate descriptions from the fixtures
    corpus = {}
    for cp in (MOCK_PATH, ROOT / "composio-upstream" / "docs" / "public" / "data" / "toolkits.json"):
        if not cp.exists():
            continue
        raw = json.loads(cp.read_text(encoding="utf-8"))
        tools = raw if isinstance(raw, list) and raw and "tools" not in raw[0] else \
            [t for tk in raw for t in (tk.get("tools") or [])]
        for t in tools:
            corpus.setdefault(t["slug"], (t.get("description") or ""))
    candidates = [{"slug": s, "description": corpus.get(s, "")[:160]} for s in task["candidates"]]
    picks = {}
    for model, rep in evals.items():
        if not rep:
            continue
        r = next((x for x in rep["results"] if x["id"] == task_id), None)
        if r:
            picks[model.split("/")[-1]] = {"chosen": r["chosen"], "correct": r["correct"]}
    return {"id": task_id, "request": task["user_request"], "candidates": candidates,
            "expected": task["expected"], "rationale": task["rationale"],
            "category": task["ambiguity_category"], "difficulty": task["difficulty"], "picks": picks}


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tool-Schema Doctor</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--fg:#e6edf3;--muted:#8b949e;
 --ok:#2ea043;--transformed:#d29922;--error:#f85149;--accent:#58a6ff;--chip:#21262d}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){--bg:#f6f8fa;--panel:#fff;--border:#d0d7de;--fg:#1f2328;--muted:#656d76;--chip:#eaeef2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:26px;margin:0 0 2px}h2{font-size:19px;margin:34px 0 12px;border-bottom:1px solid var(--border);padding-bottom:6px}
.sub{color:var(--muted);margin:0 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
.tile .n{font-size:26px;font-weight:700}.tile .l{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:top}
th{color:var(--muted);font-weight:600;background:var(--chip)}tr:last-child td{border-bottom:0}
code{background:var(--chip);padding:1px 5px;border-radius:5px;font-size:12px;word-break:break-all}
.bar{display:flex;height:22px;border-radius:5px;overflow:hidden;min-width:120px}
.bar span{display:block}.bar .ok{background:var(--ok)}.bar .transformed{background:var(--transformed)}.bar .error{background:var(--error)}
.legend{display:flex;gap:16px;color:var(--muted);font-size:13px;margin:8px 0 14px;flex-wrap:wrap}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle}
.err{color:var(--error);font-weight:600}.mut{color:var(--muted)}
.rulebar{height:10px;background:var(--accent);border-radius:5px;display:inline-block;vertical-align:middle;margin-right:8px}
.pill{display:inline-block;background:var(--chip);border:1px solid var(--border);border-radius:20px;padding:1px 9px;font-size:12px;margin:2px}
.miss{color:var(--error)}
.acc{font-weight:700}
</style></head><body><div class="wrap">
<h1>Tool-Schema Doctor</h1>
<p class="sub">Offline QA for Composio tool schemas — reusing the real provider adapters. Live view of the generated reports.</p>
<div id="app"></div>
</div>
<script>const DATA = __DATA__;
const $=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild};
const app=document.getElementById('app');
function tiles(){const c=DATA.compat||{},l=DATA.lint||{},e=DATA.eval||{};
 const fails=(c.failures||[]).length;
 const items=[['Tools checked',c.tools??'—'],['Providers',(c.summary||[]).length],
  ['Compat failures',fails],['Lint findings (mock)',(l.mock||{}).total??'—'],
  ['Eval models',(e.models||[]).length]];
 return `<div class="tiles">${items.map(([l,n])=>`<div class="tile"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('')}</div>`}
function compatSection(){const c=DATA.compat;if(!c)return '';
 const max=Math.max(...c.summary.map(r=>r.ok+r.transformed+r.error+r.unavailable),1);
 const rows=c.summary.map(r=>{const tot=r.ok+r.transformed+r.error+r.unavailable;
  const w=x=>(100*x/max).toFixed(2)+'%';
  return `<tr><td><code>${r.provider}</code></td>
   <td style="min-width:260px"><div class="bar">
     <span class="ok" style="width:${w(r.ok)}" title="ok ${r.ok}"></span>
     <span class="transformed" style="width:${w(r.transformed)}" title="transformed ${r.transformed}"></span>
     <span class="error" style="width:${w(r.error)}" title="error ${r.error}"></span></div></td>
   <td>${r.ok}</td><td>${r.transformed}</td><td class="${r.error?'err':''}">${r.error}</td></tr>`}).join('');
 const hard=c.failures.filter(f=>f.provider!=='openai_strict');
 const strict=c.failures.filter(f=>f.provider==='openai_strict');
 const frows=hard.map(f=>`<tr><td><code>${f.slug}</code></td><td><code>${f.provider}</code></td>
   <td>${f.error_type||''}</td><td><code>${f.schema_path||''}</code></td></tr>`).join('');
 return `<h2>Provider compatibility (930 tools, through the real adapters)</h2>
  <div class="legend"><span><i class="dot" style="background:var(--ok)"></i>ok</span>
   <span><i class="dot" style="background:var(--transformed)"></i>transformed (converted, keyword dropped)</span>
   <span><i class="dot" style="background:var(--error)"></i>error (hard failure)</span></div>
  <table><thead><tr><th>Provider</th><th>Distribution</th><th>ok</th><th>transformed</th><th>error</th></tr></thead><tbody>${rows}</tbody></table>
  <h2>Hard failures — tool &amp; exact schema path <span class="mut">(${hard.length} + ${strict.length} OpenAI-strict unsupported)</span></h2>
  <table><thead><tr><th>Tool</th><th>Provider</th><th>Error</th><th>Schema path</th></tr></thead><tbody>${frows}</tbody></table>
  <p class="mut">Plus <b>${strict.length}</b> tools that OpenAI strict mode cannot express (provider falls back to non-strict).</p>`}
function lintSection(){const l=DATA.lint;if(!l)return '';
 function block(name,d){if(!d)return '';const max=Math.max(...Object.values(d.by_rule),1);
  const rows=Object.entries(d.by_rule).sort((a,b)=>b[1]-a[1]).map(([r,n])=>
   `<tr><td><code>${r}</code></td><td style="min-width:220px"><span class="rulebar" style="width:${(200*n/max)|0}px"></span>${n}</td></tr>`).join('');
  const sk=(d.skipped||[]).filter(s=>s.startsWith('lint')).map(s=>`<span class="pill">${s.replace('lint:','').split(':')[0]} skipped</span>`).join(' ');
  return `<h3 style="margin:16px 0 6px">${name} — ${d.tools.toLocaleString()} tools, ${d.total.toLocaleString()} findings</h3>
   <table><thead><tr><th>Rule</th><th>Count</th></tr></thead><tbody>${rows}</tbody></table>${sk?`<div style="margin:8px 0">${sk}</div>`:''}`}
 return `<h2>Metadata lint</h2>${block('Mock corpus (has tags + schemas)',l.mock)}${block('Docs catalog (names/descriptions only)',l.catalog)}
  <p class="mut">Denominators are kept separate: hint/compat rules run on the mock; name/description rules run on the catalog.</p>`}
function evalSection(){const e=DATA.eval;if(!e||!e.models.length)return '';
 const mrows=e.models.map(m=>`<tr><td><code>${m.model}</code></td>
   <td class="acc">${(m.accuracy*100).toFixed(1)}%</td><td>${m.correct}/${m.total}</td>
   <td>${m.invalid}</td><td class="${m.wrong.length?'miss':'mut'}">${m.wrong.join(', ')||'—'}</td></tr>`).join('');
 const tasks=(e.tasks||[]).map(t=>`<tr><td><code>${t.id}</code></td><td>${t.category}</td><td>${t.difficulty}</td>
   <td><code>${t.expected}</code></td><td class="${t.missed_by.length?'miss':'mut'}">${t.missed_by.map(x=>x.split('/').pop()).join(', ')||'all correct'}</td></tr>`).join('');
 return `<h2>LLM tool-selection eval <span class="mut">(27 ambiguous tasks, selection only)</span></h2>
  <table><thead><tr><th>Model</th><th>Accuracy</th><th>Correct</th><th>Invalid</th><th>Missed</th></tr></thead><tbody>${mrows}</tbody></table>
  <h3 style="margin:16px 0 6px">Per-task (missed-by column shows which model got it wrong)</h3>
  <table><thead><tr><th>Task</th><th>Category</th><th>Difficulty</th><th>Expected tool</th><th>Missed by</th></tr></thead><tbody>${tasks}</tbody></table>`}
app.innerHTML = tiles()+compatSection()+lintSection()+evalSection();
</script></body></html>"""


def main():
    data = build_data()
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    out = OUT / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
