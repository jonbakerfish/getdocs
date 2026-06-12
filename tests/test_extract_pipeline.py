from pathlib import Path

import pytest

from getdocs.extract import extract_page

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text()


GENERATOR_CASES = [
    # (fixture, expected heading, expected code snippet with fence, chrome that must be absent)
    ("docusaurus.html", "# Installation", "```bash\npip install mylib", ["Blog", "On this page", "Copyright"]),
    ("mkdocs.html", "# Configuration", "```yaml\nsite_name: Demo", ["Table of contents", "Made with Material"]),
    ("sphinx.html", "# API Reference", "```python\nimport mylib", ["Navigation", "Created using Sphinx"]),
    ("gitbook.html", "# Getting Started", "```javascript\nconst client", ["Pricing", "Powered by GitBook"]),
    ("mintlify.html", "# Quickstart", "```python\nfrom mylib import Client", ["Powered by Mintlify"]),
]


@pytest.mark.parametrize("fixture,heading,code,absent", GENERATOR_CASES)
def test_docs_generators_extract_clean_markdown(fixture, heading, code, absent):
    page = extract_page(load(fixture), url="https://example.com/docs/x")

    assert heading in page.markdown
    assert code in page.markdown  # fenced with language hint
    for chrome in absent:
        assert chrome not in page.markdown, f"{chrome!r} leaked into markdown"


def test_tables_survive_as_markdown_tables():
    page = extract_page(load("docusaurus.html"), url="https://example.com/docs/install")

    assert "| OS | Supported |" in page.markdown
    assert "| macOS | yes |" in page.markdown


def test_user_selector_overrides_all_heuristics():
    html = """<html><head><title>T</title></head><body>
    <div class="theme-doc-markdown"><h1>Generator pick</h1></div>
    <main><h1>Semantic pick</h1></main>
    <div id="special"><h1>User pick</h1></div>
    </body></html>"""

    page = extract_page(html, url="https://example.com/x", selector="#special")

    assert "# User pick" in page.markdown
    assert "Generator pick" not in page.markdown


def test_generator_container_beats_semantic_main():
    html = """<html><head><title>T</title></head><body>
    <main><h1>Semantic pick</h1>
    <div class="theme-doc-markdown"><h1>Generator pick</h1></div>
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/x")

    assert "# Generator pick" in page.markdown
    assert "Semantic pick" not in page.markdown


def test_icon_svgs_in_table_cells_become_text_glyphs():
    check = '<span class="twemoji"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21 7 9 19l-5.5-5.5 1.41-1.41L9 16.17 19.59 5.59 21 7Z"/></svg></span>'
    cross = '<span class="twemoji"><svg viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41Z"/></svg></span>'
    html = f"""<html><head><title>Chains</title></head><body><main>
    <table><thead><tr><th>Chain</th><th>Hands only</th><th>Sidedness</th></tr></thead>
    <tbody><tr><td><code>Hand</code></td><td>{check}</td><td>{cross}</td></tr></tbody></table>
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/docs/skeletons")

    assert "| `Hand` | ✓ | ✗ |" in page.markdown


def test_svg_with_accessible_label_uses_it():
    html = """<html><head><title>T</title></head><body><main>
    <p>Status: <svg aria-label="supported" viewBox="0 0 24 24"><path d="M1 1"/></svg></p>
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/x")

    assert "Status: supported" in page.markdown


def test_links_and_media_urls_are_absolutized_against_the_page_url():
    html = """<html><head><title>T</title></head><body><main>
    <p><a href="../intro">relative</a>
    <a href="/docs/other">root-relative</a>
    <a href="https://other.com/x">absolute</a>
    <a href="mailto:hi@example.com">mail</a></p>
    <img src="../img/setup.png" alt="setup">
    <img src="//cdn.example.net/logo.svg" alt="logo">
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/docs/guide/install")

    assert "(https://example.com/docs/intro)" in page.markdown
    assert "(https://example.com/docs/other)" in page.markdown
    assert "(https://other.com/x)" in page.markdown
    assert "(mailto:hi@example.com)" in page.markdown
    assert "(https://example.com/docs/img/setup.png)" in page.markdown
    assert "(https://cdn.example.net/logo.svg)" in page.markdown


def test_srcset_candidates_are_absolutized():
    html = """<html><head><title>T</title></head><body><main>
    <img src="a.png" srcset="a.png 1x, big/a2.png 2x" alt="pic">
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/docs/page")

    assert "https://example.com/docs/a.png" in page.markdown


def test_images_and_document_links_are_reported_as_assets():
    html = """<html><head><title>T</title></head><body><main>
    <img src="../img/setup.png" alt="setup">
    <img src="https://cdn.example.net/logo.svg" alt="logo">
    <a href="/files/datasheet.pdf">Datasheet</a>
    <a href="/files/firmware.zip">Firmware</a>
    <a href="/docs/other">A normal page link</a>
    </main></body></html>"""

    page = extract_page(html, url="https://example.com/docs/guide/install")

    assert page.assets == (
        "https://example.com/docs/img/setup.png",
        "https://cdn.example.net/logo.svg",
        "https://example.com/files/datasheet.pdf",
        "https://example.com/files/firmware.zip",
    )


def test_no_container_falls_back_to_readability_not_empty():
    html = """<html><head><title>Plain page</title></head><body>
    <div><div><p>This paragraph is the real content of an unstructured page,
    long enough that a readability extractor should find and keep it as the
    main body text of the document.</p></div></div>
    </body></html>"""

    page = extract_page(html, url="https://example.com/plain")

    assert "real content" in page.markdown
