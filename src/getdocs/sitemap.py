"""Sitemap parsing: urlsets, sitemap indexes, and robots.txt Sitemap lines.

Discovery only — Scope decides what actually gets fetched.
"""

import xml.etree.ElementTree as ET


def parse_sitemap_xml(body: str) -> tuple[list[str], list[str]]:
    """Returns (page_urls, nested_sitemap_urls)."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []

    tag = root.tag.rpartition("}")[2]
    locs = [
        loc.text.strip()
        for loc in root.iter()
        if loc.tag.rpartition("}")[2] == "loc" and loc.text and loc.text.strip()
    ]
    if tag == "urlset":
        return locs, []
    if tag == "sitemapindex":
        return [], locs
    return [], []


def parse_robots_sitemaps(robots_txt: str) -> list[str]:
    sitemaps = []
    for line in robots_txt.splitlines():
        key, _, value = line.partition(":")
        if key.strip().lower() == "sitemap" and value.strip():
            sitemaps.append(value.strip())
    return sitemaps
