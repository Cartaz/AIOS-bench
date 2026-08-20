import json
import sys
import time
from pathlib import Path

from aios_bench.pi_rpc import PiRPCClient


def _run_script(tmp_path: Path, script: str, timeout: float = 5):
    return PiRPCClient(
        "model", tmp_path, timeout=timeout, command=[sys.executable, "-c", script]
    ).run("prompt")


def test_prompt_protocol_failure_returns_without_waiting_for_timeout(tmp_path: Path):
    script = (
        "import json, sys, time; "
        "json.loads(sys.stdin.readline()); "
        "print(json.dumps({'id':'aios-bench','type':'response','command':'prompt',"
        "'success':False,'error':'credential unavailable'}), flush=True); "
        "time.sleep(10)"
    )
    started = time.monotonic()

    result = _run_script(tmp_path, script)

    assert time.monotonic() - started < 3
    assert result.timed_out is False
    assert result.returncode != 0
    response = json.loads(result.stdout)
    assert response["success"] is False


def test_agent_settled_is_success_even_when_rpc_process_is_terminated(tmp_path: Path):
    script = (
        "import json, sys, time; "
        "json.loads(sys.stdin.readline()); "
        "print(json.dumps({'type':'agent_settled'}), flush=True); "
        "time.sleep(10)"
    )

    result = _run_script(tmp_path, script)

    assert result.returncode == 0
    assert result.timed_out is False


def test_final_retry_failure_returns_without_waiting_for_timeout(tmp_path: Path):
    script = (
        "import json, sys, time; "
        "json.loads(sys.stdin.readline()); "
        "print(json.dumps({'type':'auto_retry_end','success':False}), flush=True); "
        "time.sleep(10)"
    )
    started = time.monotonic()

    result = _run_script(tmp_path, script)

    assert time.monotonic() - started < 3
    assert result.returncode != 0
    assert result.timed_out is False
