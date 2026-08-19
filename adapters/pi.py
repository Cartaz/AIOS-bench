"""AIOS-bench adapter for Pi coding-agent.

Pi is invoked in JSON non-interactive mode. Configure the local model in Pi's
provider settings, or set PI_PROVIDER/PI_MODEL. The adapter records observable
JSON events and filesystem deltas; it never requests private chain-of-thought.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    payload = json.loads(sys.argv[1])
    task = payload["task"]
    workspace = Path(payload["workspace"])
    prompt = (
        "You are being evaluated by AIOS-bench. Work only inside the supplied workspace. "
        "Complete the task exactly as written. Do not expose private chain-of-thought. "
        "Observable actions and concise final summaries are sufficient.\n\nTASK:\n" + task["prompt"]
    )
    cmd = [os.environ.get("PI_COMMAND", "pi"), "--mode", "json", "--no-session"]]
    provider = os.environ.get("PI_PROVIDER")
    model = os.environ.get("PI_MODEL")
    if provider:
        cmd += ["--provider", provider]
    if model:
        cmd += ["--model", model]
    cmd += ["-p", prompt]

    before = {str(p.relative_to(workspace)): p.stat().st_mtime_ns for p in workspace.rglob("*") if p.is_file()}
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=int(os.environ.get("AIOS_TIMEOUT", "1800")))
    duration = time.perf_counter() - start
    events = []
    input_tokens = output_tokens = 0
    errors = retries = subagents = 0
    for line in proc.stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(e)
        typ = str(e.get("type", ""))
        if "error" in typ.lower() or e.get("isError") is True:
            errors += 1
        if "retry" in typ.lower():
            retries += 1
        if "subagent" in typ.lower():
            subagents += 1
        usage = e.get("usage") or {}
        input_tokens += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)

    after_files = {str(p.relative_to(workspace)): p for p in workspace.rglob("*") if p.is_file()}
    writes = [p for name, p in after_files.items() if name not in before or p.stat().st_mtime_ns != before[name]]
    trajectory = {
        "agent": "pi",
        "task_id": task["id"],
        "success": proc.returncode == 0,
        "duration_s": round(duration, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": sum(1 for e in events if "tool" in str(e.get("type", "")).lower()),
        "errors": errors + (1 if proc.returncode != 0 else 0),
        "retries": retries,
        "human_interventions": 0,
        "files_read": sum(1 for e in events if "read" in str(e.get("type", "")).lower()),
        "files_written": len(writes),
        "memory_reads": sum(1 for e in events if "memory_read" in str(e.get("type", ""))),
        "memory_writes": sum(1 for e in events if "memory_write" in str(e.get("type", ""))),
        "skills_created": sum(1 for e in events if "skill" in str(e.get("type", "")).lower() and "create" in str(e.get("type", "")).lower()),
        "subagents": subagents,
        "events": events,
        "notes": proc.stderr[-4000:] if proc.stderr else "",
    }
    print(json.dumps(trajectory, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
