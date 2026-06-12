import subprocess
import sys


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def build_site_with_sitemap(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/auth">Auth</a>'))
    site.add("/docs/auth", page("Auth", "<h1>Auth</h1>"))
    # Reachable only through the sitemap; links one hop further.
    site.add("/docs/hidden", page("Hidden", '<h1>Hidden</h1><a href="/docs/deep">Deep</a>'))
    site.add("/docs/deep", page("Deep", "<h1>Deep</h1>"))
    site.add("/blog/secret", page("Secret", "<h1>Out of scope</h1>"))
    site.add("/robots.txt", f"Sitemap: {site.url}/sitemap-index.xml\n")
    site.add("/sitemap-index.xml", f"""<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{site.url}/sitemap-pages.xml</loc></sitemap>
</sitemapindex>""")
    site.add("/sitemap-pages.xml", f"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{site.url}/docs/hidden</loc></url>
  <url><loc>{site.url}/blog/secret</loc></url>
</urlset>""")


def run_crawl(site, tmp_path, *extra):
    result = subprocess.run(
        [sys.executable, "-m", "getdocs", "crawl", f"{site.url}/docs/", "-o", str(tmp_path),
         "--delay", "0", *extra],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.md"))


def test_sitemap_page_unreachable_by_links_is_crawled_by_default(site, tmp_path):
    build_site_with_sitemap(site)

    files = run_crawl(site, tmp_path)

    assert "docs/hidden.md" in files  # found via robots → index → urlset chain
    assert "blog/secret.md" not in files  # sitemap widens finding, never fetching


def test_no_sitemap_skips_sitemap_discovery(site, tmp_path):
    build_site_with_sitemap(site)

    files = run_crawl(site, tmp_path, "--no-sitemap")

    assert "docs/hidden.md" not in files
    assert "docs/auth.md" in files


def test_sitemap_only_fetches_exactly_in_scope_sitemap_urls(site, tmp_path):
    build_site_with_sitemap(site)

    files = run_crawl(site, tmp_path, "--sitemap-only")

    assert files == ["docs/hidden.md"]  # no seed fetch, no link following


def test_depth_does_not_exclude_sitemap_discovered_pages(site, tmp_path):
    build_site_with_sitemap(site)

    files = run_crawl(site, tmp_path, "--depth", "1")

    assert "docs/hidden.md" in files  # depth-0 seed despite discovery chain
    assert "docs/deep.md" in files  # one hop from a sitemap seed
