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


def crawl_jsonl(site, *extra):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/auth">Auth</a>'))
    site.add("/docs/auth", page("Auth", "<h1>Auth</h1>"))

    result = run_getdocs("crawl", f"{site.url}/docs/", "--format", "jsonl", *extra)

    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.strip().split("\n")]


def test_jsonl_streams_typed_records_to_stdout(site):
    records = crawl_jsonl(site)

    pages = [r for r in records if r["type"] == "page"]
    assert {p["title"] for p in pages} == {"Home", "Auth"}
    assert all("html" not in p for p in pages)  # omitted by default

    manifest = records[-1]
    assert manifest["type"] == "manifest"
    assert manifest["page_count"] == 2


def test_keep_html_includes_raw_html_in_records(site):
    records = crawl_jsonl(site, "--keep-html")

    pages = [r for r in records if r["type"] == "page"]
    assert all("<html>" in p["html"] for p in pages)
