---
name: getdocs
description: Crawl and scrape a documentation site into the workspace as clean local markdown (via the getdocs CLI). Use when the user wants to fetch, mirror, crawl, or scrape the docs for a library/API/framework so the agent can read them locally.
---

# getdocs — fetch documentation as local markdown

Use this skill when the user wants documentation pulled into the workspace as
clean local markdown they (and you) can grep and read — e.g. "get me the docs
for X", "mirror these docs", "crawl/scrape this docs site".

[getdocs](https://github.com/jonbakerfish/getdocs) does all the crawling and
cloning — your job is to invoke it correctly and act on what it produced.

## How to run it

Run getdocs through `uvx` so nothing has to be installed first, and pin a version
new enough to emit the machine-readable summary this skill relies on. Never pass
`--ignore-robots`: getdocs honors robots.txt, throttles politely, and identifies
itself honestly by default — keep it that way.

Pick a mode from what the user wants, and tell them which you chose and why:

- **Synchronous — a docs section** (default; works under any agent). The URL
  points at a specific part of the docs, or the user wants "just these docs".
  getdocs bounds the crawl by Scope (same host + the URL's path prefix); a modest
  `--limit` keeps an over-wide crawl in check. Block on it:

  ```bash
  uvx --from "getdocs>=0.2.0" getdocs crawl "<docs-url>" -o ./getdocs-out --summary-json --limit 200
  ```

- **Background — a whole-site mirror.** The user wants to mirror an entire docs
  site. Run it as a background task so the user can keep working. Under **Claude
  Code** you are resumed automatically when it finishes; other agents block or
  must poll, so prefer synchronous there.

  ```bash
  uvx --from "getdocs>=0.2.0" getdocs crawl "<docs-url>" -o ./getdocs-out --summary-json &
  ```

`--summary-json` makes getdocs print one JSON object describing the **Outcome**
to stdout (files mode). Capture and parse it.

## Act on the Outcome

Branch on the summary's `outcome` field:

- **`"crawled"`** — getdocs scraped the rendered site into a Pages tree. Read
  `output_dir` and `manifest` (the `crawl.json` Manifest); grep/read the `.md`
  Pages and follow the nav / reading order in the Manifest. If `status` is
  `"truncated"` (or `truncated` is `true`), it hit the page cap — tell the user
  it's incomplete and offer to re-run with a higher `--limit` (or `0` for
  unlimited).
- **`"cloned"`** — the docs were open-source, so getdocs cloned the repo instead
  (a Clone has no Pages and no Manifest). Read `repo`, `output_dir`, and
  `mkdocs_config`; read the source under `output_dir` and offer to serve it with
  `mkdocs serve -f <mkdocs_config>`.
- **`status: "empty"`** — getdocs produced no Pages (seed unreachable?) and exits
  non-zero. Report that and suggest checking the URL.

Finally, tell the user which docs you fetched and where they landed so they can
find them alongside their code.
