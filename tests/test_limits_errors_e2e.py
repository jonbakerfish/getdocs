import json
import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=120,
    )


def build_chain_site(site, n=6):
    """/docs/ → /docs/p0 → /docs/p1 → … — a chain so page order is deterministic.

    Crawl with seed /docs/ so the whole chain is in Scope; total pages = n + 1.
    """
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/p0">start</a>'))
    for i in range(n):
        link = f'<a href="/docs/p{i + 1}">next</a>' if i + 1 < n else ""
        site.add(f"/docs/p{i}", page(f"P{i}", f"<h1>P{i}</h1>{link}"))


def manifest_of(tmp_path):
    return json.loads((tmp_path / "crawl.json").read_text())


def test_limit_caps_pages_and_flags_truncation(site, tmp_path):
    build_chain_site(site, n=6)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--limit", "2")

    assert result.returncode == 0, result.stderr
    assert len(list(tmp_path.rglob("*.md"))) == 2
    manifest = manifest_of(tmp_path)
    assert manifest["page_count"] == 2
    assert manifest["truncated"] is True


def test_crawl_that_fits_within_limit_is_not_truncated(site, tmp_path):
    build_chain_site(site, n=2)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--limit", "3")

    assert result.returncode == 0, result.stderr
    assert manifest_of(tmp_path)["truncated"] is False


def test_404_is_recorded_not_retried_and_crawl_succeeds(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/gone">Gone</a>'))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr  # page errors are not fatal
    errors = manifest_of(tmp_path)["errors"]
    assert len(errors) == 1
    assert errors[0]["url"] == f"{site.url}/docs/gone"
    assert errors[0]["status"] == 404
    assert site.hits["/docs/gone"] == 1  # not retried


def test_transient_5xx_is_retried_to_success(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/flaky">Flaky</a>'))
    site.add_flaky("/docs/flaky", page("Flaky", "<h1>Recovered</h1>"), fail_times=1)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "docs" / "flaky.md").exists()
    assert site.hits["/docs/flaky"] == 2  # failed once, retried once
    assert manifest_of(tmp_path)["errors"] == []


def test_persistent_5xx_lands_in_errors_after_retries(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/broken">Broken</a>'))
    site.add_flaky("/docs/broken", page("never", ""), fail_times=99)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    errors = manifest_of(tmp_path)["errors"]
    assert len(errors) == 1
    assert errors[0]["status"] == 500
    assert site.hits["/docs/broken"] == 3  # initial + 2 retries


def test_progress_goes_to_stderr_and_stdout_stays_clean(site, tmp_path):
    build_chain_site(site, n=2)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0
    assert "[getdocs]" in result.stderr
    assert "pages=" in result.stderr
    assert result.stdout == ""
