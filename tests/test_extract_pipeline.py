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


def test_no_container_falls_back_to_readability_not_empty():
    html = """<html><head><title>Plain page</title></head><body>
    <div><div><p>This paragraph is the real content of an unstructured page,
    long enough that a readability extractor should find and keep it as the
    main body text of the document.</p></div></div>
    </body></html>"""

    page = extract_page(html, url="https://example.com/plain")

    assert "real content" in page.markdown
