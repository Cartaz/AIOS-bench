from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print("missing prompt", file=sys.stderr)
        return 2
    api_key = os.environ.get("AIOS_BENCH_AGENTZERO_API_KEY")
    if not api_key:
        print("AIOS_BENCH_AGENTZERO_API_KEY is required", file=sys.stderr)
        return 2

    payload = {
        "message": sys.argv[1],
        "lifetime_hours": 1,
    }
    project = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT")
    if project:
        payload["project_name"] = project

    url = os.environ.get("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:80").rstrip("/") + "/api_message"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=None) as response:
            body = response.read().decode("utf-8")
            print(body)
        return 0
    except Exception as exc:
        print(f"Agent Zero API error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
