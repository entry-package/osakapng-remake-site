#!/usr/bin/env python3
"""Serve the review build on loopback without retaining stale browser copies."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "dist"
    handler = partial(PreviewHandler, directory=str(output))
    server = ThreadingHTTPServer(("127.0.0.1", 8766), handler)
    print("OsakaPNG preview: http://127.0.0.1:8766/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
