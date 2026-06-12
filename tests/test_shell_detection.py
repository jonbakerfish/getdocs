from pathlib import Path

from getdocs.extract import is_shell

FIXTURES = Path(__file__).parent / "fixtures"


def test_unhydrated_spa_shell_is_detected():
    assert is_shell((FIXTURES / "spa_shell.html").read_text()) is True


def test_real_content_pages_are_not_shells():
    for fixture in ("basic_docs_page.html", "docusaurus.html", "mkdocs.html", "sphinx.html"):
        assert is_shell((FIXTURES / fixture).read_text()) is False, fixture


def test_empty_root_div_without_noscript_is_a_shell():
    html = """<html><head><title>App</title></head><body>
    <div id="__next"></div><script src="/app.js"></script></body></html>"""

    assert is_shell(html) is True


def test_short_static_page_without_scripts_is_not_a_shell():
    html = """<html><head><title>Hi</title></head><body><p>Tiny but real.</p></body></html>"""

    assert is_shell(html) is False
