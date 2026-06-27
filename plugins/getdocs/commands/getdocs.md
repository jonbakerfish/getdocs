---
description: Fetch a documentation site into the workspace as clean local markdown (via the getdocs CLI). Pass the docs URL.
argument-hint: <docs-url>
---

# /getdocs — fetch documentation as local markdown

You are wiring the [getdocs](https://github.com/jonbakerfish/getdocs) CLI into
this session to pull documentation into the workspace as clean markdown you (and
the user) can grep and read. getdocs does all the crawling/cloning — your job is
to invoke it correctly and act on what it produced.

The docs URL to fetch is: **$ARGUMENTS**

## How to run it

Invoke getdocs through `uvx` so nothing has to be installed first, and pin a
version new enough to emit the machine-readable summary this command relies on:

```bash
uvx --from "getdocs>=0.2.0" getdocs crawl "$ARGUMENTS" -o ./getdocs-out --summary-json --limit 200
```

- Run it **synchronously** (block on it). This is for fetching a specific docs
  section, which getdocs bounds by Scope (same host + the URL's path prefix); a
  modest `--limit` keeps an over-wide crawl in check.
- Do **not** pass `--ignore-robots`. getdocs honors robots.txt, throttles
  politely, and identifies itself honestly by default — keep it that way.
- `--summary-json` makes getdocs print one JSON object describing the **Outcome**
  to stdout (files mode). Capture and parse it.

## Act on the Outcome

The summary's `outcome` field tells you what getdocs produced — branch on it:

- **`"crawled"`** — getdocs scraped the rendered site into a Pages tree.
  - Read `output_dir` and `manifest` (the `crawl.json` Manifest) from the summary.
  - Grep / read the `.md` Pages under `output_dir` to ground your answer in the
    real docs; follow the nav order and reading order recorded in the Manifest.
  - If `status` is `"truncated"` (or `truncated` is `true`), the crawl hit its
    page cap — tell the user it's incomplete and offer to re-run with a higher
    `--limit` (or `--limit 0` for unlimited).
- **`"cloned"`** — the docs were open-source, so getdocs cloned the repo instead
  (a Clone has no Pages and no Manifest).
  - Read `repo`, `output_dir`, and `mkdocs_config` from the summary.
  - You have the original markdown source: read it directly under `output_dir`,
    and offer to serve it locally with `mkdocs serve -f <mkdocs_config>`.
- **`status: "empty"`** — getdocs produced no Pages (seed unreachable?) and exits
  non-zero. Report that and suggest checking the URL.

Finally, tell the user which docs you fetched and where they landed so they can
find them alongside their code.
