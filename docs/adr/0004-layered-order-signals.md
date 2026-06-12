# Reading order comes from layered signals, not one source

The original site's reading order is captured from three signals, each authoritative for what it does best: header tabs + sidebar navigation build the Nav Order tree (grouping, labels, nesting; largest harvested sidebar as skeleton, first-seen branch merge across pages); prev/next footer link chains are authoritative for the linear Reading Order and splice pages the tree missed; fallbacks are tree traversal, then crawl order. One source alone fails predictably — sidebars can be section-scoped (Sphinx) or collapsed/virtualized, tabbed themes move top-level grouping into the header, and chains carry no hierarchy. Both artifacts live in the Manifest; file names keep mirroring URL paths regardless.

## Considered Options

- Sidebar tree only — rejected: misses header-tab grouping and collapsed-section children.
- Prev/next chain only — rejected: perfect sequence but no grouping or labels.
- Crawl-order approximation (status quo) — rejected: concurrency, sitemap seeding, and retries shuffle it.
