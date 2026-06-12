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
    format: str = "files"  # "files" or "jsonl"
    keep_html: bool = False
