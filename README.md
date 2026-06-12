# getdocs

Crawl a documentation site and emit clean markdown.

```bash
getdocs crawl https://example.com/docs -o ./out
```

Each crawled Page is written as a `.md` file mirroring the URL path
(`example.com/docs/auth` → `out/docs/auth.md`) with YAML frontmatter
(`url`, `title`, `crawled_at`, `status`), plus a `crawl.json` Manifest
summarizing the Crawl.

Sitemap discovery, JavaScript rendering, polite throttling, JSONL output,
and resumable crawls are built in — see [docs/USAGE.md](docs/USAGE.md).

## Development

```bash
conda create -n getdocs python=3.12 pip
conda run -n getdocs python -m pip install -e ".[dev]"
conda run -n getdocs python -m pytest
```

Domain vocabulary lives in [CONTEXT.md](CONTEXT.md); architectural decisions in
[docs/adr/](docs/adr/). Work is tracked as GitHub issues (see
[docs/agents/](docs/agents/)).
