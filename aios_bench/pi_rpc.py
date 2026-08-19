from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PiRPCResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class PiRPCClient:
    """Small stdio JSONL client for pi --mode rpc.

    Pi keeps stdin open while the RPC session is alive. We therefore cannot use
    subprocess.run with a one-shot input pipe: closing stdin immediately can
    terminate a run before agent_settled. This client keeps the stream open,
    sends one prompt, collects events through agent_settled, then shuts down.
    """

    def __init__(self, model: str, workspace: Path, timeout: float) -> None:
        self.model = model
        self.workspace = workspace
        self.timeout = timeout

    def _command(self) -> list[str]:
        command = ["pi", "--mode", "rpc", "--no-session"]
        if self.model and self.model != "unknown":
            command += ["--model", self.model]
        return command

    def run(self, prompt: str) -> PiRPCResult:
        env = os.environ.copy()
        env["AIOS_BENCH_WORKSPACE"] = str(self.workspace.resolve())
        proc = subprocess.Popen(
            self._command(),
            cwd=self.workspace,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        started = time.monotonic()
        lines: list[str] = []
        stderr_text = ""
        timed_out = False
        try:
            assert proc.stdin is not None
            assert proc.stdout is not None
            proc.stdin.write(json.dumps({"id": "aios-bench", "type": "prompt", "message": prompt}) + "\n")
            proc.stdin.flush()

            while True:
                if time.monotonic() - started >= self.timeout:
                    timed_out = True
                    proc.kill()
                    break
                line = proc.stdout.readline()
                if line:
                    lines.append(line)
                    try:
                        event: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "agent_settled":
                        break
                elif proc.poll() is not None:
                    break
                else:
                    time.sleep(0.01)
        finally:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            if proc.stderr:
                stderr_text = proc.stderr.read()

        return PiRPCResult(
            returncode=proc.returncode if proc.returncode is not None else 1,
            stdout="".join(lines),
            stderr=stderr_text,
            timed_out=timed_out,
        )
