import json

import pytest

from tool_schema_doctor.loader import InputError, load_tools, parse_data


def test_parse_mock_shape():
    data = [
        {"slug": "GITHUB_X", "name": "X", "description": "d", "tags": ["readOnlyHint"],
         "input_parameters": {"type": "object", "properties": {}}},
    ]
    recs = parse_data(data)
    assert len(recs) == 1
    r = recs[0]
    assert r.slug == "GITHUB_X" and r.source == "mock"
    assert r.has_schema and r.has_tags
    assert r.toolkit == "GITHUB"


def test_parse_catalog_shape():
    data = [
        {"slug": "github", "tools": [
            {"slug": "GITHUB_X", "name": "X", "description": "d1"},
            {"slug": "GITHUB_Y", "name": "Y", "description": "d2"},
        ]},
    ]
    recs = parse_data(data)
    assert len(recs) == 2
    assert all(r.source == "catalog" for r in recs)
    assert recs[0].toolkit == "github"
    assert not recs[0].has_schema  # catalog has no schemas


def test_malformed_raises():
    with pytest.raises(InputError):
        parse_data([{"no_slug": 1}])
    with pytest.raises(InputError):
        parse_data(42)


def test_load_missing_file(wtmp):
    with pytest.raises(InputError):
        load_tools(wtmp / "nope.json")


def test_load_invalid_json(wtmp):
    p = wtmp / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError):
        load_tools(p)


def test_load_roundtrip(wtmp):
    p = wtmp / "tools.json"
    p.write_text(json.dumps([{"slug": "A_B", "name": "n",
                              "input_parameters": {"type": "object"}}]), encoding="utf-8")
    recs = load_tools(p)
    assert recs[0].slug == "A_B"
