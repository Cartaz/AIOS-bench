from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class _Handler(BaseHTTPRequestHandler):
    payload: dict[str, Any] = {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/state":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(self.payload, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


def main() -> int:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("runtime probe server requires one JSON payload on stdin")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise SystemExit("runtime probe payload must be an object")
    _Handler.payload = payload
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    print(server.server_port, flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
