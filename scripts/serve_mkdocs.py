#!/usr/bin/env python
"""Serve a getdocs crawl output directory with MkDocs.

The crawl output is already MkDocs-friendly: a tree of .md files whose YAML
frontmatter (url, title, …) MkDocs reads as page meta. This script generates
a mkdocs.yml pointing at the crawl directory, adds a homepage if the crawl
didn't produce one, and runs `mkdocs serve` (or `mkdocs build`).

Usage:
    getdocs crawl https://example.com/docs -o ./out
    python scripts/serve_mkdocs.py ./out
    python scripts/serve_mkdocs.py ./out --theme material --port 9000
    python scripts/serve_mkdocs.py ./out --build site/   # static build instead

Requires: pip install mkdocs   (plus mkdocs-material for --theme material)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def site_name_for(crawl_dir: Path) -> str:
    manifest = crawl_dir / "crawl.json"
    if manifest.exists():
        seeds = json.loads(manifest.read_text()).get("seeds") or []
        if seeds:
            return urlsplit(seeds[0]).netloc or "getdocs crawl"
    return "getdocs crawl"


def ensure_homepage(crawl_dir: Path) -> None:
    """MkDocs 404s without docs_dir/index.md; generate a page list if absent."""
    index = crawl_dir / "index.md"
    if index.exists():
        return
    pages = sorted(
        p.relative_to(crawl_dir).as_posix()
        for p in crawl_dir.rglob("*.md")
        if not p.relative_to(crawl_dir).as_posix().startswith(".")
    )
    lines = ["# Crawled documentation", ""]
    lines += [f"- [{path[:-3]}]({path})" for path in pages]
    index.write_text("\n".join(lines) + "\n")
    print(f"generated {index} (homepage listing {len(pages)} pages)", file=sys.stderr)


def write_config(config_dir: Path, crawl_dir: Path, site_name: str, theme: str) -> Path:
    config = config_dir / "mkdocs.yml"
    config.write_text(
        f"site_name: {site_name}\n"
        f"docs_dir: {crawl_dir.resolve()}\n"
        f"site_dir: {(config_dir / 'site').resolve()}\n"
        f"theme:\n  name: {theme}\n"
        "use_directory_urls: true\n"
    )
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("crawl_dir", type=Path, nargs="?", default=Path("./out"),
                        help="getdocs output directory (default: ./out)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--theme", default="mkdocs",
                        help="MkDocs theme, e.g. mkdocs, readthedocs, material (default: mkdocs)")
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

    ensure_homepage(args.crawl_dir)
    site_name = args.site_name or site_name_for(args.crawl_dir)

    with tempfile.TemporaryDirectory(prefix="getdocs-mkdocs-") as tmp:
        config = write_config(Path(tmp), args.crawl_dir, site_name, args.theme)
        if args.build:
            command = ["mkdocs", "build", "-f", str(config), "-d", str(Path(args.build).resolve())]
        else:
            command = ["mkdocs", "serve", "-f", str(config), "-a", f"127.0.0.1:{args.port}"]
        return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
