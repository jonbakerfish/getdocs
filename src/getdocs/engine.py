"""Engine: shallow Scrapy glue around the deep modules.

Runs one Crawl per process via CrawlerProcess — the Twisted reactor starts
once and never restarts (ADR-0002), which is why the future API service
spawns this as a subprocess per Crawl.
"""

import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import TextResponse

from getdocs.config import CrawlConfig
from getdocs.extract import extract_page
from getdocs.output import FileTreeWriter, JsonlWriter, PageRecord
from getdocs.scope import Scope
from getdocs.sitemap import parse_robots_sitemaps, parse_sitemap_xml
from getdocs.urlnorm import normalize


class _CrawlSpider(scrapy.Spider):
    name = "getdocs"

    def __init__(self, config: CrawlConfig, writer, **kwargs):
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
        self.follow_links = config.sitemap != "only"
        self.enqueued: set[str] = set()
        self.written: set[str] = set()
        self.sitemaps_fetched: set[str] = set()

    # -- discovery ---------------------------------------------------------

    async def start(self):
        if self.config.sitemap != "off":
            roots = {f"{urlsplit(s).scheme}://{urlsplit(s).netloc}" for s in self.config.seeds}
            for root in sorted(roots):
                yield scrapy.Request(urljoin(root, "/robots.txt"), callback=self.parse_robots)
                for request in self._sitemap_requests([urljoin(root, "/sitemap.xml")]):
                    yield request
        if self.config.sitemap != "only":
            for seed in self.config.seeds:
                self.enqueued.add(normalize(seed))
                yield self._page_request(seed, hops=0)

    def parse_robots(self, response):
        yield from self._sitemap_requests(parse_robots_sitemaps(response.text))

    def parse_sitemap(self, response):
        page_urls, nested = parse_sitemap_xml(response.text)
        yield from self._sitemap_requests(nested)
        for url in page_urls:
            # Sitemap-discovered Pages are depth-0 seeds: Scope still gates
            # them, but --depth never excludes them.
            yield from self._enqueue_page(url, hops=0)

    # -- fetching ----------------------------------------------------------

    def parse_page(self, response):
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
                    html=response.text if self.config.keep_html else None,
                )
            )

        if not self.follow_links or not isinstance(response, TextResponse):
            return
        hops = response.meta["hops"]
        if self.config.depth and hops + 1 > self.config.depth:
            return
        for href in response.css("a::attr(href)").getall():
            yield from self._enqueue_page(response.urljoin(href.strip()), hops=hops + 1)

    # -- helpers -----------------------------------------------------------

    def _page_request(self, url: str, hops: int) -> scrapy.Request:
        return scrapy.Request(url, callback=self.parse_page, meta={"hops": hops})

    def _enqueue_page(self, url: str, hops: int):
        if not self.scope.allows(url):
            return
        norm = normalize(url)
        if norm in self.enqueued:
            return
        self.enqueued.add(norm)
        yield self._page_request(url, hops=hops)

    def _sitemap_requests(self, urls: list[str]):
        for url in urls:
            if url not in self.sitemaps_fetched:
                self.sitemaps_fetched.add(url)
                yield scrapy.Request(url, callback=self.parse_sitemap)


def run_crawl(config: CrawlConfig) -> int:
    """Run a Crawl to completion; returns the number of Pages produced."""
    if config.format == "jsonl":
        writer = JsonlWriter(sys.stdout)
    else:
        writer = FileTreeWriter(config.output_dir)
    process = CrawlerProcess(
        settings={
            "LOG_LEVEL": "ERROR",
            "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        },
        install_root_handler=False,
    )
    process.crawl(_CrawlSpider, config=config, writer=writer)
    process.start()
    writer.write_manifest(seeds=config.seeds)
    return writer.page_count
