"""Stdlib HTTP overlay UI for live JSONL charts."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_sidecar.live_plot import LivePlotIngest

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _content_type(name: str) -> str:
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def make_handler(ingest: LivePlotIngest) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "live_plot.html")
                return
            if path == "/chart.umd.min.js":
                self._send_file(STATIC_DIR / "chart.umd.min.js")
                return
            if path == "/api/snapshot":
                body = json.dumps(ingest.poll()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def _send_file(self, path: Path) -> None:
            if not path.is_file():
                self.send_error(404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", _content_type(path.name))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


class LivePlotServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = int(port)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url = ""

    def start(self, run_dir: Path) -> str:
        ingest = LivePlotIngest(run_dir)
        handler = make_handler(ingest)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.port = int(self._httpd.server_address[1])
        self.url = f"http://{self.host}:{self.port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def wait(self) -> None:
        if self._thread is not None:
            self._thread.join()

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=5)
