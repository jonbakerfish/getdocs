import json
import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def build_docs_site(site):
    site.add("/docs/", page("Docs Home", """
        <h1>Docs</h1>
        <a href="/docs/auth">Auth</a>
        <a href="/docs/auth#token">Auth fragment dup</a>
        <a href="/docs/auth?utm_source=nav">Auth tracking dup</a>
        <a href="/docs/guide/intro">Guide</a>
        <a href="/docs/old">Old auth</a>
        <a href="/blog/post">Blog (out of scope)</a>
    """))
    site.add("/docs/auth", f"""<html><head><title>Auth</title>
        <link rel="canonical" href="{site.url}/docs/latest/auth">
        </head><body><main><h1>Auth</h1><a href="/docs/">Home</a></main></body></html>""")
    site.add("/docs/guide/intro", page("Intro", '<h1>Intro</h1><a href="advanced">Advanced</a>'))
    site.add("/docs/guide/advanced", page("Advanced", "<h1>Advanced</h1>"))
    site.add_redirect("/docs/old", "/docs/auth")
    site.add("/blog/post", page("Blog", "<h1>Should never be crawled</h1>"))
    site.add("/docs/latest/auth", page("Latest Auth", "<h1>Canonical target — not followed</h1>"))


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args],
        capture_output=True, text=True, timeout=120,
    )


def md_files(out_dir):
    return sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.md"))


def test_crawl_follows_in_scope_links_and_dedupes(site, tmp_path):
    build_docs_site(site)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert md_files(tmp_path) == [
        "docs.md",
        "docs/auth.md",
        "docs/guide/advanced.md",
        "docs/guide/intro.md",
    ]
    manifest = json.loads((tmp_path / "crawl.json").read_text())
    assert manifest["page_count"] == 4

    auth = (tmp_path / "docs" / "auth.md").read_text()
    assert f"canonical: {site.url}/docs/latest/auth" in auth  # recorded (ADR-0003)


def test_depth_limits_link_hops(site, tmp_path):
    build_docs_site(site)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--depth", "1")

    assert result.returncode == 0, result.stderr
    files = md_files(tmp_path)
    assert "docs/guide/intro.md" in files  # one hop from seed
    assert "docs/guide/advanced.md" not in files  # two hops
