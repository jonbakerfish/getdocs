"""CLI: argument parsing to CrawlConfig, engine invocation, exit-code mapping."""

import argparse
from pathlib import Path

from getdocs.config import CrawlConfig, ServeConfig


def parse_args(argv: list[str] | None = None) -> CrawlConfig | ServeConfig:
    parser = argparse.ArgumentParser(
        prog="getdocs",
        description="Crawl a documentation site and emit clean markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl", help="Run a Crawl from one or more seed URLs")
    crawl.add_argument(
        "seeds", nargs="*", metavar="URL",
        help="Seed URL(s) for the Crawl (omit with --resume to reuse saved seeds)",
    )
    crawl.add_argument(
        "-f", "--seeds-file", type=Path, metavar="FILE",
        help="File of additional Seed URLs, one per line (# comments and blank lines ignored)",
    )
    crawl.add_argument(
        "--resume", action="store_true",
        help="Continue the interrupted Crawl whose state lives in the output directory",
    )
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
        "--selector", metavar="CSS",
        help="CSS selector for the content container (overrides auto-detection)",
    )
    crawl.add_argument(
        "--render", choices=["auto", "always", "never"], default="auto",
        help="JavaScript rendering: auto re-fetches detected SPA shells via a "
             "headless browser, always renders everything, never disables it",
    )
    crawl.add_argument(
        "--ignore-robots", action="store_true",
        help="Consciously override robots.txt rules",
    )
    crawl.add_argument(
        "--delay", type=float, default=1.0, metavar="SECONDS",
        help="Adaptive-throttle start delay between requests (default: 1.0; 0 = no throttle)",
    )
    crawl.add_argument(
        "--concurrency", type=int, default=4, metavar="N",
        help="Concurrent requests per domain (default: 4)",
    )
    crawl.add_argument(
        "--download-media", action="store_true",
        help="Download referenced images/documents (Assets) into _media/ and "
             "rewrite links to the local copies",
    )
    crawl.add_argument(
        "--media-max-size", type=float, default=50.0, metavar="MB",
        help="Per-Asset size cap for --download-media (default: 50); larger files stay linked",
    )
    crawl.add_argument(
        "--keep-html", action="store_true",
        help="Also keep each Page's raw HTML (sidecar file / jsonl field)",
    )
    crawl.add_argument(
        "--no-clone-source", dest="clone_source", action="store_false", default=True,
        help="Always crawl, even when the docs site links a public source repo "
             "(by default getdocs clones that repo instead of crawling)",
    )

    serve = subparsers.add_parser("serve", help="Run the getdocs API service")
    serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    args = parser.parse_args(argv)
    if args.command == "serve":
        return ServeConfig(host=args.host, port=args.port)
    seeds = list(args.seeds)
    if args.seeds_file is not None:
        if not args.seeds_file.exists():
            crawl.error(f"seeds file not found: {args.seeds_file}")
        seeds += [
            line.strip()
            for line in args.seeds_file.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if not seeds and not args.resume:
        crawl.error("at least one seed URL is required (or --seeds-file / --resume)")
    return CrawlConfig(
        seeds=seeds,
        resume=args.resume,
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
        selector=args.selector,
        render=args.render,
        ignore_robots=args.ignore_robots,
        delay=args.delay,
        concurrency=args.concurrency,
        download_media=args.download_media,
        media_max_size=args.media_max_size,
        clone_source=args.clone_source,
    )


def main(argv: list[str] | None = None) -> int:
    import json
    import sys
    from dataclasses import replace

    from getdocs.engine import playwright_available, run_crawl, state_file_for

    config = parse_args(argv)
    if isinstance(config, ServeConfig):
        try:
            import uvicorn

            from getdocs.api import create_app
        except ImportError:
            print(
                'error: getdocs serve needs the server extra (pip install "getdocs[server]")',
                file=sys.stderr,
            )
            return 2
        uvicorn.run(create_app(), host=config.host, port=config.port)
        return 0
    if config.render == "always" and not playwright_available():
        print(
            "error: --render always needs scrapy-playwright "
            "(pip install scrapy-playwright && playwright install chromium)",
            file=sys.stderr,
        )
        return 2
    # Source-first (ADR-0006): if the docs site is open-source, clone its repo
    # instead of crawling. Files-mode only — jsonl is a page stream with no
    # place for a clone; --resume continues an existing crawl.
    if config.format == "files" and config.clone_source and not config.resume and config.seeds:
        from getdocs.source import clone_source_for

        if clone_source_for(config) is not None:
            return 0
    state_file = state_file_for(config)
    if config.resume:
        if not state_file.exists():
            print(f"error: no crawl state found in {config.output_dir}", file=sys.stderr)
            return 2
        saved_seeds = json.loads(state_file.read_text())["seeds"]
        config = replace(config, seeds=saved_seeds)
    elif state_file.exists():
        print(
            f"note: found crawl state from an earlier run in {config.output_dir} — "
            "starting over (use --resume to continue it)",
            file=sys.stderr,
        )
        state_file.unlink()

    page_count = run_crawl(config)
    if page_count == 0:
        # stderr: stdout belongs to the jsonl stream (ADR-0002)
        print("error: no Pages produced — seed(s) unreachable?", file=sys.stderr, flush=True)
        return 1
    return 0
