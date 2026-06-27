# getdocs

**Turn any documentation site into a clean, local markdown copy your coding agent can actually read.**

```bash
getdocs crawl https://example.com/docs -o ./out
```

Coding agents are only as good as the docs they can see. Pointing an agent at a
live docs URL means it burns tokens on nav bars, cookie banners, and HTML
chrome — or can't reach the page at all. `getdocs` gives the agent a local,
offline, markdown mirror instead: the actual content, structured to match the
original site, ready to drop into a repo or feed to a model.

## Why getdocs

- **Richer context for coding agents.** A local copy is greppable, indexable,
  and always available — the agent reads the whole library at once instead of
  fetching one rendered page at a time. No rate limits, no network flakiness,
  no JS that won't hydrate.
- **Clean markdown → fewer tokens.** Each page is reduced to its content (the
  nav, headers, footers, and ad chrome stripped) and written as plain markdown.
  Agents consume it directly, and you spend tokens on docs, not `<div>` soup.
- **Structure preserved.** Files mirror the URL hierarchy
  (`example.com/docs/auth` → `out/docs/auth.md`), each with YAML frontmatter
  (`url`, `title`, `crawled_at`, `status`), plus a `crawl.json` Manifest that
  captures the site's nav order and reading order — so an agent can follow the
  docs in the order the authors intended.
- **Source-first: clone over crawl.** If the docs site is open-source, getdocs
  detects the "Edit this page" link, clones the repo, and serves you the
  original markdown source instead of scraping HTML — the highest-fidelity copy
  there is. Falls back to crawling automatically when there's no repo.

## When to reach for it

- **Coding against an unfamiliar library or API.** Mirror its docs into your
  repo (or a scratch dir) so your agent can ground its answers in the real
  reference instead of hallucinating from memory.
- **RAG / knowledge bases.** Get a clean markdown corpus to chunk and embed,
  without writing a bespoke scraper-and-cleaner for every site.
- **Offline or air-gapped work.** Take a docs set with you; read and search it
  with no network.
- **Pinning a version.** Snapshot today's docs so your agent isn't tripped up
  when the upstream site changes underneath you.
- **Migrating or archiving docs.** Pull an entire site down as markdown to move,
  diff, or keep.

## Output

```
out/
├── crawl.json            ← the Manifest: nav order, reading order, what ran
└── docs/
    ├── index.md
    ├── auth.md
    └── guide/
        └── intro.md
```

```markdown
---
url: https://example.com/docs/auth
title: Authentication
status: 200
crawled_at: 2026-06-12T10:00:00Z
---

# Authentication
...
```

Sitemap discovery, JavaScript rendering, source-repo cloning, polite
throttling, JSONL output, and resumable crawls are all built in — see
[docs/USAGE.md](docs/USAGE.md).

## Use with your agent

getdocs is built to be driven by a coding agent: it's an ordinary CLI whose
`out/` tree + `crawl.json` Manifest *is* the return value (no MCP server, no job
protocol — see [ADR-0007](docs/adr/0007-agent-integration-is-the-cli-not-an-mcp-surface.md)).
If your agent is **Claude Code**, the [one-step plugin](#claude-code-plugin-one-step-install)
below wires this up for you; **any other agent** drives the CLI directly.

### Claude Code plugin (one-step install)

getdocs ships a Claude Code plugin that adds a `/getdocs` command — no Python
install needed. The getdocs repository doubles as the plugin marketplace:

```bash
# 1. Add this repo as a plugin marketplace
claude plugin marketplace add jonbakerfish/getdocs

# 2. Install the plugin
claude plugin install getdocs@getdocs
```

Then, inside Claude Code:

```
/getdocs https://example.com/docs/auth
```

Your only prerequisite is [`uv`](https://docs.astral.sh/uv/) on your `PATH`: the
command runs getdocs through `uvx`, so getdocs itself is fetched on demand and
there's nothing to `pip install`. It picks the mode for you — a bounded
**synchronous** run for a specific docs section, or a **background** run for a
whole-site mirror (which Claude Code resumes on completion) — reads the Outcome
summary, then points you at the Pages to grep (a Crawl) or offers to serve the
docs (a Clone).

Update or remove it later with:

```bash
claude plugin uninstall getdocs@getdocs     # remove the plugin
claude plugin marketplace remove getdocs    # forget the marketplace
```

### Drive the CLI directly (any agent)

Two patterns cover most uses.

**Synchronous — fetch one docs section.** Scope defaults to the seed's host +
path prefix, so pointing at a subtree fetches just that subtree. This blocks
until done and works under any agent:

```bash
getdocs crawl https://example.com/docs/auth -o ./out --summary-json
```

**Background — mirror a whole site.** Kick the crawl off as a background task
and keep working. Under **Claude Code** the agent is resumed automatically when
the crawl finishes; every other agent surveyed blocks or polls the output path
instead (this is a harness feature, not a getdocs one):

```bash
getdocs crawl https://example.com/docs -o ./out --summary-json &
```

**Read the summary, branch on the Outcome.** Every run ends with a one-line
summary on stderr; `--summary-json` adds a machine-readable object discriminated
by `outcome`. A run produces exactly one Outcome — a Crawl or a Clone:

```jsonc
// outcome: "crawled" — getdocs scraped the rendered site
{ "outcome": "crawled", "status": "ok", "pages": 42,
  "output_dir": "./out", "manifest": "./out/crawl.json", "truncated": false }

// outcome: "cloned" — the docs were open-source, so getdocs cloned the repo
// (no pages / no manifest: a Clone is not a Crawl)
{ "outcome": "cloned", "status": "ok", "repo": "acme/docs",
  "output_dir": "./out/docs", "mkdocs_config": "./out/mkdocs.yml" }
```

Have the agent switch on `outcome`:

- **`crawled`** → grep and read the Pages under `output_dir` and follow the nav
  / reading order in `manifest` (`crawl.json`).
- **`cloned`** → you have the original markdown source; serve it with
  `mkdocs serve -f <mkdocs_config>` (or just read the files under `output_dir`).
- **`status: "truncated"`** → the crawl hit its page cap; re-run with a higher
  `--limit` (or `0` for unlimited) to get the rest.

## Install

Requires **Python 3.12+**.

```bash
pip install getdocs
```

Or from source, for the latest unreleased changes:

```bash
git clone https://github.com/jonbakerfish/getdocs
cd getdocs
pip install -e .
```

That's enough to crawl. Two optional pieces unlock more:

```bash
# JavaScript rendering — the headless browser used to hydrate SPA docs
playwright install chromium

# Serve a crawled/cloned copy locally as a browsable site
pip install mkdocs mkdocs-material
```

**`git`** must be on your `PATH` for source-first cloning (it almost always
already is); without it, getdocs simply falls back to crawling. To run the
optional API service, install the server extra: `pip install "getdocs[server]"`.

## Development

```bash
git clone https://github.com/jonbakerfish/getdocs
cd getdocs
pip install -e ".[dev]"
pytest
```

## Responsible use

getdocs is a tool; how you point it is on you. By default it **honors
`robots.txt`**, throttles itself politely, and **identifies itself honestly**
in the `User-Agent` (`getdocs/<version> (+project-url)`) — please keep it that
way. For high-volume crawls, add `--contact you@example.com` so site operators
can reach you (it's appended to the User-Agent; optional but courteous).

getdocs is intended for personal, reference, and agent/RAG use on documentation
you have the right to access. **You are solely responsible for complying with
each site's Terms of Service, its `robots.txt`, applicable law, and the
copyright of the content you fetch** — getdocs is provided as-is, with no
warranty (see [LICENSE](LICENSE)). Crawled documentation belongs to its authors:
use it for your own reference, but don't redistribute someone else's docs as
your own. Crawl only what you have the right to.
