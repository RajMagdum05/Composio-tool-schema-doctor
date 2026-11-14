import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def wtmp():
    """A writable, project-local temp dir.

    The machine's global pytest temp root is permission-locked on this host,
    so `tmp_path` can fail; this fixture sidesteps it entirely.
    """
    base = Path(__file__).resolve().parent / ".wtmp"
    base.mkdir(parents=True, exist_ok=True)
    d = base / f"t{id(object())}"
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# Locate the upstream mock corpus relative to this repo layout (optional).
_MOCK = Path(__file__).resolve().parents[2] / "composio-upstream" / "ts" / "packages" / "cli" / "test" / "__mocks__" / "tools.json"


@pytest.fixture(scope="session")
def mock_tools():
    if not _MOCK.exists():
        pytest.skip(f"upstream mock corpus not found at {_MOCK}")
    return {t["slug"]: t for t in json.loads(_MOCK.read_text(encoding="utf-8"))}
