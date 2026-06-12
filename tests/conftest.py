"""Shared fixture site: a local HTTP server serving a dict of routes.

Each route maps a path to either an HTML string (served as 200 text/html)
or a (status, headers) tuple for redirects and errors. Later slices extend
this site with a sitemap, error endpoints, an SPA shell, and robots.txt.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class FixtureSite:
    def __init__(self):
        self.routes: dict[str, object] = {}
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                route = site.routes.get(self.path)
                if route is None:
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

    def stop(self):
        self._server.shutdown()


@pytest.fixture
def site():
    fixture = FixtureSite()
    yield fixture
    fixture.stop()
