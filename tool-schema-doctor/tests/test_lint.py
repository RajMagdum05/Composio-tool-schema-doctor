from tool_schema_doctor.model import ToolRecord
from tool_schema_doctor.lint import run_lint, RULES


def rec(slug, name="", desc="", tags=None, toolkit=None, schema=None):
    return ToolRecord(slug=slug, name=name, description=desc, tags=tags or [],
                      input_parameters=schema, toolkit=toolkit or slug.split("_")[0],
                      source="mock" if tags is not None else "catalog")


# ---- missing-action-hint ----

def test_missing_action_hint_positive_and_negative():
    recs = [
        rec("GH_CREATE_ISSUE", tags=["openWorldHint"]),           # has a hint, but not an action hint -> flagged
        rec("GH_GET_ISSUE", tags=["readOnlyHint"]),               # action hint -> OK
    ]
    findings, skipped = run_lint(recs, ["missing-action-hint"])
    slugs = {f.slug for f in findings}
    assert slugs == {"GH_CREATE_ISSUE"}
    assert not skipped


def test_missing_action_hint_skipped_on_catalog():
    recs = [rec("GH_X", name="X", desc="d")]  # no tags -> catalog
    findings, skipped = run_lint(recs, ["missing-action-hint"])
    assert findings == []
    assert "missing-action-hint" in skipped


# ---- destructive-verb heuristic + allowlist ----

def test_destructive_verb_without_hint():
    recs = [
        rec("GH_DELETE_REPO", tags=["createHint"]),                       # destructive verb, no destructiveHint -> flagged
        rec("GH_DELETE_BRANCH", tags=["destructiveHint"]),               # has hint -> OK
        rec("GH_DOWNLOAD_A_REPOSITORY_ARCHIVE_ZIP", tags=["readOnlyHint"]),  # allowlisted (DOWNLOAD) -> OK
    ]
    findings, _ = run_lint(recs, ["destructive-verb-without-destructive-hint"])
    assert {f.slug for f in findings} == {"GH_DELETE_REPO"}


# ---- duplicate display name in toolkit ----

def test_duplicate_display_name_in_toolkit():
    recs = [
        rec("SLACK_SEND_MESSAGE", name="Send message", toolkit="SLACK"),
        rec("SLACK_CHAT_POST_MESSAGE", name="send message", toolkit="SLACK"),  # case-insensitive dup
        rec("SLACK_LIST_USERS", name="List users", toolkit="SLACK"),
        rec("GITHUB_SEND_MESSAGE", name="Send message", toolkit="GITHUB"),     # different toolkit -> not a dup
    ]
    findings, _ = run_lint(recs, ["duplicate-display-name-in-toolkit"])
    flagged = {f.slug for f in findings}
    assert flagged == {"SLACK_SEND_MESSAGE", "SLACK_CHAT_POST_MESSAGE"}


# ---- description rules ----

def test_description_repeats_name():
    recs = [
        rec("GITHUB_GET_AN_ORGANIZATION", name="Get an organization",
            desc="Get an organization"),            # repeats name -> flagged
        rec("GITHUB_GET_REPO", name="Get repo",
            desc="Fetch a repository by owner and name."),  # real desc -> OK
    ]
    findings, _ = run_lint(recs, ["description-repeats-name"])
    assert {f.slug for f in findings} == {"GITHUB_GET_AN_ORGANIZATION"}


def test_description_too_long_and_empty():
    recs = [
        rec("A_LONG", name="l", desc="x" * 2000),
        rec("A_EMPTY", name="e", desc=""),
        rec("A_OK", name="o", desc="short and clear"),
    ]
    long_f, _ = run_lint(recs, ["description-too-long"])
    empty_f, _ = run_lint(recs, ["description-empty"])
    assert {f.slug for f in long_f} == {"A_LONG"}
    assert {f.slug for f in empty_f} == {"A_EMPTY"}


def test_all_rules_registered():
    assert set(RULES) == {
        "missing-action-hint",
        "destructive-verb-without-destructive-hint",
        "duplicate-display-name-in-toolkit",
        "description-repeats-name",
        "description-empty",
        "description-too-long",
    }
