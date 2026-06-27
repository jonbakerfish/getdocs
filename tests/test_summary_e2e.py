"""Completion summary: the agent-native Outcome report (#21).

A finished run reports what it produced — an always-on one-line summary on
stderr, and an opt-in structured object via --summary-json. Both surfaces are
rendered from the same Outcome so they cannot disagree (ADR-0007). Verified at
the subprocess CLI seam (prior art: test_crawl_e2e, test_limits_errors_e2e).
"""

import json
import subprocess
import sys
from pathlib import Path

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "basic_docs_page.html").read_text()


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=120,
    )


def test_crawl_prints_one_line_stderr_summary(site, tmp_path):
    site.add("/docs/auth", FIXTURE_HTML)
    seed = f"{site.url}/docs/auth"

    result = run_getdocs("crawl", seed, "-o", str(tmp_path), "--no-clone-source")

    assert result.returncode == 0, result.stderr
    # Names the page count and where the Pages landed.
    assert "getdocs: crawled 1 Pages" in result.stderr
    assert str(tmp_path) in result.stderr


def test_summary_json_emits_crawled_object_to_stdout(site, tmp_path):
    site.add("/docs/auth", FIXTURE_HTML)
    seed = f"{site.url}/docs/auth"

    result = run_getdocs(
        "crawl", seed, "-o", str(tmp_path), "--no-clone-source", "--summary-json"
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["outcome"] == "crawled"
    assert summary["status"] == "ok"
    assert summary["pages"] == 1
    assert summary["output_dir"] == str(tmp_path)
    assert summary["manifest"] == str(tmp_path / "crawl.json")
    assert summary["truncated"] is False


def test_jsonl_summary_emits_no_stdout_object_but_keeps_stderr_line(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/auth">Auth</a>'))
    site.add("/docs/auth", page("Auth", "<h1>Auth</h1>"))

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "--format", "jsonl",
        "--summary-json", "--no-clone-source",
    )

    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.strip().split("\n")]
    # stdout stays the page stream: Page records + the final Manifest, nothing else.
    assert records[-1]["type"] == "manifest"
    assert all(r["type"] in ("page", "manifest") for r in records)
    # The stderr line is still emitted in jsonl mode.
    assert "getdocs: crawled 2 Pages" in result.stderr


def test_truncated_crawl_reports_truncated_status(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/p0">start</a>'))
    for i in range(6):
        link = f'<a href="/docs/p{i + 1}">next</a>' if i + 1 < 6 else ""
        site.add(f"/docs/p{i}", page(f"P{i}", f"<h1>P{i}</h1>{link}"))

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path),
        "--limit", "2", "--summary-json", "--no-clone-source",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "truncated"
    assert summary["truncated"] is True
    assert "[truncated]" in result.stderr


def test_empty_crawl_reports_empty_status_and_exits_nonzero(tmp_path):
    result = run_getdocs(
        "crawl", "http://127.0.0.1:1/none", "-o", str(tmp_path),
        "--summary-json", "--no-clone-source",
    )

    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary["outcome"] == "crawled"
    assert summary["status"] == "empty"
    assert summary["pages"] == 0


def test_stderr_line_and_json_carry_the_same_facts(site, tmp_path):
    site.add("/docs/auth", FIXTURE_HTML)
    seed = f"{site.url}/docs/auth"

    result = run_getdocs(
        "crawl", seed, "-o", str(tmp_path), "--no-clone-source", "--summary-json"
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert f"crawled {summary['pages']} Pages" in result.stderr
    assert ("[truncated]" in result.stderr) == summary["truncated"]


def test_resume_run_produces_a_crawled_summary(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/p0">start</a>'))
    for i in range(4):
        link = f'<a href="/docs/p{i + 1}">next</a>' if i + 1 < 4 else ""
        site.add(f"/docs/p{i}", page(f"P{i}", f"<h1>P{i}</h1>{link}"))

    first = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path),
        "--limit", "2", "--no-clone-source",
    )
    assert first.returncode == 0, first.stderr

    second = run_getdocs("crawl", "--resume", "-o", str(tmp_path), "--summary-json")

    assert second.returncode == 0, second.stderr
    summary = json.loads(second.stdout)
    assert summary["outcome"] == "crawled"
    assert "getdocs: crawled" in second.stderr
