import json
import subprocess
import sys


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=120,
    )


def nav_page(site, path, title, body_links, prev=None, next=None):
    sidebar = """<aside><nav><ul>
      <li><a href="/docs/">Welcome</a></li>
      <li><a href="/docs/setup">Getting set up</a>
        <ul><li><a href="/docs/setup/advanced">Advanced setup</a></li></ul>
      </li>
      <li><a href="/docs/api">API reference</a></li>
    </ul></nav></aside>"""
    links = "".join(f'<a href="{href}">{href}</a>' for href in body_links)
    rels = ""
    if prev:
        rels += f'<a rel="prev" href="{prev}">prev</a>'
    if next:
        rels += f'<a rel="next" href="{next}">next</a>'
    site.add(path, f"""<html><head><title>{title}</title></head><body>
    {sidebar}<main><h1>{title}</h1>{links}</main>{rels}</body></html>""")


def build_site(site):
    # Body links list pages in anti-nav order, so crawl order disagrees
    # with the sidebar; prev/next chains define the true reading order.
    nav_page(site, "/docs/", "Welcome",
             ["/docs/api", "/docs/setup/advanced", "/docs/setup"],
             next="/docs/setup")
    nav_page(site, "/docs/setup", "Getting set up", [],
             prev="/docs/", next="/docs/setup/advanced")
    nav_page(site, "/docs/setup/advanced", "Advanced setup", [],
             prev="/docs/setup", next="/docs/api")
    nav_page(site, "/docs/api", "API reference", [], prev="/docs/setup/advanced")


def test_manifest_carries_nav_tree_and_chain_reading_order(site, tmp_path):
    build_site(site)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "crawl.json").read_text())

    nav = manifest["nav"]
    assert [n["title"] for n in nav] == ["Welcome", "Getting set up", "API reference"]
    assert nav[1]["children"][0]["title"] == "Advanced setup"
    assert nav[1]["url"] == f"{site.url}/docs/setup"

    assert manifest["reading_order"] == [
        f"{site.url}/docs/",
        f"{site.url}/docs/setup",
        f"{site.url}/docs/setup/advanced",
        f"{site.url}/docs/api",
    ]


def test_pages_without_any_nav_yield_crawl_order(site, tmp_path):
    page = "<html><head><title>{t}</title></head><body><main><h1>{t}</h1>{links}</main></body></html>"
    site.add("/docs/", page.format(t="Home", links='<a href="/docs/a">a</a>'))
    site.add("/docs/a", page.format(t="A", links=""))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "crawl.json").read_text())
    assert manifest["nav"] == []
    assert manifest["reading_order"] == [f"{site.url}/docs/", f"{site.url}/docs/a"]
