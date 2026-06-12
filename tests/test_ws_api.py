import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from getdocs.api import create_app


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def build_docs_site(site):
    site.add("/docs/", page("Home", '<h1>Home</h1><a href="/docs/a">A</a><a href="/docs/b">B</a>'))
    site.add("/docs/a", page("A", "<h1>A</h1>"))
    site.add("/docs/b", page("B", "<h1>B</h1>"))


def collect_events(ws):
    events = []
    while True:
        try:
            events.append(ws.receive_json())
        except WebSocketDisconnect:
            return events


def test_live_stream_delivers_every_page_then_manifest(site):
    build_docs_site(site)

    with TestClient(create_app()) as client:
        job_id = client.post(
            "/v1/crawl", json={"url": f"{site.url}/docs/", "delay": 0.2}
        ).json()["id"]

        with client.websocket_connect(f"/v1/crawl/{job_id}/ws") as ws:
            events = collect_events(ws)

    pages = [e for e in events if e["type"] == "page"]
    assert {p["title"] for p in pages} == {"Home", "A", "B"}
    assert events[-1]["type"] == "manifest"
    assert events[-1]["page_count"] == 3


def test_connecting_after_completion_replays_everything(site):
    build_docs_site(site)

    with TestClient(create_app()) as client:
        job_id = client.post(
            "/v1/crawl", json={"url": f"{site.url}/docs/", "delay": 0}
        ).json()["id"]
        # wait for completion via polling first
        import time
        while client.get(f"/v1/crawl/{job_id}").json()["status"] == "running":
            time.sleep(0.05)

        with client.websocket_connect(f"/v1/crawl/{job_id}/ws") as ws:
            events = collect_events(ws)

    assert len([e for e in events if e["type"] == "page"]) == 3
    assert events[-1]["type"] == "manifest"


def test_unknown_job_closes_with_error_code(site):
    with TestClient(create_app()) as client:
        with client.websocket_connect("/v1/crawl/nope/ws") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()

    assert exc.value.code == 4404
