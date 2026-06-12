# getdocs

A documentation crawler: given one or more seed URLs, it recursively discovers and scrapes every reachable page in scope, returning clean markdown or structured data per page.

## Language

**Crawl**:
One traversal job that starts from Seed URLs and fetches every Page allowed by its Scope.
_Avoid_: scrape (that's a single page), spider run, job (reserved for the future API layer)

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

## Relationships

- A **Crawl** has one or more **Seed URLs** and exactly one **Scope**
- A **Crawl** produces zero or more **Pages** and exactly one **Manifest**
- A **Scope** is derived from the **Seed URLs** plus user overrides (backward, subdomains, path globs)

## Example dialogue

> **Dev:** "If the sitemap lists a URL outside the path prefix, does the **Crawl** fetch it?"
> **Domain expert:** "No — the **Scope** applies to every discovered URL regardless of how it was discovered. Sitemap discovery widens *finding*, never *fetching*."

## Flagged ambiguities

- The PROMPT uses "getdocs" for both a CLI tool and an API service — resolved: it is a layered system; the crawl engine + CLI ship first, the API service wraps the same engine later.
