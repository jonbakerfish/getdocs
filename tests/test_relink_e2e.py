import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=120,
    )


def test_in_crawl_page_links_become_relative_md_paths(site, tmp_path):
    site.add("/docs/", page("Home", """
        <h1>Home</h1>
        <a href="/docs/guide/install">Install guide</a>
        <a href="https://other.com/page">External</a>"""))
    site.add("/docs/guide/install", page("Install", """
        <h1>Install</h1>
        <a href="/docs/#features">Home features</a>
        <a href="/docs/missing">Never crawled</a>"""))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr

    home = (tmp_path / "docs.md").read_text()
    assert "(docs/guide/install.md)" in home  # crawled page → relative md path
    assert "(https://other.com/page)" in home  # external stays absolute

    install = (tmp_path / "docs" / "guide" / "install.md").read_text()
    assert "(../../docs.md#features)" in install  # relative up-tree, fragment kept
    assert f"({site.url}/docs/missing)" in install  # 404'd page stays absolute
