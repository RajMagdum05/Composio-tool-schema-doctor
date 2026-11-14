import json

from tool_schema_doctor.model import ToolRecord, CompatResult, to_jsonable
from tool_schema_doctor.report import build_report, render_markdown


def _recs():
    return [
        # description repeats the (Unicode) name -> triggers description-repeats-name,
        # whose evidence captures the Unicode text into the report.
        ToolRecord(slug="GH_X", name="Café 日本 ✓", description="Café 日本 ✓",
                   tags=["openWorldHint"], input_parameters={"type": "object", "properties": {}},
                   toolkit="GH", source="mock"),
        ToolRecord(slug="GH_GET", name="Get", description="Fetches a thing by id.",
                   tags=["readOnlyHint"], input_parameters={"type": "object"},
                   toolkit="GH", source="mock"),
    ]


def test_report_renders_unicode_without_crashing():
    rep = build_report(_recs(), run_compat=False)   # lint only, no adapters/network
    md = render_markdown(rep)
    # render must not crash on Unicode and produces a real report
    assert isinstance(md, str) and "Tool-Schema Doctor" in md and "Metadata lint" in md
    # Unicode flows into finding evidence and JSON-serializes cleanly (ensure_ascii=False).
    blob = json.dumps(to_jsonable(rep), ensure_ascii=False)
    assert "日本" in blob


def test_report_failing_conversions_table():
    rep = build_report(_recs(), run_compat=False)
    # inject a compat error to exercise the failures table
    rep.compatibility = [CompatResult("GH_X", "google_vertex", "error",
                                      error_type="ParseError", message="boom",
                                      schema_path="/properties/x/examples")]
    rep.meta["compatibility_summary"] = {"google_vertex": {"error": 1}}
    md = render_markdown(rep)
    assert "Failing conversions" in md
    assert "/properties/x/examples" in md


def test_catalog_source_skips_compat():
    recs = [ToolRecord(slug="A_X", name="X", description="d", tags=[],
                       input_parameters=None, toolkit="A", source="catalog")]
    rep = build_report(recs, run_compat=True)
    assert any("compatibility" in s for s in rep.skipped)
    assert rep.meta["counts"]["with_schema"] == 0
