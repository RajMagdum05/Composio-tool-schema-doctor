import json

import pytest

from tool_schema_doctor.cli import main

TINY = [
    {"slug": "GH_GET_THING", "name": "Get thing", "description": "Get thing",
     "tags": ["readOnlyHint"],
     "input_parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"slug": "GH_CREATE_THING", "name": "Create thing", "description": "Creates a thing from the given fields.",
     "tags": ["openWorldHint"],
     "input_parameters": {"type": "object", "properties": {"name": {"type": "string", "examples": ["x"]}}}},
]


@pytest.fixture
def tiny_input(wtmp):
    p = wtmp / "tiny.json"
    p.write_text(json.dumps(TINY), encoding="utf-8")
    return str(p)


def test_inspect(tiny_input, capsys):
    rc = main(["inspect", "--input", tiny_input])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tools"] == 2 and out["with_schema"] == 2


def test_lint(tiny_input, capsys):
    rc = main(["lint", "--input", tiny_input, "--verbose"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    slugs = {f["slug"] for f in out["findings"] if f["rule_id"] == "missing-action-hint"}
    assert "GH_CREATE_THING" in slugs            # openWorldHint only -> no action hint
    assert "GH_GET_THING" not in slugs           # readOnlyHint -> ok
    rr = {f["slug"] for f in out["findings"] if f["rule_id"] == "description-repeats-name"}
    assert "GH_GET_THING" in rr                  # desc == name


def test_compatibility_fast_provider(tiny_input, capsys):
    rc = main(["compatibility", "--input", tiny_input, "--providers", "openai_strict", "--verbose"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "openai_strict" in out["summary"]


def test_report_markdown_no_compat(tiny_input, capsys):
    rc = main(["report", "--input", tiny_input, "--no-compat", "--format", "markdown"])
    assert rc == 0
    md = capsys.readouterr().out
    assert md.startswith("# Tool-Schema Doctor")
    assert "Metadata lint" in md


def test_report_writes_files(tiny_input, wtmp, capsys):
    outdir = wtmp / "rep"
    rc = main(["report", "--input", tiny_input, "--no-compat", "--format", "both", "-o", str(outdir)])
    assert rc == 0
    assert (outdir / "report.json").exists()
    assert (outdir / "report.md").exists()
    data = json.loads((outdir / "report.json").read_text(encoding="utf-8"))
    assert data["meta"]["counts"]["tools"] == 2


def test_unknown_provider_exit2(tiny_input):
    assert main(["compatibility", "--input", tiny_input, "--providers", "nope"]) == 2


def test_missing_input_exit2(wtmp):
    assert main(["inspect", "--input", str(wtmp / "absent.json")]) == 2
