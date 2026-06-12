import time

from fastapi.testclient import TestClient

from getdocs.api import create_app


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def build_docs_site(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/a">A</a>'))
    site.add("/docs/a", page("A", "<h1>A</h1>"))


def run_crawl_with_webhook(client, site):
    job_id = client.post(
        "/v1/crawl",
        json={"url": f"{site.url}/docs/", "delay": 0, "webhook": f"{site.url}/hook"},
    ).json()["id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        body = client.get(f"/v1/crawl/{job_id}").json()
        if body["status"] != "running" and (
            site.posts and site.posts[-1][1].get("event") == "completed"
            or body["webhook_failures"]
        ):
            return body
        time.sleep(0.1)
    raise AssertionError("job/webhooks did not finish in time")


def test_webhook_receives_started_pages_and_completed(site):
    build_docs_site(site)

    with TestClient(create_app()) as client:
        body = run_crawl_with_webhook(client, site)

    assert body["status"] == "completed"
    events = [payload["event"] for path, payload in site.posts if path == "/hook"]
    assert events[0] == "started"
    assert events.count("page") == 2
    assert events[-1] == "completed"

    completed = site.posts[-1][1]
    assert completed["manifest"]["page_count"] == 2
    assert body["webhook_failures"] == 0


def test_failing_webhook_does_not_fail_the_crawl(site):
    build_docs_site(site)
    site.post_status["/hook"] = 500

    with TestClient(create_app()) as client:
        body = run_crawl_with_webhook(client, site)

    assert body["status"] == "completed"  # crawl unaffected
    assert body["page_count"] == 2
    assert body["webhook_failures"] > 0  # but the failures are visible
