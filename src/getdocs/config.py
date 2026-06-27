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
    summary_json: bool = False  # emit a machine-readable Outcome summary object
    keep_html: bool = False
    sitemap: str = "both"  # "both", "off" (--no-sitemap), or "only" (--sitemap-only)
    selector: str | None = None  # CSS selector naming the content container
    render: str = "auto"  # "auto" (escalate on Shells), "always", or "never"
    ignore_robots: bool = False
    resume: bool = False  # continue an interrupted Crawl from saved state
    delay: float = 1.0  # throttle start delay in seconds; 0 disables throttling
    concurrency: int = 4  # concurrent requests per domain
    download_media: bool = False  # fetch referenced Assets into _media/
    media_max_size: float = 50.0  # per-Asset cap in MB; larger files stay hotlinked
    clone_source: bool = True  # clone the docs' source repo if the site is open-source
    contact: str | None = None  # email/URL appended to the User-Agent (crawling etiquette)
    user_agent: str | None = None  # override the User-Agent string entirely


@dataclass(frozen=True)
class ServeConfig:
    host: str = "127.0.0.1"
    port: int = 8000
