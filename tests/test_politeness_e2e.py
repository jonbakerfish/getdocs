import json
import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args],
        capture_output=True, text=True, timeout=120,
    )


def build_robots_site(site):
    site.add("/robots.txt", "User-agent: *\nDisallow: /docs/private\n")
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/private">Private</a><a href="/docs/open">Open</a>'))
    site.add("/docs/private", page("Private", "<h1>Should be skipped</h1>"))
    site.add("/docs/open", page("Open", "<h1>Open</h1>"))


def manifest_of(tmp_path):
    return json.loads((tmp_path / "crawl.json").read_text())


def test_robots_disallowed_page_is_skipped_not_errored(site, tmp_path):
    build_robots_site(site)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--delay", "0")

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "docs" / "private.md").exists()
    assert (tmp_path / "docs" / "open.md").exists()
    assert site.hits.get("/docs/private", 0) == 0  # never fetched

    manifest = manifest_of(tmp_path)
    assert manifest["errors"] == []
    assert [s["url"] for s in manifest["skipped"]] == [f"{site.url}/docs/private"]


def test_ignore_robots_fetches_disallowed_page(site, tmp_path):
    build_robots_site(site)

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--delay", "0", "--ignore-robots"
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "docs" / "private.md").exists()
    assert manifest_of(tmp_path)["skipped"] == []


def test_429_retry_honors_retry_after_delay(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/limited">Limited</a>'))
    site.add_flaky(
        "/docs/limited", page("Limited", "<h1>Recovered</h1>"),
        fail_times=1, status=429, headers={"Retry-After": "1"},
    )

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--delay", "0")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "docs" / "limited.md").exists()  # eventually succeeded
    times = site.hit_times["/docs/limited"]
    assert len(times) == 2
    assert times[1] - times[0] >= 0.9  # no sooner than Retry-After
