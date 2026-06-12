"""Shared fixture site: a local HTTP server serving a dict of routes.

Each route maps a path to either an HTML string (served as 200 text/html)
or a (status, headers) tuple for redirects and errors. Later slices extend
this site with a sitemap, error endpoints, an SPA shell, and robots.txt.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _Binary:
    def __init__(self, data: bytes, content_type: str):
        self.data = data
        self.content_type = content_type


class _Flaky:
    """Returns an error status for the first fail_times requests, then HTML."""

    def __init__(self, html: str, fail_times: int, status: int, headers: dict | None = None):
        self.html = html
        self.remaining_failures = fail_times
        self.status = status
        self.headers = headers or {}


class FixtureSite:
    def __init__(self):
        self.routes: dict[str, object] = {}
        self.hits: dict[str, int] = {}
        self.hit_times: dict[str, list[float]] = {}
        self.posts: list[tuple[str, dict | None]] = []
        self.post_status: dict[str, int] = {}
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                site.hits[self.path] = site.hits.get(self.path, 0) + 1
                site.hit_times.setdefault(self.path, []).append(time.monotonic())
                route = site.routes.get(self.path)
                if isinstance(route, _Flaky):
                    if route.remaining_failures > 0:
                        route.remaining_failures -= 1
                        self.send_response(route.status)
                        for name, value in route.headers.items():
                            self.send_header(name, value)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    route = route.html
                if isinstance(route, _Binary):
                    self.send_response(200)
                    self.send_header("Content-Type", route.content_type)
                    self.send_header("Content-Length", str(len(route.data)))
                    self.end_headers()
                    self.wfile.write(route.data)
                elif route is None:
                    self.send_error(404)
                elif isinstance(route, tuple):
                    status, headers = route
                    self.send_response(status)
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.end_headers()
                else:
                    body = route.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                site.posts.append((self.path, json.loads(body) if body else None))
                self.send_response(site.post_status.get(self.path, 200))
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def add(self, path: str, html: str):
        self.routes[path] = html

    def add_redirect(self, path: str, location: str, status: int = 302):
        self.routes[path] = (status, {"Location": location})

    def add_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream"):
        self.routes[path] = _Binary(data, content_type)

    def add_flaky(
        self, path: str, html: str, fail_times: int = 1, status: int = 500,
        headers: dict | None = None,
    ):
        self.routes[path] = _Flaky(html, fail_times, status, headers)

    def stop(self):
        self._server.shutdown()


@pytest.fixture
def site():
    fixture = FixtureSite()
    yield fixture
    fixture.stop()
