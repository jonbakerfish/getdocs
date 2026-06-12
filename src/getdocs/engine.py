"""Engine: shallow Scrapy glue around the deep modules.

Runs one Crawl per process via CrawlerProcess — the Twisted reactor starts
once and never restarts (ADR-0002), which is why the future API service
spawns this as a subprocess per Crawl.
"""

from datetime import datetime, timezone

import scrapy
from scrapy.crawler import CrawlerProcess

from getdocs.config import CrawlConfig
from getdocs.extract import extract_page
from getdocs.output import FileTreeWriter, PageRecord


class _CrawlSpider(scrapy.Spider):
    name = "getdocs"

    def __init__(self, config: CrawlConfig, writer: FileTreeWriter, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.writer = writer

    async def start(self):
        for seed in self.config.seeds:
            yield scrapy.Request(seed, callback=self.parse_page)

    def parse_page(self, response):
        extracted = extract_page(response.text, response.url)
        self.writer.write_page(
            PageRecord(
                url=response.url,
                title=extracted.title,
                markdown=extracted.markdown,
                status=response.status,
                crawled_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )


def run_crawl(config: CrawlConfig) -> int:
    """Run a Crawl to completion; returns the number of Pages produced."""
    writer = FileTreeWriter(config.output_dir)
    process = CrawlerProcess(
        settings={"LOG_LEVEL": "ERROR", "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7"},
        install_root_handler=False,
    )
    process.crawl(_CrawlSpider, config=config, writer=writer)
    process.start()
    writer.write_manifest(seeds=config.seeds)
    return writer.page_count
