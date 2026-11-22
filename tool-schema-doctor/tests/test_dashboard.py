"""Headless smoke tests for the Streamlit dashboard (no browser needed).

Uses Streamlit's own AppTest runner to execute streamlit_app.py against the saved
evidence in out/. Skipped when Streamlit or the generated evidence is missing.
"""

import json
import re
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

HERE = Path(__file__).resolve().parents[1]
APP = HERE / "streamlit_app.py"
EVIDENCE = HERE / "out" / "evidence" / "evidence.json"

pytestmark = pytest.mark.skipif(not EVIDENCE.exists(),
                                reason="run make_evidence.py first to generate out/evidence/")


def _run():
    at = st_testing.AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    return at


def _expected_stats():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    full = json.loads((HERE / "out" / "compat_full.json").read_text(encoding="utf-8"))
    mock = json.loads((HERE / "out" / "report-mock" / "report.json").read_text(encoding="utf-8"))
    causes = evidence["causes"]
    missing_hints = sum(f["rule_id"] == "missing-action-hint" for f in mock.get("lint", []))
    enum_total = causes["tools_with_enum"]
    enum_dropped = causes["dropped_by_provider"]["gemini"].get("enum", 0)
    return [str(len(causes["adapter_errors"])), str(causes["strict_unsupported_tools"]),
            f"{enum_dropped} / {enum_total}", f"{missing_hints} / {full['tools']}"]


def test_dashboard_renders_without_exceptions():
    at = _run()
    assert not at.exception, [e.message for e in at.exception]
    page = "\n".join(m.value for m in at.markdown)
    assert re.findall(r"<div class='stat-label'>([^<]*)</div>", page) == [
        "Tools that fail to convert", "No OpenAI strict mode", "Gemini drops enums", "Missing action hints"]
    # the four numbers come from saved evidence, not from a fixture-specific constant
    nums = re.findall(r"<div class='stat-num'>([^<]*)</div>", page)
    assert nums == _expected_stats()
    # independence is stated at the very top of the page
    assert "Not affiliated with or endorsed by Composio" in page


def test_fix_list_has_five_findings_and_all_pinned_tests_pass():
    at = _run()
    text = "\n".join(m.value for m in at.markdown)
    titles = [m.value for m in at.markdown if m.value.startswith("#### ")]
    assert text.count("<div class='lbl'>Fix</div>") == len(titles)
    assert text.count("<div class='lbl'>Why it matters</div>") == len(titles)
    # each finding lists the tests that pin it: "✓ `test_x` · ✓ `test_y`" (✗ failed, – skipped, ? missing)
    pinned = [m.value for m in at.markdown if re.match(r"^[✓✗–?] `test_", m.value)]
    assert len(pinned) == len(titles)
    # every listed test has a ✓ in front of it, none is failed, skipped or missing
    assert all(p.count("✓ `test_") == p.count("`test_") for p in pinned), pinned
    assert all(not re.search(r"[✗–?] `test_", p) for p in pinned), pinned


def test_fixed_upstream_finding_is_labelled_and_listed_last():
    import json

    status = json.loads((HERE / "out" / "evidence" / "upstream_status.json").read_text(encoding="utf-8"))
    if status["findings"]["vertex"]["status"] != "fixed_upstream":
        pytest.skip("Vertex finding is not marked fixed upstream")
    at = _run()
    titles = [m.value for m in at.markdown if m.value.startswith("#### ")]
    assert titles
    assert "vertex" in titles[-1].lower() and titles[-1].startswith(f"#### {len(titles)}.")
    assert all("fixed upstream" not in t.lower() for t in titles[:-1])
    assert any("d-fixed" in m.value and "Fixed upstream" in m.value for m in at.markdown)
    assert any("class='note'" in m.value and "pull/4751" in m.value for m in at.markdown)


def test_dashboard_works_without_the_composio_checkout(wtmp):
    # Simulates a deployed copy: the app + its saved evidence, but no composio-upstream/.
    import shutil

    app_dir = wtmp / "tool-schema-doctor"
    app_dir.mkdir()
    shutil.copy(APP, app_dir / "streamlit_app.py")
    shutil.copytree(HERE / "out", app_dir / "out")
    assert not (wtmp / "composio-upstream").exists()

    at = st_testing.AppTest.from_file(str(app_dir / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    # destructive tools' tags come from the evidence file, not the checkout
    tags_df = next(d.value for d in at.dataframe if "hint tags it has today" in d.value.columns)
    assert "hint tags it has today" in tags_df.columns
    assert all(isinstance(value, str) for value in tags_df["hint tags it has today"])
    # no broken live button; an explanation instead
    assert not [b for b in at.button if b.label == "Run it now"]
    assert any("Live re-run needs the Composio checkout" in c.value for c in at.caption)


def test_check_a_tool_shows_the_full_untruncated_adapter_error():
    at = _run()
    full = json.loads((HERE / "out" / "compat_full.json").read_text(encoding="utf-8"))
    slug = next((r["slug"] for r in full["results"]
                 if r["provider"] == "openai_strict" and r["status"] == "error"), None)
    if slug is None:
        pytest.skip("the current fixture has no OpenAI strict-mode failures")
    at.selectbox[0].set_value(slug).run()
    assert not at.exception
    # the "Check a tool" block is "<ErrorType>: <message>" (CLI JSON output elsewhere also
    # mentions strict-unsupported, so match the block's own format)
    errors = [c.value for c in at.code if c.value.startswith("ValueError: strict-unsupported:")]
    assert errors, "full openai_strict error block not shown"
    msg = errors[0]
    assert "truncated" not in msg
    assert "strict-unsupported: " in msg and len(msg) > 100
