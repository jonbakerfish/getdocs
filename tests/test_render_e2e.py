import json
import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def shell(title, hydrated_body):
    """An SPA shell: empty root + noscript plainly, content injected by JS."""
    return f"""<html><head><title>{title}</title></head><body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
    <script>document.getElementById('root').innerHTML = {json.dumps(hydrated_body)};</script>
    </body></html>"""


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=180,
    )


def manifest_of(tmp_path):
    return json.loads((tmp_path / "crawl.json").read_text())


def test_auto_mode_renders_shells_and_leaves_static_pages_alone(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/app">App</a>'))
    site.add("/docs/app", shell("App", "<main><h1>Hydrated Content</h1></main>"))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "Hydrated Content" in (tmp_path / "docs" / "app.md").read_text()
    assert site.hits["/docs/"] == 1  # static page: plain fetch only
    assert site.hits["/docs/app"] == 2  # plain fetch + render escalation


def test_auto_mode_latches_host_after_repeated_shells(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/a1">a1</a>'))
    site.add("/docs/a1", shell("A1", '<main><h1>A1</h1><a href="/docs/a2">a2</a></main>'))
    site.add("/docs/a2", shell("A2", '<main><h1>A2</h1><a href="/docs/a3">a3</a></main>'))
    site.add("/docs/a3", shell("A3", "<main><h1>A3</h1></main>"))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "# A3" in (tmp_path / "docs" / "a3.md").read_text()
    assert site.hits["/docs/a1"] == 2  # shell discovered, re-fetched rendered
    assert site.hits["/docs/a2"] == 2  # second shell — latches the host
    assert site.hits["/docs/a3"] == 1  # straight to the browser


def test_render_never_writes_shell_as_is_and_flags_it(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/app">App</a>'))
    site.add("/docs/app", shell("App", "<main><h1>Hydrated Content</h1></main>"))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--render", "never")

    assert result.returncode == 0, result.stderr
    assert site.hits["/docs/app"] == 1  # no second fetch
    assert "Hydrated Content" not in (tmp_path / "docs" / "app.md").read_text()
    assert manifest_of(tmp_path)["shells"] == [f"{site.url}/docs/app"]


def test_render_always_browser_fetches_everything_once(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/app">App</a>'))
    site.add("/docs/app", shell("App", "<main><h1>Hydrated Content</h1></main>"))

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--render", "always")

    assert result.returncode == 0, result.stderr
    assert "Hydrated Content" in (tmp_path / "docs" / "app.md").read_text()
    assert site.hits["/docs/app"] == 1  # rendered first time, no double fetch
    assert manifest_of(tmp_path)["shells"] == []
