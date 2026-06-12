"""Engine: shallow Scrapy glue around the deep modules.

Runs one Crawl per process via CrawlerProcess — the Twisted reactor starts
once and never restarts (ADR-0002), which is why the future API service
spawns this as a subprocess per Crawl.
"""

from datetime import datetime, timezone

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import TextResponse

from getdocs.config import CrawlConfig
from getdocs.extract import extract_page
from getdocs.output import FileTreeWriter, PageRecord
from getdocs.scope import Scope
from getdocs.urlnorm import normalize


class _CrawlSpider(scrapy.Spider):
    name = "getdocs"

    def __init__(self, config: CrawlConfig, writer: FileTreeWriter, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.writer = writer
        self.scope = Scope.from_seeds(
            config.seeds,
            allow_backward=config.allow_backward,
            allow_subdomains=config.allow_subdomains,
            include_paths=config.include_paths,
            exclude_paths=config.exclude_paths,
        )
        self.enqueued = {normalize(seed) for seed in config.seeds}
        self.written: set[str] = set()

    async def start(self):
        for seed in self.config.seeds:
            yield scrapy.Request(seed, callback=self.parse_page)

    def parse_page(self, response):
        # Redirects land on their final URL, which may already be written.
        norm = normalize(response.url)
        if norm not in self.written:
            self.written.add(norm)
            extracted = extract_page(response.text, response.url)
            self.writer.write_page(
                PageRecord(
                    url=response.url,
                    title=extracted.title,
                    markdown=extracted.markdown,
                    status=response.status,
                    crawled_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    canonical=extracted.canonical,
                )
            )

        if not isinstance(response, TextResponse):
            return
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href.strip())
            if not self.scope.allows(url):
                continue
            norm = normalize(url)
            if norm in self.enqueued:
                continue
            self.enqueued.add(norm)
            yield scrapy.Request(url, callback=self.parse_page)


def run_crawl(config: CrawlConfig) -> int:
    """Run a Crawl to completion; returns the number of Pages produced."""
    writer = FileTreeWriter(config.output_dir)
    process = CrawlerProcess(
        settings={
            "LOG_LEVEL": "ERROR",
            "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
            "DEPTH_LIMIT": config.depth,
        },
        install_root_handler=False,
    )
    process.crawl(_CrawlSpider, config=config, writer=writer)
    process.start()
    writer.write_manifest(seeds=config.seeds)
    return writer.page_count
