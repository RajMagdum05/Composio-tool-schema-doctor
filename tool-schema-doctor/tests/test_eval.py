"""Offline tests for the selection eval: dataset integrity + metrics logic.

No network. Live Groq calls are exercised separately (manual/opt-in).
"""

import json
from pathlib import Path

import pytest

from tool_schema_doctor import selection_eval as sev

# Locate the upstream fixtures absolutely (repo layout), independent of cwd.
_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = [
    _ROOT / "composio-upstream" / "ts" / "packages" / "cli" / "test" / "__mocks__" / "tools.json",
    _ROOT / "composio-upstream" / "docs" / "public" / "data" / "toolkits.json",
]


def _corpus_or_skip():
    paths = [str(p) for p in _CORPUS if p.exists()]
    if not paths:
        pytest.skip("upstream fixtures not available")
    return sev.build_corpus_map(paths)


def test_dataset_loads_and_shapes():
    ds = sev.load_dataset()
    assert ds["meta"]["selection_only"] is True
    assert len(ds["tasks"]) >= 20
    for t in ds["tasks"]:
        assert t["expected"] in t["candidates"]
        assert len(t["candidates"]) >= 2


def test_dataset_integrity_against_real_corpus():
    corpus = _corpus_or_skip()
    ds = sev.load_dataset()
    problems = sev.validate_dataset(ds, corpus)
    assert problems == [], f"dataset references unknown slugs: {problems}"


def test_metrics_with_stub_perfect_selector():
    corpus = _corpus_or_skip()
    ds = sev.load_dataset()
    # Tasks are keyed by their unique user_request line (several tasks share a
    # candidate SET deliberately, so match on the request text, not the set).
    by_request = {t["user_request"]: t for t in ds["tasks"]}

    def oracle(messages):
        text = messages[1]["content"]
        req = text.splitlines()[0].split("User request: ", 1)[1]
        t = by_request[req]
        return json.dumps({"chosen_slug": t["expected"], "reasoning": "oracle"})

    rep = sev.run_eval(ds, corpus, selector=oracle, model="test-oracle")
    assert rep.metrics["accuracy"] == 1.0
    assert rep.metrics["incorrect_selection_rate"] == 0.0
    assert rep.metrics["invalid_slug_count"] == 0
    assert rep.meta["model"] == "test-oracle"
    assert set(rep.metrics["by_category"]) and set(rep.metrics["by_difficulty"])


def test_metrics_with_stub_always_first():
    corpus = _corpus_or_skip()
    ds = sev.load_dataset()

    def first(messages):
        text = messages[1]["content"]
        slugs = [ln.split("slug: ", 1)[1].strip() for ln in text.splitlines() if "slug: " in ln]
        return json.dumps({"chosen_slug": slugs[0], "reasoning": "first"})

    rep = sev.run_eval(ds, corpus, selector=first, model="test-first")
    # all chosen slugs are valid candidates; accuracy is whatever the ordering yields (0..1)
    assert rep.metrics["invalid_slug_count"] == 0
    assert 0.0 <= rep.metrics["accuracy"] <= 1.0


def test_invalid_slug_is_counted():
    corpus = _corpus_or_skip()
    ds = sev.load_dataset()

    def bogus(messages):
        return json.dumps({"chosen_slug": "NOT_A_REAL_SLUG", "reasoning": "x"})

    rep = sev.run_eval(ds, corpus, selector=bogus, model="test-bogus")
    assert rep.metrics["invalid_slug_count"] == len(ds["tasks"])
    assert rep.metrics["accuracy"] == 0.0


def test_parse_selection_tolerates_case():
    chosen, _ = sev.parse_selection('{"chosen_slug":"github_create_an_issue","reasoning":"r"}',
                                    ["GITHUB_CREATE_AN_ISSUE", "GITHUB_ISSUES_CREATE"])
    assert chosen == "GITHUB_CREATE_AN_ISSUE"


@pytest.mark.parametrize("raw", ["[]", "5", "null", '"text"', "not json at all", ""])
def test_parse_selection_handles_non_dict_and_garbage(raw):
    chosen, reasoning = sev.parse_selection(raw, ["A", "B"])
    assert chosen is None and reasoning == ""


def test_parse_selection_missing_slug():
    chosen, _ = sev.parse_selection('{"reasoning":"no slug"}', ["A", "B"])
    assert chosen is None
