"""Output: Page records to a .md tree with YAML frontmatter, plus the Manifest."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


@dataclass(frozen=True)
class PageRecord:
    url: str
    title: str
    markdown: str
    status: int
    crawled_at: str
    canonical: str | None = None
    html: str | None = None


class FileTreeWriter:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.page_count = 0

    def path_for(self, url: str) -> Path:
        # Decode percent-escapes per segment so %20 doesn't end up in file
        # names (and %2F can't smuggle in extra directory levels).
        segments = [
            unquote(segment).replace("/", "_")
            for segment in urlsplit(url).path.split("/")
            if segment
        ]
        path = "/".join(segments) or "index"
        return self.output_dir / f"{path}.md"

    def write_page(self, record: PageRecord) -> Path:
        target = self.path_for(record.url)
        target.parent.mkdir(parents=True, exist_ok=True)

        frontmatter = {
            k: v
            for k, v in asdict(record).items()
            if k not in ("markdown", "html") and v is not None
        }
        target.write_text(
            "---\n"
            + yaml.safe_dump(frontmatter, sort_keys=False)
            + "---\n\n"
            + record.markdown
            + "\n"
        )
        if record.html is not None:
            target.with_suffix(".html").write_text(record.html)
        self.page_count += 1
        return target

    def write_manifest(
        self,
        seeds: list[str],
        errors: list[dict] | None = None,
        truncated: bool = False,
        skipped: list[dict] | None = None,
        shells: list[str] | None = None,
        nav: list[dict] | None = None,
        reading_order: list[str] | None = None,
        media_skipped: list[dict] | None = None,
    ) -> Path:
        target = self.output_dir / "crawl.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "seeds": seeds,
                    "page_count": self.page_count,
                    "errors": errors or [],
                    "skipped": skipped or [],
                    "shells": shells or [],
                    "truncated": truncated,
                    "nav": nav or [],
                    "reading_order": reading_order or [],
                    "media_skipped": media_skipped or [],
                },
                indent=2,
            )
            + "\n"
        )
        return target


class AssetStore:
    """Downloaded Assets land under _media/<host>/<decoded path>."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def save(self, url: str, body: bytes) -> str:
        parts = urlsplit(url)
        segments = [
            unquote(s).replace("/", "_") for s in parts.path.split("/") if s
        ] or ["asset"]
        relpath = "/".join(["_media", parts.netloc, *segments])
        target = self.output_dir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return relpath


class JsonlWriter:
    """One typed JSON record per line; the Manifest is the final record.

    This stream is the process-boundary protocol the future API service
    consumes (ADR-0002) — record shape changes are contract changes.
    """

    def __init__(self, stream):
        self.stream = stream
        self.page_count = 0

    def _emit(self, record: dict) -> None:
        self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.stream.flush()

    def write_page(self, record: PageRecord) -> None:
        fields = {k: v for k, v in asdict(record).items() if v is not None}
        self._emit({"type": "page", **fields})
        self.page_count += 1

    def write_manifest(
        self,
        seeds: list[str],
        errors: list[dict] | None = None,
        truncated: bool = False,
        skipped: list[dict] | None = None,
        shells: list[str] | None = None,
        nav: list[dict] | None = None,
        reading_order: list[str] | None = None,
        media_skipped: list[dict] | None = None,
    ) -> None:
        self._emit(
            {
                "type": "manifest",
                "seeds": seeds,
                "page_count": self.page_count,
                "errors": errors or [],
                "skipped": skipped or [],
                "shells": shells or [],
                "truncated": truncated,
                "nav": nav or [],
                "reading_order": reading_order or [],
                "media_skipped": media_skipped or [],
            }
        )
