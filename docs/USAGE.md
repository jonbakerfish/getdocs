# getdocs usage

`getdocs` crawls a documentation site and emits clean markdown — one file per
page, or a structured JSONL stream.

## Install

```bash
conda create -n getdocs python=3.12 pip
conda run -n getdocs python -m pip install -e .

# Optional but recommended: the headless browser used for JS rendering
conda run -n getdocs playwright install chromium
```

## Quickstart

```bash
getdocs crawl https://example.com/docs -o ./out
```

This recursively crawls every page under `/docs` on `example.com` and writes:

```
out/
├── crawl.json            ← the Manifest: what the Crawl did
└── docs/
    ├── index.md
    ├── auth.md
    └── guide/
        └── intro.md
```

Each `.md` file mirrors its URL path and starts with YAML frontmatter:

```markdown
---
url: https://example.com/docs/auth
title: Authentication
status: 200
crawled_at: 2026-06-12T10:00:00Z
canonical: https://example.com/docs/latest/auth   # only when the page declares one
---

# Authentication
...
```

## What gets crawled (Scope)

By default a Crawl is limited to the **same host and path prefix** as the seed
URL: seeding `example.com/docs/v2` crawls `…/docs/v2/**` and nothing else — not
the blog, not subdomains, never external sites. Pages are discovered both by
following links and from sitemaps (robots.txt-declared and `/sitemap.xml`),
but Scope gates fetching regardless of how a URL was found.

| Flag | Effect |
|------|--------|
| `--allow-backward` | Widen Scope to the seed's whole host |
| `--allow-subdomains` | Also crawl subdomains of the seed host |
| `--include-paths GLOB` | Only crawl matching paths (repeatable) |
| `--exclude-paths GLOB` | Never crawl matching paths (repeatable) |
| `--depth N` | Limit link-hops from any seed (sitemap URLs count as seeds) |
| `--limit N` | Max pages per Crawl (default 1000, `0` = unlimited) |
| `--no-sitemap` / `--sitemap-only` | Force link-only or sitemap-only discovery |

Multiple seed URLs are allowed: `getdocs crawl URL1 URL2 -o ./out`, or keep
them in a file (one per line; blank lines and `#` comments ignored) with
`-f`/`--seeds-file urls.txt` — positional URLs and file URLs combine.

## Output formats

- **`--format files`** (default) — the `.md` tree shown above plus `crawl.json`.
- **`--format jsonl`** — one JSON record per page on stdout, ending with a
  manifest record. Suited for piping into other tools:

  ```bash
  getdocs crawl https://example.com/docs --format jsonl | jq -r 'select(.type=="page") | .title'
  ```

- **`--keep-html`** — also keep each page's raw HTML (a `.html` sidecar in
  files mode, an `html` field in jsonl mode).

### The Manifest (`crawl.json` / final jsonl record)

```json
{
  "seeds": ["https://example.com/docs"],
  "page_count": 42,
  "errors":  [{"url": "…/gone", "status": 404, "reason": "HTTP 404"}],
  "skipped": [{"url": "…/private", "reason": "robots.txt"}],
  "shells":  ["…/app"],
  "truncated": false
}
```

- `errors` — pages that failed after retries (5xx/timeouts retry twice; 404s
  are not retried). Page errors never abort a Crawl.
- `skipped` — pages robots.txt told us not to fetch.
- `shells` — pages written as unhydrated app frames because rendering was off.
- `truncated` — `true` when `--limit` stopped the Crawl early.

Exit code is `0` for any completed Crawl (even with page errors), non-zero
only when nothing could be crawled at all.

## Markdown extraction

The content container is found by trying, in order: your `--selector`, the
known containers of common docs generators (Docusaurus, MkDocs Material,
Sphinx, GitBook, Mintlify), then semantic elements (`<main>`, `<article>`,
`[role=main]`). Navigation, sidebars, breadcrumbs, and footers are stripped;
code blocks keep their language hints; tables convert to markdown tables.
Pages with no recognizable container fall back to readability extraction.

```bash
getdocs crawl https://internal.docs/ -o ./out --selector "#main-content"
```

## JavaScript rendering

Some docs sites ship an empty shell and render client-side. `--render`
controls how that's handled:

- **`auto`** (default) — every page is fetched plain first; a detected shell
  is re-fetched through headless Chromium. After two shells on one host, the
  whole host switches to browser fetching.
- **`always`** — everything goes through the browser (slow, maximum fidelity).
- **`never`** — no browser; shells are written as-is and listed under
  `shells` in the Manifest.

Rendering requires `playwright install chromium`; without it, `auto` degrades
to `never` with a note on stderr.

## Politeness

getdocs is a polite crawler by default: adaptive throttling (1s start delay,
adapting to server latency), 4 concurrent requests per domain, robots.txt
obeyed, and `429 Too Many Requests` retried no sooner than the server's
`Retry-After` asks.

| Flag | Effect |
|------|--------|
| `--delay SECONDS` | Throttle start delay (default 1.0; `0` disables throttling) |
| `--concurrency N` | Concurrent requests per domain (default 4) |
| `--ignore-robots` | Consciously override robots.txt |

## Interrupting and resuming

Crawl state is saved in `<output-dir>/.getdocs/` whenever a Crawl stops —
Ctrl-C, a `--limit` cap, or completion. To continue where it left off:

```bash
getdocs crawl --resume -o ./out      # seeds are reused from the saved state
```

Already-written pages are not re-fetched, `--limit` spans the combined runs,
and the final Manifest reflects the whole Crawl. Resume is always explicit:
running *without* `--resume` against a directory holding old state announces
it is starting over.

## API service

For programmatic use, getdocs ships a Firecrawl-style async API:

```bash
pip install "getdocs[server]"
getdocs serve --host 127.0.0.1 --port 8000
```

- `POST /v1/crawl` — body `{"url": "...", ...}` (or `"urls": [...]`) accepting
  the same options as the CLI flags (`limit`, `depth`, `allow_backward`,
  `include_paths`, `render`, `selector`, `delay`, …) plus an optional
  `"webhook"` URL. Returns `{"id": ..., "status": "running"}` immediately.
  Each job runs the CLI as a subprocess and consumes its JSONL stream.
- `GET /v1/crawl/{id}` — poll a job: status (`running` / `completed` /
  `failed` / `cancelled`), pages so far, and the Manifest once done.
- `GET /v1/crawl` — list all jobs (summaries).
- `DELETE /v1/crawl/{id}` — cancel a running job; partial results are kept.
- `WS /v1/crawl/{id}/ws` — stream events live: pages already produced are
  replayed first, then live page events, ending with the Manifest.
- **Webhooks** — when a `webhook` URL is given, the service POSTs
  `{"event": "started"}`, one `{"event": "page", "page": {...}}` per page,
  and `{"event": "completed", "manifest": {...}}`. Delivery failures are
  retried a few times and reported as `webhook_failures` on the job — they
  never affect the Crawl itself.

## All options

Run `getdocs crawl --help` for the authoritative list.
