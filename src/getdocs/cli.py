"""CLI: argument parsing to CrawlConfig, engine invocation, exit-code mapping."""

import argparse
from pathlib import Path

from getdocs.config import CrawlConfig


def parse_args(argv: list[str] | None = None) -> CrawlConfig:
    parser = argparse.ArgumentParser(
        prog="getdocs",
        description="Crawl a documentation site and emit clean markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl", help="Run a Crawl from one or more seed URLs")
    crawl.add_argument("seeds", nargs="+", metavar="URL", help="Seed URL(s) for the Crawl")
    crawl.add_argument(
        "-o", "--output-dir", type=Path, default=Path("./out"),
        help="Directory the Pages and Manifest are written to (default: ./out)",
    )
    crawl.add_argument(
        "--allow-backward", action="store_true",
        help="Widen Scope from the seed's path prefix to its whole host",
    )
    crawl.add_argument(
        "--allow-subdomains", action="store_true",
        help="Widen Scope to subdomains of the seed host",
    )
    crawl.add_argument(
        "--include-paths", action="append", default=[], metavar="GLOB",
        help="Only crawl paths matching at least one glob (repeatable)",
    )
    crawl.add_argument(
        "--exclude-paths", action="append", default=[], metavar="GLOB",
        help="Never crawl paths matching a glob (repeatable)",
    )
    crawl.add_argument(
        "--depth", type=int, default=0, metavar="N",
        help="Maximum link-hops from any seed (default: 0 = unlimited)",
    )
    crawl.add_argument(
        "--limit", type=int, default=1000, metavar="N",
        help="Maximum Pages per Crawl (default: 1000; 0 = unlimited)",
    )
    sitemap_group = crawl.add_mutually_exclusive_group()
    sitemap_group.add_argument(
        "--no-sitemap", dest="sitemap", action="store_const", const="off", default="both",
        help="Discover pages by link traversal only",
    )
    sitemap_group.add_argument(
        "--sitemap-only", dest="sitemap", action="store_const", const="only",
        help="Crawl exactly the in-Scope sitemap URLs; follow no links",
    )
    crawl.add_argument(
        "--format", choices=["files", "jsonl"], default="files",
        help="files: .md tree + crawl.json; jsonl: one record per Page on stdout",
    )
    crawl.add_argument(
        "--keep-html", action="store_true",
        help="Also keep each Page's raw HTML (sidecar file / jsonl field)",
    )

    args = parser.parse_args(argv)
    return CrawlConfig(
        seeds=args.seeds,
        output_dir=args.output_dir,
        allow_backward=args.allow_backward,
        allow_subdomains=args.allow_subdomains,
        include_paths=args.include_paths,
        exclude_paths=args.exclude_paths,
        depth=args.depth,
        limit=args.limit,
        format=args.format,
        keep_html=args.keep_html,
        sitemap=args.sitemap,
    )


def main(argv: list[str] | None = None) -> int:
    from getdocs.engine import run_crawl

    import sys

    config = parse_args(argv)
    page_count = run_crawl(config)
    if page_count == 0:
        # stderr: stdout belongs to the jsonl stream (ADR-0002)
        print("error: no Pages produced — seed(s) unreachable?", file=sys.stderr, flush=True)
        return 1
    return 0
