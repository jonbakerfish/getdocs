"""Extract: HTML in, (title, markdown, canonical) out.

Selector-first pipeline: a user-supplied selector wins, then the known
content containers of common docs generators, then semantic candidates.
Readability extraction (trafilatura) is a last resort for pages with no
recognizable content root — docs sites are structured, so exploiting
that structure beats statistical extraction (and never eats code blocks).
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter, markdownify


@dataclass(frozen=True)
class ExtractedPage:
    title: str
    markdown: str
    canonical: str | None = None
    assets: tuple[str, ...] = ()  # absolute URLs of referenced images/documents


_DOC_EXTENSIONS = (
    ".pdf", ".zip", ".tar.gz", ".tgz", ".7z", ".dmg", ".pkg", ".msi", ".exe", ".whl",
)


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


# Known icon shapes (Material Design icon path prefixes, as emitted by
# mkdocs-material twemoji spans). Inline SVGs carry no text, so without
# this, checkmark columns in comparison tables extract as empty cells.
_SVG_GLYPHS = {
    "M21 7 9 19l-5.5-5.5": "✓",  # mdi-check
    "M9 20.42 2.79 14.21": "✓",  # mdi-check-bold
    "M19 6.41 17.59 5 12 10.59": "✗",  # mdi-close
    "M20 6.91 17.09 4 12 9.09": "✗",  # mdi-close-thick
}


def _svg_to_text(root) -> None:
    for svg in root.find_all("svg"):
        label = svg.get("aria-label")
        if not label:
            title = svg.find("title")
            label = title.get_text(strip=True) if title else None
        if not label:
            path = svg.find("path")
            d = (path.get("d") or "") if path else ""
            label = next((g for prefix, g in _SVG_GLYPHS.items() if d.startswith(prefix)), None)
        if label:
            svg.replace_with(label)


def _absolutize_urls(root, page_url: str) -> list[str]:
    """Rewrite hrefs/srcs absolute against the page URL — relative values
    would point at nothing in the output tree (hotlink default, ADR-0005).
    Returns the Asset URLs found: images, then document downloads."""
    images, documents = [], []
    for tag in root.find_all(href=True):
        tag["href"] = urljoin(page_url, tag["href"])
        if tag.name == "a" and urlsplit(tag["href"]).path.lower().endswith(_DOC_EXTENSIONS):
            documents.append(tag["href"])
    for tag in root.find_all(src=True):
        tag["src"] = urljoin(page_url, tag["src"])
        if tag.name == "img":
            images.append(tag["src"])
    for tag in root.find_all(srcset=True):
        tag["srcset"] = ", ".join(
            " ".join([urljoin(page_url, part.strip().split()[0]), *part.strip().split()[1:]])
            for part in tag["srcset"].split(",")
            if part.strip()
        )
    return images + documents


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


_ROOT_DIV_IDS = ["root", "app", "__next", "___gatsby", "__nuxt"]


def is_shell(html: str) -> bool:
    """True when a response is an unhydrated client-side app frame rather
    than real content — the signal that triggers render escalation."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if body is None:
        return False

    noscript_warning = any(
        "javascript" in ns.get_text().lower() for ns in body.find_all("noscript")
    )
    has_scripts = bool(soup.find("script"))

    for tag in body.find_all(["script", "noscript", "style", "template"]):
        tag.decompose()
    text = body.get_text(strip=True)
    if len(text) > 200:
        return False  # plenty of real text — not a shell, whatever else it has

    empty_root = any(
        not div.get_text(strip=True) for div in body.find_all("div", id=_ROOT_DIV_IDS)
    )
    return empty_root or noscript_warning or (has_scripts and len(text) < 30)


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
    assets: list[str] = []
    if root is not None:
        _strip_noise(root)
        _svg_to_text(root)
        assets = _absolutize_urls(root, url)
        markdown = _converter.convert(str(root)).strip()
    else:
        markdown = (_readability_markdown(html) or markdownify(str(soup.body or soup))).strip()

    return ExtractedPage(
        title=title, markdown=markdown, canonical=canonical, assets=tuple(assets)
    )
