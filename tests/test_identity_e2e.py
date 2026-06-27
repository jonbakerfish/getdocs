"""End-to-end: the running crawler identifies itself as getdocs, not Scrapy."""

import subprocess
import sys

PAGE = "<html><body><h1>Home</h1></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0", "--no-clone-source"],
        capture_output=True, text=True, timeout=120,
    )


def test_crawl_sends_getdocs_user_agent(site, tmp_path):
    site.add("/docs/", PAGE)

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert site.user_agents, "no requests reached the site"
    # Every request identifies as getdocs (not the default Scrapy UA).
    assert all(ua.startswith("getdocs/") for ua in site.user_agents), site.user_agents
    assert not any("Scrapy" in ua for ua in site.user_agents)


def test_contact_flag_reaches_the_server(site, tmp_path):
    site.add("/docs/", PAGE)

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--contact", "me@example.com"
    )

    assert result.returncode == 0, result.stderr
    assert all("me@example.com" in ua for ua in site.user_agents), site.user_agents


def test_user_agent_override_is_sent_verbatim(site, tmp_path):
    site.add("/docs/", PAGE)

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--user-agent", "AcmeBot/2.0"
    )

    assert result.returncode == 0, result.stderr
    assert all(ua == "AcmeBot/2.0" for ua in site.user_agents), site.user_agents
