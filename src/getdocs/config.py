"""CrawlConfig: the value object describing a Crawl — the engine boundary (ADR-0002)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CrawlConfig:
    seeds: list[str] = field(default_factory=list)
    output_dir: Path = Path("./out")
