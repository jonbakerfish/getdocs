import asyncio

from getdocs.jobs import JobManager, build_args


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def build_docs_site(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/auth">Auth</a>'))
    site.add("/docs/auth", page("Auth", "<h1>Auth</h1>"))


def test_job_runs_a_crawl_to_completion(site):
    build_docs_site(site)

    async def scenario():
        manager = JobManager()
        job = manager.start({"url": f"{site.url}/docs/", "delay": 0})
        await manager.wait(job.id)
        return job

    job = asyncio.run(scenario())

    assert job.status == "completed"
    assert {p["title"] for p in job.pages} == {"Home", "Auth"}
    assert job.manifest["page_count"] == 2


def test_job_with_unreachable_seed_fails(tmp_path):
    async def scenario():
        manager = JobManager()
        job = manager.start({"url": "http://127.0.0.1:1/none", "delay": 0})
        await manager.wait(job.id)
        return job

    job = asyncio.run(scenario())

    assert job.status == "failed"
    assert job.pages == []
    assert job.error


def test_build_args_maps_options_to_cli_flags():
    args = build_args({
        "urls": ["https://a.com/d", "https://b.com/d"],
        "limit": 50,
        "depth": 2,
        "allow_backward": True,
        "include_paths": ["/d/api/*"],
        "render": "never",
        "delay": 0.5,
    }, output_dir="/tmp/job1")

    assert args[0] == "crawl"
    assert "https://a.com/d" in args and "https://b.com/d" in args
    assert ["--format", "jsonl"] == [args[args.index("--format")], args[args.index("--format") + 1]]
    assert ["--limit", "50"] == [args[args.index("--limit")], args[args.index("--limit") + 1]]
    assert ["--depth", "2"] == [args[args.index("--depth")], args[args.index("--depth") + 1]]
    assert "--allow-backward" in args
    assert "--allow-subdomains" not in args
    assert ["--include-paths", "/d/api/*"] == [args[args.index("--include-paths")], args[args.index("--include-paths") + 1]]
    assert ["--render", "never"] == [args[args.index("--render")], args[args.index("--render") + 1]]
    assert ["--delay", "0.5"] == [args[args.index("--delay")], args[args.index("--delay") + 1]]
