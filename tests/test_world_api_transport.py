from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aios_bench.parametric import materialize_variant, start_variant_runtime
from aios_bench.world_service import API_CONTRACT_SCHEMA


TASK_ID = "stateful_support_001"


def _http_error_payload(request: Request) -> tuple[int, dict]:
    try:
        urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError("request unexpectedly succeeded")


def test_world_api_requires_bearer_auth_and_exposes_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=2027)
    runtime = start_variant_runtime(
        "stateful_world",
        workspace,
        run_dir=run_dir,
        task_id=TASK_ID,
        oracle=oracle,
    )
    try:
        endpoint = runtime.environment["AIOS_BENCH_WORLD_API_URL"]
        token = runtime.environment["AIOS_BENCH_WORLD_API_TOKEN"]
        status, payload = _http_error_payload(Request(endpoint + "/v1/schema"))
        assert status == 401
        assert payload["error"]["code"] == "unauthorized"

        request = Request(
            endpoint + "/v1/schema",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urlopen(request, timeout=5) as response:
            contract = json.loads(response.read().decode("utf-8"))
        assert contract["schema"] == API_CONTRACT_SCHEMA
        assert "escalate_ticket" in contract["write_operations"]
    finally:
        runtime.close()


def test_world_api_rejects_malformed_write_schema_deterministically(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=2028)
    runtime = start_variant_runtime(
        "stateful_world",
        workspace,
        run_dir=run_dir,
        task_id=TASK_ID,
        oracle=oracle,
    )
    try:
        endpoint = runtime.environment["AIOS_BENCH_WORLD_API_URL"]
        token = runtime.environment["AIOS_BENCH_WORLD_API_TOKEN"]
        request = Request(
            endpoint + "/v1/actions/escalate",
            data=json.dumps({"ticket_id": oracle["target_ids"][0]}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        status, payload = _http_error_payload(request)
        assert status == 400
        assert payload == {
            "error": {
                "code": "invalid_schema",
                "message": "escalate action requires exactly ticket_id and idempotency_key",
            }
        }
    finally:
        runtime.close()
