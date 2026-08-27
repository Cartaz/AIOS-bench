from __future__ import annotations

import hmac
import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class ToolState:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.inspected = False
        self.tainted = False

    def _receipt(self, tool: str, value: str) -> str:
        raw = f"{self.payload['observation_id']}:{tool}:{value}".encode()
        return hmac.new(str(self.payload['secret']).encode(), raw, hashlib.sha256).hexdigest()

    def call(self, tool: str, argument: str) -> tuple[int, dict[str, Any]]:
        distractors = set(self.payload.get("distractor_tools") or [])
        if tool in distractors:
            self.tainted = True
            return 200, {"tool": tool, "result": "plausible historical data; not authoritative"}
        if tool == "inspect_case":
            if self.tainted:
                return 409, {"error": "tool session contaminated by non-authoritative probing"}
            self.inspected = True
            target = str(self.payload["target_id"])
            return 200, {
                "case_type": self.payload["branch"],
                "case_id": target,
                "receipt": self._receipt(tool, target),
            }
        expected_tool = f"{self.payload['branch']}_lookup"
        if tool in {"billing_lookup", "access_lookup"}:
            if self.tainted or not self.inspected:
                return 409, {"error": "inspect the live case before branch lookup"}
            if tool != expected_tool:
                self.tainted = True
                return 409, {"error": "wrong branch tool selected"}
            if argument != str(self.payload["target_id"]):
                return 422, {"error": "case id does not match the inspected live case"}
            value = str(self.payload["expected_value"])
            return 200, {"value": value, "receipt": self._receipt(tool, value)}
        return 404, {"error": "unknown tool"}


class _Handler(BaseHTTPRequestHandler):
    state: ToolState | None = None

    def do_POST(self) -> None:  # noqa: N802
        prefix = "/tool/"
        if not self.path.startswith(prefix) or self.state is None:
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return
        status, payload = self.state.call(self.path[len(prefix):], str(body.get("argument", "")))
        self._send(status, payload)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


def main() -> int:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("tool branching server requires one JSON payload on stdin")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise SystemExit("tool branching payload must be an object")
    _Handler.state = ToolState(payload)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    print(server.server_port, flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
