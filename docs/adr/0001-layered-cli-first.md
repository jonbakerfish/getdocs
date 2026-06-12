# Layered architecture: crawl engine + CLI first, API service later

The PROMPT cites Firecrawl-style APIs (polling/WebSocket/webhook), which suggests building an API service. We decided instead to build a core crawl engine (Scrapy-based Python library) with a CLI as the first deliverable, and to design the engine boundary so a FastAPI service can wrap it in a later phase. The crawl engine is the hard, valuable part; a CLI validates extraction quality end-to-end without standing up job-queue and HTTP infrastructure first.
