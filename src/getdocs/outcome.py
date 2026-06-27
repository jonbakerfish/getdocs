"""Outcome: the structured result of a getdocs run — a Crawl or a Clone (ADR-0007).

A run produces exactly one Outcome — a Crawl or a Clone. The always-on stderr
summary line and the opt-in --summary-json object are both rendered from the
same Outcome value, so the two surfaces cannot disagree.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrawlOutcome:
    """What a Crawl produced: how many Pages, where they landed, whether capped."""

    pages: int
    output_dir: Path
    manifest: Path | None  # crawl.json path in files mode; None in jsonl mode
    truncated: bool
    format: str = "files"  # "files" or "jsonl"

    @property
    def status(self) -> str:
        """ok | truncated | empty — derived so the line and JSON always agree."""
        if self.pages == 0:
            return "empty"
        if self.truncated:
            return "truncated"
        return "ok"

    def stderr_line(self) -> str:
        if self.format == "jsonl":
            dest = "stdout (jsonl)"
        else:
            dest = f"{self.output_dir} ({self.manifest.name})"
        note = " [truncated]" if self.truncated else ""
        return f"getdocs: crawled {self.pages} Pages → {dest}{note}"

    def summary_json(self) -> dict:
        return {
            "outcome": "crawled",
            "status": self.status,
            "pages": self.pages,
            "output_dir": str(self.output_dir),
            "manifest": str(self.manifest),
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class CloneOutcome:
    """What a Clone produced: the source repo, where it landed, its serve config.

    A Clone is a sibling of a Crawl, not a kind of Crawl (CONTEXT.md): it carries
    no Pages and no Manifest, so the summary omits those keys entirely.
    """

    repo: str  # source-repo identity, e.g. "acme/docs"
    output_dir: Path  # where the clone landed, e.g. ./out/docs
    mkdocs_config: Path | None  # generated/own serve config; None if none was written

    status: str = "ok"  # producing a Clone at all means it succeeded

    def stderr_line(self) -> str:
        cfg = f" ({self.mkdocs_config.name})" if self.mkdocs_config else ""
        return f"getdocs: cloned {self.repo} → {self.output_dir}{cfg}"

    def summary_json(self) -> dict:
        return {
            "outcome": "cloned",
            "status": self.status,
            "repo": self.repo,
            "output_dir": str(self.output_dir),
            "mkdocs_config": str(self.mkdocs_config) if self.mkdocs_config else None,
        }
