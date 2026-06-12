# Assets are exempt from Scope

Scope gates which Pages a Crawl fetches. Assets (images, document downloads) referenced by in-Scope Pages routinely live off-host on CDNs, so when `--download-media` is enabled, Asset fetches deliberately bypass `scope.allows()` — applying Page Scope to Assets would make media download useless on most real sites. This mirrors normal browser behavior: one throttled GET per referenced asset. Do not "fix" the bypassed scope check for Asset requests; Scope's contract is Pages only (see CONTEXT.md).
