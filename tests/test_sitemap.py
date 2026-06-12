from getdocs.sitemap import parse_robots_sitemaps, parse_sitemap_xml

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/docs/auth</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://example.com/docs/hidden</loc></url>
</urlset>"""

SITEMAPINDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-docs.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-blog.xml</loc></sitemap>
</sitemapindex>"""


def test_urlset_yields_page_urls():
    pages, sitemaps = parse_sitemap_xml(URLSET)

    assert pages == ["https://example.com/docs/auth", "https://example.com/docs/hidden"]
    assert sitemaps == []


def test_sitemapindex_yields_nested_sitemap_urls():
    pages, sitemaps = parse_sitemap_xml(SITEMAPINDEX)

    assert pages == []
    assert sitemaps == [
        "https://example.com/sitemap-docs.xml",
        "https://example.com/sitemap-blog.xml",
    ]


def test_invalid_xml_yields_nothing():
    assert parse_sitemap_xml("<html>not a sitemap</html>") == ([], [])
    assert parse_sitemap_xml("garbage <<<") == ([], [])


def test_robots_txt_sitemap_lines():
    robots = """User-agent: *
Disallow: /private/
Sitemap: https://example.com/sitemap-index.xml
sitemap: https://example.com/other.xml
"""
    assert parse_robots_sitemaps(robots) == [
        "https://example.com/sitemap-index.xml",
        "https://example.com/other.xml",
    ]
