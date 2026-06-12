"""Extract: HTML in, (title, markdown, canonical) out.

Selector-first pipeline: a user-supplied selector wins, then the known
content containers of common docs generators, then semantic candidates.
Readability extraction (trafilatura) is a last resort for pages with no
recognizable content root — docs sites are structured, so exploiting
that structure beats statistical extraction (and never eats code blocks).
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter, markdownify


@dataclass(frozen=True)
class ExtractedPage:
    title: str
    markdown: str
    canonical: str | None = None


_GENERATOR_SELECTORS = [
    "div.theme-doc-markdown",      # Docusaurus
    "article.md-content__inner",   # MkDocs Material
    'div.body[role="main"]',       # Sphinx
    "#content-area",               # Mintlify
]
_SEMANTIC_SELECTORS = ["main", "article", '[role="main"]']

_NOISE_TAGS = ("nav", "aside", "header", "footer", "script", "style", "noscript")
_NOISE_CLASS_RE = re.compile(r"breadcrumb|table-of-contents|(^|[-_])toc($|[-_])")


def _code_language(el) -> str:
    """Language hint for a <pre> block: language-x on it or its <code>
    children, or Sphinx-style highlight-x on an ancestor."""
    candidates = [el, *el.find_all("code"), *el.parents]
    for node in candidates:
        for cls in node.get("class") or []:
            if cls.startswith("language-"):
                return cls.removeprefix("language-")
            if cls.startswith("highlight-"):
                lang = cls.removeprefix("highlight-")
                if lang not in ("default", "notranslate"):
                    return lang
    return ""


_converter = MarkdownConverter(heading_style="ATX", code_language_callback=_code_language)


def _strip_noise(root) -> None:
    for tag in root.find_all(_NOISE_TAGS):
        tag.decompose()
    doomed = [
        el
        for el in root.find_all(True)
        if any(_NOISE_CLASS_RE.search(cls) for cls in el.get("class") or [])
    ]
    for el in doomed:
        el.decompose()


def _find_content_root(soup, selector: str | None):
    if selector:
        root = soup.select_one(selector)
        if root is not None:
            return root
    for sel in [*_GENERATOR_SELECTORS, *_SEMANTIC_SELECTORS]:
        root = soup.select_one(sel)
        if root is not None:
            return root
    return None


def _readability_markdown(html: str) -> str | None:
    import trafilatura

    return trafilatura.extract(html, output_format="markdown", include_tables=True)


def extract_page(html: str, url: str, selector: str | None = None) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else None
    if not title:
        og_title = soup.find("meta", property="og:title")
        title = og_title.get("content") if og_title else None
    title = title or url

    canonical_link = soup.find("link", rel="canonical")
    canonical = canonical_link.get("href") if canonical_link else None

    root = _find_content_root(soup, selector)
    if root is not None:
        _strip_noise(root)
        markdown = _converter.convert(str(root)).strip()
    else:
        markdown = (_readability_markdown(html) or markdownify(str(soup.body or soup))).strip()

    return ExtractedPage(title=title, markdown=markdown, canonical=canonical)
