import time

from fastapi.testclient import TestClient

from getdocs.api import create_app


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def poll_until_done(client, job_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/v1/crawl/{job_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish in time")


def test_crawl_job_via_post_and_polling(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/a">A</a><a href="/docs/b">B</a>'))
    site.add("/docs/a", page("A", "<h1>A</h1>"))
    site.add("/docs/b", page("B", "<h1>B</h1>"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/crawl", json={"url": f"{site.url}/docs/", "delay": 0, "limit": 2}
        )
        assert response.status_code == 202
        job_id = response.json()["id"]

        body = poll_until_done(client, job_id)

    assert body["status"] == "completed"
    assert body["page_count"] == 2
    assert len(body["pages"]) == 2
    assert all(p["markdown"] for p in body["pages"])
    assert body["manifest"]["truncated"] is True  # the limit option reached the subprocess


def test_unknown_job_id_is_404(site):
    with TestClient(create_app()) as client:
        assert client.get("/v1/crawl/nope").status_code == 404


def test_failed_crawl_reports_failed_status(site):
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/crawl", json={"url": "http://127.0.0.1:1/none", "delay": 0}
        )
        body = poll_until_done(client, response.json()["id"])

    assert body["status"] == "failed"
    assert body["error"]


def test_crawl_requires_a_url(site):
    with TestClient(create_app()) as client:
        assert client.post("/v1/crawl", json={"limit": 5}).status_code == 422
