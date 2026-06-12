#!/usr/bin/env python
"""Serve a getdocs crawl output directory with MkDocs.

The crawl output is already MkDocs-friendly: a tree of .md files whose YAML
frontmatter (url, title, …) MkDocs reads as page meta. This script generates
a mkdocs.yml pointing at the crawl directory — with an explicit nav that
mirrors the original site's URL hierarchy (sections from path segments, page
labels from crawled titles, ordered by crawl order) — adds a homepage if the
crawl didn't produce one, and runs `mkdocs serve` (or `mkdocs build`).

Usage:
    getdocs crawl https://example.com/docs -o ./out
    python scripts/serve_mkdocs.py ./out
    python scripts/serve_mkdocs.py ./out --theme readthedocs --port 9000
    python scripts/serve_mkdocs.py ./out --build site/   # static build instead

Requires: pip install mkdocs mkdocs-material
(material is the default theme when installed; plain mkdocs otherwise)
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit

import yaml


def site_name_for(crawl_dir: Path) -> str:
    manifest = crawl_dir / "crawl.json"
    if manifest.exists():
        seeds = json.loads(manifest.read_text()).get("seeds") or []
        if seeds:
            return urlsplit(seeds[0]).netloc or "getdocs crawl"
    return "getdocs crawl"


def read_frontmatter(md_file: Path) -> dict:
    text = md_file.read_text(errors="replace")
    if not text.startswith("---\n"):
        return {}
    frontmatter, _, _ = text[4:].partition("\n---\n")
    try:
        return yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return {}


def crawled_pages(crawl_dir: Path) -> list[dict]:
    """Every crawled page with its relative path, title, and crawl order."""
    pages = []
    for md_file in crawl_dir.rglob("*.md"):
        rel = md_file.relative_to(crawl_dir).as_posix()
        if rel.startswith("."):
            continue
        meta = read_frontmatter(md_file)
        pages.append({
            "path": rel,
            "title": meta.get("title") or md_file.stem,
            # str(): YAML may parse the timestamp into a datetime; "~" sorts
            # pages without one after everything else.
            "crawled_at": str(meta.get("crawled_at") or "~"),
        })
    # Crawl order approximates the original site's nav order: links are
    # discovered in the order they appear on each page.
    pages.sort(key=lambda p: (p["crawled_at"], p["path"]))
    return pages


def build_nav(pages: list[dict], has_homepage: bool) -> list:
    """Nest pages by their URL path segments, preserving crawl order.

    A directory and a same-named page (docs.md + docs/) merge into one
    section with the page as its first entry.
    """
    root: dict = {"sections": {}, "pages": []}

    def section_for(segments: list[str]) -> dict:
        node = root
        for segment in segments:
            node = node["sections"].setdefault(
                segment, {"sections": {}, "pages": []}
            )
        return node

    for page in pages:
        if page["path"] == "index.md":
            continue  # always pinned first
        parts = page["path"][:-3].split("/")
        section_for(parts[:-1])["pages"].append((page["title"], page["path"]))

    def render(node: dict, prefix: str) -> list:
        entries = [{title: path} for title, path in node["pages"]]
        for name, child in node["sections"].items():
            # A page with the section's own path (Products.md next to
            # Products/) becomes the section's first entry and label, and
            # the section takes that page's place in the crawl order.
            lead_path = f"{prefix}{name}.md"
            rendered = render(child, f"{prefix}{name}/")
            index = next(
                (i for i, e in enumerate(entries) if list(e.values())[0] == lead_path), None
            )
            if index is not None:
                lead = entries[index]
                entries[index] = {list(lead.keys())[0]: [lead] + rendered}
            else:
                entries.append({name.replace("-", " ").replace("_", " "): rendered})
        return entries

    nav = render(root, "")
    if has_homepage:
        nav.insert(0, {"Home": "index.md"})
    return nav


def ensure_homepage(crawl_dir: Path, pages: list[dict]) -> bool:
    """MkDocs 404s without docs_dir/index.md; generate a page list if absent."""
    index = crawl_dir / "index.md"
    if index.exists():
        return True
    lines = ["# Crawled documentation", ""]
    lines += [f"- [{p['title']}]({quote(p['path'])})" for p in pages]
    index.write_text("\n".join(lines) + "\n")
    print(f"generated {index} (homepage listing {len(pages)} pages)", file=sys.stderr)
    return True


def default_theme() -> str:
    return "material" if importlib.util.find_spec("material") else "mkdocs"


def write_config(
    config_dir: Path, crawl_dir: Path, site_name: str, theme: str, nav: list
) -> Path:
    config: dict = {
        "site_name": site_name,
        "docs_dir": str(crawl_dir.resolve()),
        "site_dir": str((config_dir / "site").resolve()),
        "theme": {"name": theme},
        "use_directory_urls": True,
        "nav": nav,
    }
    if theme == "material":
        config["theme"]["features"] = [
            "navigation.sections",
            "navigation.top",
            "search.suggest",
        ]
        config["plugins"] = ["search"]
    path = config_dir / "mkdocs.yml"
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("crawl_dir", type=Path, nargs="?", default=Path("./out"),
                        help="getdocs output directory (default: ./out)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--theme", default=None,
                        help="MkDocs theme (default: material when installed, else mkdocs)")
    parser.add_argument("--site-name", help="Override the site name (default: first seed's host)")
    parser.add_argument("--build", metavar="DIR",
                        help="Build a static site into DIR instead of serving")
    args = parser.parse_args()

    if shutil.which("mkdocs") is None:
        print("error: mkdocs not found — pip install mkdocs", file=sys.stderr)
        return 2
    if not args.crawl_dir.is_dir() or not any(args.crawl_dir.rglob("*.md")):
        print(f"error: no crawled .md files found in {args.crawl_dir}", file=sys.stderr)
        return 2

    pages = crawled_pages(args.crawl_dir)
    has_homepage = ensure_homepage(args.crawl_dir, pages)
    nav = build_nav(pages, has_homepage)
    site_name = args.site_name or site_name_for(args.crawl_dir)
    theme = args.theme or default_theme()

    with tempfile.TemporaryDirectory(prefix="getdocs-mkdocs-") as tmp:
        config = write_config(Path(tmp), args.crawl_dir, site_name, theme, nav)
        # --use-directory-urls is passed explicitly: with click >= 8.2 the
        # mkdocs CLI's None-default flag resolves to False and silently
        # overrides the config file, flattening every page to page.html —
        # which breaks the original site's trailing-slash links.
        if args.build:
            command = ["mkdocs", "build", "--use-directory-urls",
                       "-f", str(config), "-d", str(Path(args.build).resolve())]
        else:
            command = ["mkdocs", "serve", "--use-directory-urls",
                       "-f", str(config), "-a", f"127.0.0.1:{args.port}"]
        return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
