"""AIOS-bench adapter for Hermes Agent.

Hermes currently exposes a strong CLI but not a stable machine-readable
trajectory contract, so this adapter captures the final process result and
filesystem deltas. It is intentionally conservative about inferred events.
Set HERMES_PROVIDER/HERMES_MODEL/HERMES_TOOLSETS as needed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    payload = json.loads(sys.argv[1])
    task = payload["task"]
    workspace = Path(payload["workspace"])
    prompt = (
        "AIOS-bench task. Work only in this workspace. Complete the requested task. "
        "Do not reveal private chain-of-thought; provide a concise final summary.\n\n" + task["prompt"]
    )
    cmd = [os.environ.get("HERMES_COMMAND", "hermes"), "chat", "--verbose"]
    provider = os.environ.get("HERMES_PROVIDER")
    model = os.environ.get("HERMES_MODEL")
    toolsets = os.environ.get("HERMES_TOOLSETS")
    if provider:
        cmd += ["--provider", provider]
    if model:
        cmd += ["--model", model]
    if toolsets:
        cmd += ["--toolsets", toolsets]
    cmd += ["-q", prompt]

    before = {str(p.relative_to(workspace)): p.stat().st_mtime_ns for p in workspace.rglob("*") if p.is_file()}
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=int(os.environ.get("AIOS_TIMEOUT", "1800")))
    duration = time.perf_counter() - start
    text = proc.stdout
    low = text.lower()
    errors = len(re.findall(r"\b(error|exception|failed|failure)\b", low))
    retries = len(re.findall(r"\b(retry|retrying)\b", low))
    tool_calls = len(re.findall(r"\b(tool|terminal|python|read_file|write_file|browser)\b", low))
    after_files = {str(p.relative_to(workspace)): p for p in workspace.rglob("*") if p.is_file()}
    writes = [p for name, p in after_files.items() if name not in before or p.stat().st_mtime_ns != before[name]]
    trajectory = {
        "agent": "hermes", "task_id": task["id"], "success": proc.returncode == 0,
        "duration_s": round(duration, 3), "input_tokens": 0, "output_tokens": 0,
        "tool_calls": tool_calls, "errors": errors + (1 if proc.returncode != 0 else 0),
        "retries": retries, "human_interventions": 0, "files_read": 0,
        "files_written": len(writes), "memory_reads": 0, "memory_writes": 0,
        "skills_created": 0, "subagents": 0,
        "events": [{"type":"process","exit_code":proc.returncode}],
        "notes": (proc.stderr + "\n" + text)[-6000:],
    }
    print(json.dumps(trajectory, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
