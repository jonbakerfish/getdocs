"""CrawlConfig: the value object describing a Crawl — the engine boundary (ADR-0002)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CrawlConfig:
    seeds: list[str] = field(default_factory=list)
    output_dir: Path = Path("./out")
    allow_backward: bool = False
    allow_subdomains: bool = False
    include_paths: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    depth: int = 0  # link-hops from any seed; 0 = unlimited
    limit: int = 1000  # max Pages per Crawl; 0 = unlimited
    format: str = "files"  # "files" or "jsonl"
    keep_html: bool = False
    sitemap: str = "both"  # "both", "off" (--no-sitemap), or "only" (--sitemap-only)
    selector: str | None = None  # CSS selector naming the content container
    render: str = "auto"  # "auto" (escalate on Shells), "always", or "never"
    ignore_robots: bool = False
    resume: bool = False  # continue an interrupted Crawl from saved state
    delay: float = 1.0  # throttle start delay in seconds; 0 disables throttling
    concurrency: int = 4  # concurrent requests per domain
