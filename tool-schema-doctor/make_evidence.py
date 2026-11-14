"""Collect the evidence the dashboard shows, by running the real CLI.

For each finding it runs the exact `tool-schema-doctor` command an engineer
would run and saves the stdout verbatim, so the dashboard shows real CLI output,
not a summary. It also runs the test suite (JUnit XML) and records provenance:
upstream commit, fixture git blob hashes, and installed adapter versions.

Run from the project root (the folder that contains composio-upstream/):
    .venv-investigate/Scripts/python tool-schema-doctor/make_evidence.py

Outputs (all under tool-schema-doctor/out/):
    compat_full.json          full verbose compatibility run (all providers)
    evidence/cli/<id>.txt     verbatim CLI output per finding
    evidence/test-results.xml pytest JUnit report
    evidence/evidence.json    index the dashboard reads
"""

from __future__ import annotations

import collections
import datetime as dt
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tool-schema-doctor/
ROOT = HERE.parent                              # project root
UP = ROOT / "composio-upstream"
OUT = HERE / "out"
EV = OUT / "evidence"
CLI_DIR = EV / "cli"

MOCK = "composio-upstream/ts/packages/cli/test/__mocks__/tools.json"
CATALOG = "composio-upstream/docs/public/data/toolkits.json"
GEMINI_CASES = "tool-schema-doctor/out/evidence/gemini_cases.json"

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run_cli(cid: str, args: list[str], *, save: bool = True) -> dict:
    """Run `python -m tool_schema_doctor.cli <args>` from ROOT; save stdout verbatim."""
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", "tool_schema_doctor.cli", *args],
                          cwd=ROOT, env=ENV, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)
    rec = {"id": cid, "command": "tool-schema-doctor " + " ".join(args),
           "exit_code": proc.returncode, "seconds": round(time.time() - t0, 1)}
    if save:
        CLI_DIR.mkdir(parents=True, exist_ok=True)
        (CLI_DIR / f"{cid}.txt").write_text(proc.stdout, encoding="utf-8")
        rec["output_file"] = f"out/evidence/cli/{cid}.txt"
    print(f"  [{rec['exit_code']}] {rec['command']}  ({rec['seconds']}s)", flush=True)
    return rec


def git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", str(UP), *args], capture_output=True,
                              text=True, timeout=60).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def versions() -> dict:
    out = {}
    for pkg in ("composio", "composio-openai", "composio-anthropic", "composio-google",
                "composio-gemini", "composio-google-adk", "openai", "anthropic",
                "google-cloud-aiplatform", "google-genai", "google-adk", "groq"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def build_gemini_cases() -> str | None:
    """Two real tools: the one Gemini rejects + one whose enum Gemini drops."""
    mock = {t["slug"]: t for t in json.loads((ROOT / MOCK).read_text(encoding="utf-8"))}
    full = json.loads((OUT / "compat_full.json").read_text(encoding="utf-8"))
    enum_dropped = sorted(r["slug"] for r in full["results"]
                          if r["provider"] == "gemini" and "enum" in (r.get("dropped_keywords") or []))
    pick = next((s for s in enum_dropped if s.startswith("GITHUB_")), enum_dropped[0] if enum_dropped else None)
    cases = [mock["GOOGLEDRIVE_UPDATE_PERMISSION"]] + ([mock[pick]] if pick else [])
    p = ROOT / GEMINI_CASES
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    return pick


def run_tests() -> dict:
    xml = EV / "test-results.xml"
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"],
                          cwd=HERE, env=ENV, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)
    # pytest records the machine's hostname in the JUnit XML; drop it before saving.
    if xml.exists():
        import re
        xml.write_text(re.sub(r'hostname="[^"]*"', 'hostname=""', xml.read_text(encoding="utf-8")),
                       encoding="utf-8")
    res = {"exit_code": proc.returncode, "seconds": round(time.time() - t0, 1),
           "junit_file": "out/evidence/test-results.xml",
           "last_line": (proc.stdout.strip().splitlines() or [""])[-1]}
    try:
        root = ET.parse(xml).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        tests, fails = int(suite.get("tests", 0)), int(suite.get("failures", 0))
        errs, skips = int(suite.get("errors", 0)), int(suite.get("skipped", 0))
        res.update(tests=tests, failures=fails, errors=errs, skipped=skips,
                   passed=tests - fails - errs - skips)
        res["cases"] = [f"{c.get('classname')}::{c.get('name')}" for c in suite.iter("testcase")]
    except Exception as e:  # noqa: BLE001
        res["parse_error"] = str(e)
    print(f"  tests: {res.get('passed')}/{res.get('tests')} passed ({res['seconds']}s)", flush=True)
    return res


def derived_causes() -> dict:
    """Numbers the fix list cites, computed from the fresh full CLI run."""
    full = json.loads((OUT / "compat_full.json").read_text(encoding="utf-8"))
    R = full["results"]
    mock = json.loads((ROOT / MOCK).read_text(encoding="utf-8"))

    def has_kw(o, kw):
        if isinstance(o, dict):
            return kw in o or any(has_kw(v, kw) for v in o.values())
        if isinstance(o, list):
            return any(has_kw(v, kw) for v in o)
        return False

    dropped = {p: collections.Counter() for p in ("google_vertex", "gemini", "google_adk", "openai_strict")}
    for r in R:
        if r["provider"] in dropped:
            dropped[r["provider"]].update(r.get("dropped_keywords") or [])

    # Strict-mode causes come straight from the SDK, not from the (length-capped)
    # CLI message text, so a truncated message can't invent a keyword.
    from composio.utils.strict_schema import to_strict_json_schema

    by_slug = {t["slug"]: t for t in mock}
    strict = [r for r in R if r["provider"] == "openai_strict" and r["status"] == "error"]
    strict_kw, strict_example = collections.Counter(), {}
    for r in strict:
        res = to_strict_json_schema(by_slug[r["slug"]].get("input_parameters") or {})
        seen = set()
        for u in res.unsupported:
            seen.add(u.keyword)
            strict_example.setdefault(u.keyword, {"slug": r["slug"], "path": u.path, "detail": u.detail})
        strict_kw.update(seen)

    errors = [r for r in R if r["status"] == "error" and r["provider"] != "openai_strict"]

    # Hint tags of the destructive-sounding tools, saved here so the dashboard
    # doesn't need the upstream checkout to show them.
    from tool_schema_doctor.lint import ALL_HINTS, run_lint
    from tool_schema_doctor.loader import load_tools

    destructive, _ = run_lint(load_tools(ROOT / MOCK), ["destructive-verb-without-destructive-hint"])
    destructive_hint_tags = {f.slug: sorted(set(by_slug[f.slug].get("tags") or []) & ALL_HINTS)
                             for f in destructive}
    return {
        "destructive_hint_tags": destructive_hint_tags,
        "tools_with_enum": sum(1 for t in mock if has_kw(t.get("input_parameters"), "enum")),
        "dropped_by_provider": {p: dict(c.most_common()) for p, c in dropped.items()},
        "strict_unsupported_tools": len(strict),
        "strict_by_keyword": dict(strict_kw.most_common()),
        "strict_example": strict_example,
        "adapter_errors": [{k: r.get(k) for k in ("slug", "provider", "error_type", "schema_path", "message", "where")}
                           for r in errors],
    }


def main() -> None:
    EV.mkdir(parents=True, exist_ok=True)
    if "--tests-only" in sys.argv:
        # Re-run just the test suite and update its results (no CLI re-runs).
        ev = json.loads((EV / "evidence.json").read_text(encoding="utf-8"))
        ev["tests"] = run_tests()
        (EV / "evidence.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
        print("refreshed tests ->", EV / "evidence.json")
        return
    if "--causes-only" in sys.argv:
        # Recompute derived numbers from the existing full run (no CLI re-runs).
        ev = json.loads((EV / "evidence.json").read_text(encoding="utf-8"))
        ev["causes"] = derived_causes()
        (EV / "evidence.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
        print("recomputed causes ->", EV / "evidence.json")
        return
    print("Collecting evidence (runs the real CLI; Gemini/Vertex imports are slow)...", flush=True)

    enum_tool = build_gemini_cases()
    commands = {}
    commands["inspect"] = run_cli("inspect", ["inspect", "--input", MOCK])
    commands["strict"] = run_cli("strict", ["compatibility", "--input", MOCK, "--providers", "openai_strict"])
    commands["hints"] = run_cli("hints", ["lint", "--input", MOCK, "--rules",
                                          "missing-action-hint,destructive-verb-without-destructive-hint"])
    commands["names"] = run_cli("names", ["lint", "--input", CATALOG, "--rules",
                                          "duplicate-display-name-in-toolkit,description-repeats-name"])
    commands["vertex"] = run_cli("vertex", ["compatibility", "--input", MOCK, "--providers", "google_vertex"])
    commands["gemini"] = run_cli("gemini", ["compatibility", "--input", GEMINI_CASES,
                                            "--providers", "gemini", "--verbose"])
    commands["eval"] = run_cli("eval", ["eval"])
    # Full verbose run used for per-tool lookups (all six providers).
    commands["full"] = run_cli("full", ["compatibility", "--input", MOCK, "--verbose",
                                        "-o", "tool-schema-doctor/out/compat_full.json"], save=False)

    evidence = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "provenance": {
            "upstream_repo": "https://github.com/ComposioHQ/composio",
            "upstream_commit": git("rev-parse", "HEAD"),
            "upstream_commit_date": git("log", "-1", "--format=%cI"),
            "upstream_commit_subject": git("log", "-1", "--format=%s"),
            "upstream_dirty_files": len([x for x in git("status", "--porcelain").splitlines() if x.strip()]),
            "fixtures": {
                MOCK: git("rev-parse", "HEAD:ts/packages/cli/test/__mocks__/tools.json"),
                CATALOG: git("rev-parse", "HEAD:docs/public/data/toolkits.json"),
            },
            "python": platform.python_version(),
            "versions": versions(),
        },
        "commands": commands,
        "gemini_enum_example": enum_tool,
        "tests": run_tests(),
        "causes": derived_causes(),
    }
    (EV / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    bad = [c["command"] for c in commands.values() if c["exit_code"] != 0]
    print("wrote", EV / "evidence.json", "| non-zero exits:", bad or "none", flush=True)


if __name__ == "__main__":
    main()
