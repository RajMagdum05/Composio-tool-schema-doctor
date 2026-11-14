"""The static site (what gets hosted on Netlify/Vercel) must match the Streamlit dashboard
and must not leak anything. Builds into a temp folder, so the committed site/ is untouched."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
EVIDENCE = HERE / "out" / "evidence" / "evidence.json"

pytestmark = pytest.mark.skipif(not EVIDENCE.exists(), reason="run make_evidence.py first")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    # tmp_path can be unreliable on this host (see conftest.wtmp), so build next to the tests
    out = HERE / "tests" / ".wtmp" / "static-site"
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, str(HERE / "build_static.py")], capture_output=True, text=True,
                          env={**os.environ, "TSD_SITE_DIR": str(out), "PYTHONIOENCODING": "utf-8"}, timeout=300)
    assert proc.returncode == 0, proc.stderr[-800:]
    return out


def _page(site) -> str:
    return (site / "index.html").read_text(encoding="utf-8")


def test_builds_a_self_contained_page(site):
    page = _page(site)
    assert page.startswith("<!doctype html>") and "</html>" in page
    # only the stylesheet for the two fonts is fetched from elsewhere; everything else is inline
    hosts = set(re.findall(r"""(?:src|href)=["'](https?://[^/"']+)""", page)) - {"https://github.com"}
    assert hosts == set(), hosts
    assert page.count("fonts.googleapis.com") == 1


def test_matches_the_streamlit_dashboard(site):
    st_testing = pytest.importorskip("streamlit.testing.v1")
    page = _page(site)
    at = st_testing.AppTest.from_file(str(HERE / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception
    md = "\n".join(m.value for m in at.markdown)

    static_nums = re.findall(r"<div class='stat-num'>([^<]*)</div>", page)
    app_nums = re.findall(r"<div class='stat-num'>([^<]*)</div>", md)
    assert static_nums == app_nums and len(static_nums) == 4

    static_titles = [re.sub(r"&#x27;", "'", t) for t in re.findall(r"<h3>\d\. (.*?)</h3>", page)]
    app_titles = [re.sub(r"^#### \d\. ", "", m.value) for m in at.markdown if m.value.startswith("#### ")]
    assert static_titles == app_titles and len(static_titles) == 5


def test_every_evidence_link_resolves_and_the_lookup_data_is_complete(site):
    page = _page(site)
    for rel in set(re.findall(r"href='(evidence/cli/[a-z]+\.txt)'", page)):
        assert (site / rel).is_file(), rel
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1)
                      .replace("<\\/", "</"))
    assert len(data) == 930
    assert all(len(rows) == 6 for rows in data.values())          # one row per adapter
    # the long strict-mode message is complete here too: 11 unsupported paths
    full = next(d for p, o, d, _ in data["GITHUB_UPDATE_BRANCH_PROTECTION"] if p == "openai_strict")
    assert len(full.split("strict-unsupported: ")[1].split("; ")) == 11


def test_nothing_personal_or_secret_is_published(site):
    blob = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in site.rglob("*") if f.is_file())
    for needle in ("rajma", "RajOMEN", "C:\\Users", "C:/Users", "R:\\Internship", "R:/Internship"):
        assert needle.lower() not in blob.lower(), needle
    assert not re.search(r"gsk_[A-Za-z0-9]{20,}", blob)
    assert "Not affiliated with or endorsed by Composio" in blob
