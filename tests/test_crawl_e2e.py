import json
import subprocess
import sys
from pathlib import Path

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "basic_docs_page.html").read_text()


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args],
        capture_output=True, text=True, timeout=120,
    )


def test_single_page_crawl_writes_page_and_manifest(site, tmp_path):
    site.add("/docs/auth", FIXTURE_HTML)
    seed = f"{site.url}/docs/auth"

    result = run_getdocs("crawl", seed, "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    page_file = tmp_path / "docs" / "auth.md"
    assert page_file.exists()
    text = page_file.read_text()
    assert text.startswith("---\n")
    assert f"url: {seed}" in text
    assert "# Authentication" in text

    manifest = json.loads((tmp_path / "crawl.json").read_text())
    assert manifest["seeds"] == [seed]
    assert manifest["page_count"] == 1


def test_unreachable_seed_exits_nonzero(tmp_path):
    result = run_getdocs("crawl", "http://127.0.0.1:1/none", "-o", str(tmp_path))

    assert result.returncode != 0
