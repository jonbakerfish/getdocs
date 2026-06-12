"""Extract: HTML in, (title, markdown) out.

Tracer-bullet version: semantic content containers with whole-body fallback.
The full selector-first pipeline (docs-generator containers, --selector,
trafilatura fallback) arrives with the extraction-quality slice.
"""

from dataclasses import dataclass

from bs4 import BeautifulSoup
from markdownify import markdownify


@dataclass(frozen=True)
class ExtractedPage:
    title: str
    markdown: str


_CONTENT_SELECTORS = ["main", "article", "[role=main]"]


def extract_page(html: str, url: str) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else url

    root = None
    for selector in _CONTENT_SELECTORS:
        root = soup.select_one(selector)
        if root is not None:
            break
    if root is None:
        root = soup.body or soup

    markdown = markdownify(str(root), heading_style="ATX").strip()
    return ExtractedPage(title=title, markdown=markdown)
