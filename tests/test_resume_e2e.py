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


def build_chain_site(site, n=4):
    """/docs/ → p0 → p1 → … chain, plus a 404 link off the root."""
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/p0">start</a><a href="/docs/gone">gone</a>'))
    for i in range(n):
        link = f'<a href="/docs/p{i + 1}">next</a>' if i + 1 < n else ""
        site.add(f"/docs/p{i}", page(f"P{i}", f"<h1>P{i}</h1>{link}"))


ALL_FILES = ["docs.md", "docs/p0.md", "docs/p1.md", "docs/p2.md", "docs/p3.md"]


def md_files(out_dir):
    return sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.md"))


def manifest_of(tmp_path):
    return json.loads((tmp_path / "crawl.json").read_text())


def test_resume_completes_interrupted_crawl_without_refetching(site, tmp_path):
    build_chain_site(site)

    first = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--limit", "2")
    assert first.returncode == 0, first.stderr
    assert len(md_files(tmp_path)) == 2
    assert manifest_of(tmp_path)["truncated"] is True
    hits_before = dict(site.hits)

    second = run_getdocs("crawl", "--resume", "-o", str(tmp_path))
    assert second.returncode == 0, second.stderr

    assert md_files(tmp_path) == ALL_FILES  # same tree as an uninterrupted Crawl
    manifest = manifest_of(tmp_path)
    assert manifest["page_count"] == 5
    assert manifest["truncated"] is False  # the resumed Crawl finished everything
    # errors aggregate across both runs without duplication
    assert [e["status"] for e in manifest["errors"]] == [404]
    # Pages written in run 1 are not re-fetched in run 2
    for path in ("/docs/", "/docs/p0"):
        assert site.hits[path] == hits_before[path]
    assert site.hits["/docs/gone"] == 1  # errored URLs are not re-fetched either


def test_resume_without_state_fails_clearly(tmp_path):
    result = run_getdocs("crawl", "--resume", "-o", str(tmp_path))

    assert result.returncode != 0
    assert "no crawl state" in result.stderr.lower()


def test_fresh_run_on_dirty_dir_states_it_starts_over(site, tmp_path):
    build_chain_site(site)
    run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--limit", "2")

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "starting over" in result.stderr.lower()
    assert md_files(tmp_path) == ALL_FILES
    assert site.hits["/docs/"] == 2  # genuinely re-crawled from scratch
