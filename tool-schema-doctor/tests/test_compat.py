"""Regression tests pinning the validated provider conversion behavior.

Each provider test is skipped if its SDK is not installed, so the suite runs
anywhere. The point is to pin the specific bugs the investigation found.
"""

import pytest

from tool_schema_doctor.model import ToolRecord, OK, TRANSFORMED, ERROR
from tool_schema_doctor.compat import run_one
from tool_schema_doctor import providers


def _rec(slug, params):
    return ToolRecord(slug=slug, name=slug, description="probe", input_parameters=params)


def _needs(*mods):
    for m in mods:
        pytest.importorskip(m)


# ---- fixtures: tiny hand-written schemas ----
NESTED_EXAMPLES = {
    "type": "object",
    "properties": {
        "outer": {"type": "object", "properties": {
            "inner": {"type": "string", "examples": ["x"]}}},
    },
}
TOP_LEVEL_EXAMPLES_ONLY = {
    "type": "object",
    "properties": {"q": {"type": "string", "examples": ["a", "b"]}},
    "required": ["q"],
}
FILE_UPLOADABLE = {
    "type": "object",
    "properties": {"f": {"type": "string", "file_uploadable": True}},
}
STRING_ENUM = {
    "type": "object",
    "properties": {"method": {"type": "string", "enum": ["GET", "POST", "HEAD"]}},
}
BASELINE = {
    "type": "object",
    "properties": {"owner": {"type": "string", "description": "repo owner"}},
    "required": ["owner"],
}


# ---------------- Vertex (composio_google) ----------------

def test_vertex_nested_examples_errors():
    _needs("composio_google")
    res = run_one(_rec("NESTED_EX", NESTED_EXAMPLES), "google_vertex")
    assert res.status == ERROR
    assert res.schema_path == "/properties/outer/properties/inner/examples"


def test_vertex_file_uploadable_errors():
    _needs("composio_google")
    res = run_one(_rec("FU", FILE_UPLOADABLE), "google_vertex")
    assert res.status == ERROR
    assert res.schema_path == "/properties/f/file_uploadable"


def test_vertex_top_level_examples_is_stripped_not_error():
    _needs("composio_google")
    res = run_one(_rec("TOP_EX", TOP_LEVEL_EXAMPLES_ONLY), "google_vertex")
    # top-level examples are stripped by the adapter -> no error, keyword dropped
    assert res.status in (OK, TRANSFORMED)
    assert "examples" in res.dropped_keywords


# ---------------- Gemini (composio_gemini) ----------------

def test_gemini_drops_enum():
    _needs("composio_gemini", "google.genai")
    res = run_one(_rec("ENUMTOOL", STRING_ENUM), "gemini")
    assert res.status == TRANSFORMED
    assert "enum" in res.dropped_keywords


def test_gemini_real_nested_object_failure(mock_tools):
    _needs("composio_gemini", "google.genai")
    t = mock_tools["GOOGLEDRIVE_UPDATE_PERMISSION"]
    res = run_one(ToolRecord(slug=t["slug"], name=t["name"],
                             description=t["description"],
                             input_parameters=t["input_parameters"]), "gemini")
    assert res.status == ERROR
    assert "permission" in (res.schema_path or "") + (res.message or "")


# ---------------- OpenAI strict: explain why a schema can't be strict ----------------

def test_openai_strict_reports_sdk_reason_for_free_form_object():
    _needs("composio")
    free_form = {"type": "object", "properties": {
        "emails": {"type": "array", "items": {"type": "object"}}}}
    res = run_one(_rec("FREEFORM", free_form), "openai_strict")
    assert res.status == ERROR
    # message carries path, keyword and the SDK's own detail text
    assert "emails.items" in res.message
    assert "arbitrary keys" in res.message


# ---------------- Offline mode is scoped: it must not leak into the caller ----------------

def test_offline_blocks_inside_and_restores_after():
    import socket

    real_connect, real_gai = socket.socket.connect, socket.getaddrinfo
    with providers.offline():
        with pytest.raises(RuntimeError, match="network access is blocked"):
            socket.getaddrinfo("example.com", 80)
        with providers.offline():          # nesting keeps it blocked
            pass
        with pytest.raises(RuntimeError):
            socket.getaddrinfo("example.com", 80)
    assert socket.socket.connect is real_connect
    assert socket.getaddrinfo is real_gai


def test_offline_restores_even_if_the_run_raises():
    import socket

    real_gai = socket.getaddrinfo
    with pytest.raises(ValueError):
        with providers.offline():
            raise ValueError("boom")
    assert socket.getaddrinfo is real_gai


def test_run_compatibility_does_not_leave_network_blocked():
    import socket
    from tool_schema_doctor.compat import run_compatibility

    real_gai = socket.getaddrinfo
    run_compatibility([_rec("X", BASELINE)], ["openai_strict"])
    assert socket.getaddrinfo is real_gai


# ---------------- Error messages are evidence: never silently cut ----------------

def test_clip_message_keeps_short_and_labels_long():
    from tool_schema_doctor.compat import clip_message

    assert clip_message("short") == "short"
    clipped = clip_message("x" * 50, limit=10)
    assert clipped == "x" * 10 + " …[truncated 40 chars]"


def test_long_strict_message_is_reported_in_full(mock_tools):
    # Real tool whose strict-mode explanation (11 unsupported paths, ~1,355 chars)
    # used to be cut at 400 chars, mid-word.
    _needs("composio")
    t = mock_tools["GITHUB_UPDATE_BRANCH_PROTECTION"]
    res = run_one(ToolRecord(slug=t["slug"], name=t["name"], description=t["description"],
                             input_parameters=t["input_parameters"]), "openai_strict")
    assert res.status == ERROR
    assert len(res.message) > 400
    assert "truncated" not in res.message
    assert len(res.message.replace("strict-unsupported: ", "").split("; ")) == 11


# ---------------- Baseline passes everywhere available ----------------

@pytest.mark.parametrize("pid", providers.PROVIDER_IDS)
def test_baseline_no_error(pid):
    avail = providers.available_providers()
    if not avail.get(pid):
        pytest.skip(f"{pid} SDK not installed")
    res = run_one(_rec("BASELINE_TOOL", BASELINE), pid)
    assert res.status in (OK, TRANSFORMED), f"{pid} unexpectedly {res.status}: {res.message}"


# ---------------- Optional-dependency handling ----------------

def test_unavailable_not_counted_as_error(monkeypatch):
    # Simulate a missing SDK: convert() raises ImportError -> status unavailable.
    import tool_schema_doctor.compat as compat

    def boom(provider_id, slug, description, params):
        raise ImportError("no module named composio_fake")

    monkeypatch.setattr(compat.providers, "convert", boom)
    res = run_one(_rec("X", BASELINE), "openai")
    assert res.status == "unavailable"
    assert res.status != ERROR
