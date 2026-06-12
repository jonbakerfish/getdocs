"""Engine: shallow Scrapy glue around the deep modules.

Runs one Crawl per process via CrawlerProcess — the Twisted reactor starts
once and never restarts (ADR-0002), which is why the future API service
spawns this as a subprocess per Crawl.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.downloadermiddlewares.retry import get_retry_request
from scrapy.exceptions import CloseSpider, IgnoreRequest
from scrapy.http import TextResponse
from scrapy.spidermiddlewares.httperror import HttpError

from getdocs.config import CrawlConfig
from getdocs.extract import extract_page, is_shell
from getdocs.output import FileTreeWriter, JsonlWriter, PageRecord
from getdocs.scope import Scope
from getdocs.sitemap import parse_robots_sitemaps, parse_sitemap_xml
from getdocs.urlnorm import normalize


def state_file_for(config: CrawlConfig) -> Path:
    return config.output_dir / ".getdocs" / "crawl-state.json"


def playwright_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("scrapy_playwright") is not None


_SHELL_LATCH_THRESHOLD = 2  # Shells on one host before it renders everything


class RetryAfterMiddleware:
    """Retry 429 responses no sooner than the server's Retry-After asks.

    Scrapy's stock RetryMiddleware retries 429 immediately, which is exactly
    what a rate-limiting server is telling us not to do — so 429 is removed
    from its codes and handled here with an async sleep (asyncio reactor).
    """

    async def process_response(self, request, response, spider):
        if response.status != 429:
            return response
        retry = get_retry_request(request, spider=spider, reason="429 Too Many Requests")
        if retry is None:
            return response  # retries exhausted; falls through to the errback
        try:
            delay = float(response.headers.get("Retry-After", b"1"))
        except ValueError:
            delay = 1.0
        await asyncio.sleep(delay)
        return retry


class _CrawlSpider(scrapy.Spider):
    name = "getdocs"

    def __init__(
        self, config: CrawlConfig, writer, outcome: dict, resume_state: dict | None = None,
        render_enabled: bool = False, **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config
        self.writer = writer
        self.outcome = outcome
        self.resume_state = resume_state
        self.render_enabled = render_enabled
        self.shell_hosts: dict[str, int] = {}
        # Frontier bookkeeping, persisted across runs (see closed()).
        # pending maps a yielded URL to its hop count; an entry is removed
        # only once the URL is written or errored, so an interruption never
        # loses in-flight work.
        self.pending: dict[str, int] = {}
        self.scope = Scope.from_seeds(
            config.seeds,
            allow_backward=config.allow_backward,
            allow_subdomains=config.allow_subdomains,
            include_paths=config.include_paths,
            exclude_paths=config.exclude_paths,
        )
        self.follow_links = config.sitemap != "only"
        self.enqueued: set[str] = set(resume_state["enqueued"]) if resume_state else set()
        self.written: set[str] = set(resume_state["written"]) if resume_state else set()
        self.sitemaps_fetched: set[str] = set()

    # -- discovery ---------------------------------------------------------

    async def start(self):
        if self.config.sitemap != "off":
            roots = {f"{urlsplit(s).scheme}://{urlsplit(s).netloc}" for s in self.config.seeds}
            for root in sorted(roots):
                yield scrapy.Request(urljoin(root, "/robots.txt"), callback=self.parse_robots)
                for request in self._sitemap_requests([urljoin(root, "/sitemap.xml")]):
                    yield request
        if self.resume_state:
            for url, hops in self.resume_state["pending"].items():
                self.pending[url] = hops
                yield self._page_request(url, hops=hops)
        elif self.config.sitemap != "only":
            for seed in self.config.seeds:
                self.enqueued.add(normalize(seed))
                self.pending[seed] = 0
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
        rendered = response.meta.get("playwright", False)
        shellish = (
            not rendered and isinstance(response, TextResponse) and is_shell(response.text)
        )
        if shellish and self.config.render == "auto" and self.render_enabled:
            # Escalate: re-fetch through the browser. The pending entry
            # survives until the rendered version is written.
            host = urlsplit(response.url).netloc
            self.shell_hosts[host] = self.shell_hosts.get(host, 0) + 1
            yield scrapy.Request(
                response.request.url,
                callback=self.parse_page,
                errback=self.on_page_error,
                meta={"hops": response.meta["hops"], "playwright": True},
                dont_filter=True,
            )
            return

        norm = normalize(response.url)
        if norm not in self.written:
            if self.config.limit and self.writer.page_count >= self.config.limit:
                self.outcome["truncated"] = True
                raise CloseSpider("page limit reached")
            self.written.add(norm)
            extracted = extract_page(response.text, response.url, selector=self.config.selector)
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
            if shellish:
                # Rendering is off or unavailable: written as-is, flagged.
                self.outcome["shells"].append(response.url)
            self._progress()
        self.pending.pop(response.request.url, None)

        if not self.follow_links or not isinstance(response, TextResponse):
            return
        hops = response.meta["hops"]
        if self.config.depth and hops + 1 > self.config.depth:
            return
        for href in response.css("a::attr(href)").getall():
            yield from self._enqueue_page(response.urljoin(href.strip()), hops=hops + 1)

    def on_page_error(self, failure):
        self.pending.pop(failure.request.url, None)
        if failure.check(HttpError):
            response = failure.value.response
            error = {"url": response.url, "status": response.status, "reason": f"HTTP {response.status}"}
        elif failure.check(IgnoreRequest):
            # HttpError subclasses IgnoreRequest, so this arm only sees true
            # filtering — robots.txt telling us not to fetch.
            self.outcome["skipped"].append(
                {"url": failure.request.url, "reason": "robots.txt"}
            )
            self._progress()
            return
        else:
            error = {"url": failure.request.url, "status": None, "reason": failure.type.__name__}
        self.outcome["errors"].append(error)
        self._progress()

    # -- helpers -----------------------------------------------------------

    def _progress(self):
        done = len(self.written) + len(self.outcome["errors"])
        print(
            f"[getdocs] pages={len(self.written)} "
            f"pending={max(len(self.enqueued) - done, 0)} "
            f"errors={len(self.outcome['errors'])}",
            file=sys.stderr,
            flush=True,
        )

    def _page_request(self, url: str, hops: int) -> scrapy.Request:
        meta = {"hops": hops}
        if self._should_render(url):
            meta["playwright"] = True
        return scrapy.Request(
            url, callback=self.parse_page, errback=self.on_page_error, meta=meta
        )

    def _should_render(self, url: str) -> bool:
        if not self.render_enabled:
            return False
        if self.config.render == "always":
            return True
        host = urlsplit(url).netloc
        return self.shell_hosts.get(host, 0) >= _SHELL_LATCH_THRESHOLD

    def _enqueue_page(self, url: str, hops: int):
        if not self.scope.allows(url):
            return
        norm = normalize(url)
        if norm in self.enqueued:
            return
        self.enqueued.add(norm)
        self.pending[url] = hops
        yield self._page_request(url, hops=hops)

    def _sitemap_requests(self, urls: list[str]):
        for url in urls:
            if url not in self.sitemaps_fetched:
                self.sitemaps_fetched.add(url)
                yield scrapy.Request(url, callback=self.parse_sitemap)

    def closed(self, reason):
        state_file = state_file_for(self.config)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {
                    "seeds": self.config.seeds,
                    "enqueued": sorted(self.enqueued),
                    "written": sorted(self.written),
                    "pending": self.pending,
                    "errors": self.outcome["errors"],
                    "skipped": self.outcome["skipped"],
                    "shells": self.outcome["shells"],
                }
            )
        )


def run_crawl(config: CrawlConfig) -> int:
    """Run a Crawl to completion; returns the number of Pages produced."""
    if config.format == "jsonl":
        writer = JsonlWriter(sys.stdout)
    else:
        writer = FileTreeWriter(config.output_dir)
    resume_state = None
    if config.resume:
        resume_state = json.loads(state_file_for(config).read_text())
        writer.page_count = len(resume_state["written"])
    outcome = {
        "errors": list(resume_state["errors"]) if resume_state else [],
        "skipped": list(resume_state["skipped"]) if resume_state else [],
        "shells": list(resume_state.get("shells", [])) if resume_state else [],
        "truncated": False,  # recomputed by this run: a resumed Crawl may finish
    }
    render_enabled = config.render != "never" and playwright_available()
    if config.render != "never" and not render_enabled:
        print(
            "note: scrapy-playwright is not installed — JS rendering disabled; "
            "Shell pages will be written as-is and flagged in the Manifest",
            file=sys.stderr,
        )
    settings = {
        "LOG_LEVEL": "ERROR",
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "RETRY_TIMES": 2,
        # 429 is handled by RetryAfterMiddleware, which honors Retry-After.
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 522, 524, 408],
        "DOWNLOADER_MIDDLEWARES": {RetryAfterMiddleware: 560},
        "ROBOTSTXT_OBEY": not config.ignore_robots,
        "DOWNLOAD_DELAY": config.delay,
        "AUTOTHROTTLE_ENABLED": config.delay > 0,
        "AUTOTHROTTLE_START_DELAY": config.delay or 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": config.concurrency,
    }
    if render_enabled:
        settings["DOWNLOAD_HANDLERS"] = {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        }
        settings["TWISTED_REACTOR"] = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    process = CrawlerProcess(settings=settings, install_root_handler=False)
    process.crawl(
        _CrawlSpider,
        config=config,
        writer=writer,
        outcome=outcome,
        resume_state=resume_state,
        render_enabled=render_enabled,
    )
    process.start()
    writer.write_manifest(
        seeds=config.seeds,
        errors=outcome["errors"],
        truncated=outcome["truncated"],
        skipped=outcome["skipped"],
        shells=outcome["shells"],
    )
    return writer.page_count
