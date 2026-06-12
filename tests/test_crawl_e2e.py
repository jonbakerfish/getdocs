import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "basic_docs_page.html").read_bytes()


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/docs/auth":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(FIXTURE_HTML)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


@pytest.fixture
def fixture_site():
    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args],
        capture_output=True, text=True, timeout=120,
    )


def test_single_page_crawl_writes_page_and_manifest(fixture_site, tmp_path):
    seed = f"{fixture_site}/docs/auth"

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
