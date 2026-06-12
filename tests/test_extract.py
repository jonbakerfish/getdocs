from pathlib import Path

from getdocs.extract import extract_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_title_and_main_content_as_markdown():
    html = (FIXTURES / "basic_docs_page.html").read_text()

    page = extract_page(html, url="https://example.com/docs/auth")

    assert page.title == "Authentication — Example Docs"
    assert "# Authentication" in page.markdown
    assert "bearer token" in page.markdown
    assert "Blog" not in page.markdown  # nav chrome stripped
    assert "Copyright" not in page.markdown  # footer stripped
    assert page.canonical is None


def test_rel_canonical_is_recorded():
    html = """<html><head><title>V2 Auth</title>
    <link rel="canonical" href="https://example.com/docs/latest/auth">
    </head><body><main><h1>Auth</h1></main></body></html>"""

    page = extract_page(html, url="https://example.com/docs/v2/auth")

    assert page.canonical == "https://example.com/docs/latest/auth"
