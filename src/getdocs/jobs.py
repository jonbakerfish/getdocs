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
    webhook_failures: int = 0


class JobManager:
    def __init__(self):
        self.jobs: dict[str, CrawlJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def start(self, options: dict) -> CrawlJob:
        seeds = options.get("urls") or [options["url"]]
        job = CrawlJob(id=uuid.uuid4().hex, seeds=seeds)
        self.jobs[job.id] = job
        output_dir = tempfile.mkdtemp(prefix=f"getdocs-{job.id[:8]}-")
        args = build_args(options, output_dir=output_dir)
        self._tasks[job.id] = asyncio.ensure_future(
            self._run(job, args, webhook=options.get("webhook"))
        )
        return job

    def get(self, job_id: str) -> CrawlJob | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> CrawlJob | None:
        """Cancel a running job (terminates its subprocess, keeps partial
        results). A no-op on finished jobs; None for unknown ids."""
        job = self.jobs.get(job_id)
        if job is None:
            return None
        if job.status == "running":
            job.status = "cancelled"
            process = self._processes.get(job_id)
            if process is not None and process.returncode is None:
                process.terminate()
        return job

    async def wait(self, job_id: str) -> CrawlJob:
        await self._tasks[job_id]
        return self.jobs[job_id]

    def _publish(self, job_id: str, event: dict) -> None:
        for queue in self._subscribers.get(job_id, []):
            queue.put_nowait(event)

    async def stream(self, job_id: str):
        """Yield a job's events: a replay of everything so far, then live
        page events, ending with the manifest (when one was produced).

        The queue is attached in the same event-loop step as the replay
        snapshot, so no event is missed or duplicated around the boundary.
        """
        job = self.jobs[job_id]
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        try:
            replay = list(job.pages)
            finished = job.status != "running"
            for record in replay:
                yield {"type": "page", **record}
            if finished:
                if job.manifest is not None:
                    yield {"type": "manifest", **job.manifest}
                return
            while True:
                event = await queue.get()
                if event["type"] == "end":
                    return
                yield event
                if event["type"] == "manifest":
                    return
        finally:
            self._subscribers[job_id].remove(queue)

    async def _deliver(self, job: CrawlJob, url: str, payload: dict) -> None:
        """Bounded-retry webhook POST; failures are recorded, never raised."""
        import httpx

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.post(url, json=payload)
                if response.status_code < 400:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05 * (attempt + 1))
        job.webhook_failures += 1

    async def _run(self, job: CrawlJob, args: list[str], webhook: str | None = None) -> None:
        if webhook:
            await self._deliver(
                job, webhook, {"event": "started", "id": job.id, "seeds": job.seeds}
            )
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "getdocs", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_STREAM_LIMIT,
        )
        self._processes[job.id] = process
        async for line in process.stdout:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "page":
                page = {k: v for k, v in record.items() if k != "type"}
                job.pages.append(page)
                self._publish(job.id, record)
                if webhook:
                    await self._deliver(
                        job, webhook, {"event": "page", "id": job.id, "page": page}
                    )
            elif record.get("type") == "manifest":
                job.manifest = {k: v for k, v in record.items() if k != "type"}
                self._publish(job.id, record)
        stderr = await process.stderr.read()
        returncode = await process.wait()
        if job.status == "cancelled":
            pass  # keep the cancelled status and partial pages
        elif returncode == 0:
            job.status = "completed"
        else:
            job.status = "failed"
            job.error = stderr.decode(errors="replace").strip()[-2000:] or (
                f"crawl exited with code {returncode}"
            )
        self._publish(job.id, {"type": "end", "status": job.status})
        if webhook:
            await self._deliver(
                job,
                webhook,
                {
                    "event": "completed",
                    "id": job.id,
                    "status": job.status,
                    "manifest": job.manifest,
                },
            )
