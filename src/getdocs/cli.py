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

    args = parser.parse_args(argv)
    return CrawlConfig(seeds=args.seeds, output_dir=args.output_dir)


def main(argv: list[str] | None = None) -> int:
    from getdocs.engine import run_crawl

    config = parse_args(argv)
    page_count = run_crawl(config)
    if page_count == 0:
        print("error: no Pages produced — seed(s) unreachable?", flush=True)
        return 1
    return 0
