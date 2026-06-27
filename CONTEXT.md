# getdocs

A documentation crawler: given one or more seed URLs, it recursively discovers and scrapes every reachable page in scope, returning clean markdown or structured data per page.

## Language

**Crawl**:
One traversal job that starts from Seed URLs and fetches every Page allowed by its Scope.
_Avoid_: scrape (that's a single page), spider run, job (reserved for the future API layer)

**Outcome**:
What a single getdocs run produces — exactly one of a Crawl or a Clone.
_Avoid_: result, output

**Clone**:
The source-repo result when the docs site is open-source — a cloned repository plus a generated serve config — produced instead of a Crawl. Yields no Pages and no Manifest.
_Avoid_: download, mirror, checkout

**Seed URL**:
A starting URL the user provides to a Crawl.
_Avoid_: root URL, entry point

**Scope**:
The rule deciding whether a discovered URL belongs to a Crawl; by default, same host + path prefix of the Seed URL.
_Avoid_: domain filter, boundary

**Page**:
One URL successfully fetched and extracted within a Crawl.
_Avoid_: document, result, item

**Manifest**:
The per-Crawl summary record (seeds, scope, counts, errors) written alongside the Pages.
_Avoid_: index, report

**Shell**:
A fetched response that is an unhydrated client-side app frame rather than real content; triggers render escalation.
_Avoid_: empty page, SPA page

**Asset**:
A file a Page references rather than links to as documentation — an image, document download, or video; fetched (optionally) by media download, never converted to markdown.
_Avoid_: attachment, resource, media file (use Asset in code; "media" only in flag names)

**Nav Order**:
The tree of in-Scope Page links — labels, grouping, nesting — as presented by the original site's header and sidebar navigation, recorded in the Manifest.
_Avoid_: sidebar structure, nav map

**Reading Order**:
The linear sequence of Pages matching how a reader would traverse the original site; prev/next link chains are authoritative, falling back to Nav Order traversal, then crawl order.
_Avoid_: page order (ambiguous with crawl order), webpage order

## Relationships

- A getdocs run produces exactly one **Outcome**: a **Crawl** or a **Clone**
- A **Clone** bypasses traversal, so it has no **Scope**, **Pages**, or **Manifest**; it is *not* a Crawl
- A **Crawl** has one or more **Seed URLs** and exactly one **Scope**
- A **Crawl** produces zero or more **Pages** and exactly one **Manifest**
- A **Scope** is derived from the **Seed URLs** plus user overrides (backward, subdomains, path globs)
- A **Manifest** carries the Crawl's **Nav Order** and **Reading Order**; Pages absent from every signal follow in crawl order
- A **Page** references zero or more **Assets**; **Scope** gates Pages, never Assets (Assets may live off-host)

## Example dialogue

> **Dev:** "If the sitemap lists a URL outside the path prefix, does the **Crawl** fetch it?"
> **Domain expert:** "No — the **Scope** applies to every discovered URL regardless of how it was discovered. Sitemap discovery widens *finding*, never *fetching*."

## Flagged ambiguities

- The PROMPT uses "getdocs" for both a CLI tool and an API service — resolved: it is a layered system; the crawl engine + CLI ship first, the API service wraps the same engine later. Agent integration is the CLI run as a background task by the agent's own harness, not a new surface — it produces the same Outcome (Crawl or Clone).
- The `crawl` command can produce a **Clone**, not a Crawl, when source-first detection finds the docs' public repo — resolved: the command name reflects intent ("get me these docs"), not the mechanism; a run yields one **Outcome**, and Clone is a sibling of Crawl, never a kind of Crawl.
