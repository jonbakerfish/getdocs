# getdocs

A documentation crawler (Python 3.12, Scrapy + Playwright): recursively crawl a
docs site and emit clean markdown, or clone its source repo when one exists.
Domain vocabulary and design rationale are authoritative in `CONTEXT.md` and
`docs/adr/` — use those terms (Crawl, Clone, Outcome, Scope, Page, Manifest).

## Commands

```bash
python -m pip install -e ".[dev]"        # install package + dev deps
python -m playwright install chromium    # required for render/e2e tests
pytest -q                                # run the test suite
getdocs crawl https://example.com/docs -o ./out   # run a Crawl
getdocs serve                            # run the API service (needs ".[server]")
claude plugin validate . --strict        # validate plugin/marketplace manifests
```

## Architecture

Layered, CLI-first (ADR-0001). Source in `src/getdocs/`:
- **Deep modules** (pure logic): `extract`, `scope`, `source`, `navharvest`,
  `sitemap`, `urlnorm`, `output`, `outcome`, `identity`.
- **`engine.py`** — thin Scrapy glue over the deep modules.
- **`cli.py`** (`crawl`/`serve`) and **`api.py`** (FastAPI) — entry surfaces over
  the same engine; `config.py` (`CrawlConfig`) is the engine boundary.
- **`jobs.py`** — runs Crawls as subprocesses (ADR-0002).

## Agent skills

### Issue tracker

Issues are tracked on GitHub (jonbakerfish/getdocs) via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
