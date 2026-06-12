"""Jobs: run Crawls as subprocesses and track their state.

Per ADR-0002, a job is the getdocs CLI run with --format jsonl; its stdout
stream is the event protocol. One subprocess per Crawl sidesteps the
one-reactor-per-process constraint and isolates crashes.
"""

import asyncio
import json
import sys
import tempfile
import uuid
from dataclasses import dataclass, field

_BOOL_FLAGS = {
    "allow_backward": "--allow-backward",
    "allow_subdomains": "--allow-subdomains",
    "ignore_robots": "--ignore-robots",
    "keep_html": "--keep-html",
}
_VALUE_FLAGS = {
    "limit": "--limit",
    "depth": "--depth",
    "delay": "--delay",
    "concurrency": "--concurrency",
    "render": "--render",
    "selector": "--selector",
}
_LIST_FLAGS = {
    "include_paths": "--include-paths",
    "exclude_paths": "--exclude-paths",
}
_SITEMAP_FLAGS = {"off": "--no-sitemap", "only": "--sitemap-only"}

# JSONL lines carry whole pages (and raw HTML with keep_html).
_STREAM_LIMIT = 32 * 1024 * 1024


def build_args(options: dict, output_dir: str) -> list[str]:
    seeds = options.get("urls") or [options["url"]]
    args = ["crawl", *seeds, "--format", "jsonl", "-o", output_dir]
    for key, flag in _VALUE_FLAGS.items():
        if options.get(key) is not None:
            args += [flag, str(options[key])]
    for key, flag in _BOOL_FLAGS.items():
        if options.get(key):
            args.append(flag)
    for key, flag in _LIST_FLAGS.items():
        for value in options.get(key) or []:
            args += [flag, value]
    sitemap_flag = _SITEMAP_FLAGS.get(options.get("sitemap", ""))
    if sitemap_flag:
        args.append(sitemap_flag)
    return args


@dataclass
class CrawlJob:
    id: str
    seeds: list[str]
    status: str = "running"  # running | completed | failed | cancelled
    pages: list[dict] = field(default_factory=list)
    manifest: dict | None = None
    error: str | None = None


class JobManager:
    def __init__(self):
        self.jobs: dict[str, CrawlJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def start(self, options: dict) -> CrawlJob:
        seeds = options.get("urls") or [options["url"]]
        job = CrawlJob(id=uuid.uuid4().hex, seeds=seeds)
        self.jobs[job.id] = job
        output_dir = tempfile.mkdtemp(prefix=f"getdocs-{job.id[:8]}-")
        args = build_args(options, output_dir=output_dir)
        self._tasks[job.id] = asyncio.ensure_future(self._run(job, args))
        return job

    def get(self, job_id: str) -> CrawlJob | None:
        return self.jobs.get(job_id)

    async def wait(self, job_id: str) -> CrawlJob:
        await self._tasks[job_id]
        return self.jobs[job_id]

    async def _run(self, job: CrawlJob, args: list[str]) -> None:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "getdocs", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_STREAM_LIMIT,
        )
        async for line in process.stdout:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "page":
                job.pages.append({k: v for k, v in record.items() if k != "type"})
            elif record.get("type") == "manifest":
                job.manifest = {k: v for k, v in record.items() if k != "type"}
        stderr = await process.stderr.read()
        returncode = await process.wait()
        if returncode == 0:
            job.status = "completed"
        else:
            job.status = "failed"
            job.error = stderr.decode(errors="replace").strip()[-2000:] or (
                f"crawl exited with code {returncode}"
            )
