# The API service runs one subprocess per Crawl

Scrapy runs on Twisted, and a Twisted reactor can only be started once per process — a long-lived API service cannot repeatedly run crawls in-process, and the asyncio-reactor bridge is fragile under concurrent crawls. So the engine boundary is a single entrypoint (`CrawlConfig` in, event stream out): the CLI drives it in-process via `CrawlerProcess`, and the future API service spawns the CLI as a subprocess per Crawl, reading JSONL Page records from stdout as the event stream. Subprocess isolation also gives per-crawl resource limits and crash isolation, and the JSONL output format doubles as the process boundary protocol.

## Considered Options

- Shared-process asyncio reactor inside the API worker — rejected: fights the one-reactor constraint, couples crash domains across crawls.
