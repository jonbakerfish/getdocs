"""API service: Firecrawl-style async Crawl jobs over the engine (ADR-0002)."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from getdocs.jobs import CrawlJob, JobManager


class CrawlRequest(BaseModel):
    url: str | None = None
    urls: list[str] | None = None
    limit: int | None = None
    depth: int | None = None
    allow_backward: bool = False
    allow_subdomains: bool = False
    include_paths: list[str] | None = None
    exclude_paths: list[str] | None = None
    sitemap: str | None = None  # "both" | "off" | "only"
    render: str | None = None  # "auto" | "always" | "never"
    selector: str | None = None
    ignore_robots: bool = False
    keep_html: bool = False
    delay: float | None = None
    concurrency: int | None = None

    @model_validator(mode="after")
    def _require_some_url(self):
        if not self.url and not self.urls:
            raise ValueError("either url or urls is required")
        return self


def _serialize(job: CrawlJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "seeds": job.seeds,
        "page_count": len(job.pages),
        "pages": job.pages,
        "manifest": job.manifest,
        "error": job.error,
    }


def create_app(manager: JobManager | None = None) -> FastAPI:
    manager = manager or JobManager()
    app = FastAPI(title="getdocs", version="0.1.0")
    app.state.manager = manager

    @app.post("/v1/crawl", status_code=202)
    async def start_crawl(request: CrawlRequest):
        job = manager.start(request.model_dump(exclude_none=True))
        return {"id": job.id, "status": job.status}

    @app.get("/v1/crawl/{job_id}")
    async def get_crawl(job_id: str):
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such Crawl job")
        return _serialize(job)

    return app
