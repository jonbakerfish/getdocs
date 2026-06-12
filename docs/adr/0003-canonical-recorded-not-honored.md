# rel=canonical is recorded in Page metadata but never used for dedup

Frontier dedup uses normalized URLs (fragments and tracking params stripped, slashes normalized) and redirect targets only. Honoring `rel=canonical` looks like an obvious dedup improvement, but versioned docs sites canonicalize `/v1/x` and `/v2/x` to `/latest/x` — following it would silently collapse pages the user explicitly scoped. The canonical URL is captured in each Page's frontmatter so consumers can dedupe downstream if they choose. Do not "fix" dedup by acting on it.
