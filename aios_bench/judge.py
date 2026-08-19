from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .pi_rpc import PiRPCClient


JUDGE_PROMPT = Path(__file__).resolve().parents[1] / "benchmarks" / "judge" / "SYSTEM.md"


def _assistant_text(rpc_stdout: str) -> str:
    parts: list[str] = []
    for line in rpc_stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") == "message_end":
            message = item.get("message") or {}
            if message.get("role") != "assistant":
                continue
            content = message.get("content") or []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
    if parts:
        return "\n".join(parts).strip()
    return ""


def _extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.S)
        if not match:
            raise ValueError("judge did not return a JSON object")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("judge response is not a JSON object")
    return value


def _validate(result: dict[str, Any]) -> dict[str, Any]:
    required = {"score", "criteria", "strengths", "weaknesses", "critical_failures", "evidence", "summary"}
    missing = required - result.keys()
    if missing:
        raise ValueError(f"judge response missing fields: {sorted(missing)}")
    score = float(result["score"])
    if not 0 <= score <= 100:
        raise ValueError("judge score must be between 0 and 100")
    if not isinstance(result["criteria"], dict):
        raise ValueError("judge criteria must be an object")
    for key in ("strengths", "weaknesses", "critical_failures", "evidence"):
        if not isinstance(result[key], list):
            raise ValueError(f"judge field {key} must be a list")
    result["score"] = round(score, 2)
    return result


def _snapshot_workspace(workspace: Path, root: Path) -> Path:
    judge_root = root / "judge_workspace"
    if judge_root.exists():
        shutil.rmtree(judge_root)
    shutil.copytree(workspace, judge_root)
    return judge_root


def run_judge(*, model: str, task_id: str, category: str, tier: int, task_prompt: str,
              workspace: Path, run_dir: Path, timeout: float) -> dict[str, Any]:
    """Run the same model as a read-only, blinded evaluator on a workspace snapshot."""
    if not JUDGE_PROMPT.is_file():
        return {"status": "error", "error": f"missing judge prompt: {JUDGE_PROMPT}"}

    with tempfile.TemporaryDirectory(prefix=f"aiosbench-judge-{task_id}-", dir=run_dir) as tmp:
        tmp_root = Path(tmp)
        judge_workspace = _snapshot_workspace(workspace, tmp_root)
        request = (
            f"TASK ID: {task_id}\n"
            f"CATEGORY: {category}\n"
            f"TIER: {tier}\n\n"
            "ORIGINAL TASK REQUEST:\n"
            f"{task_prompt}\n\n"
            "The current working directory contains a read-only snapshot of the agent's final workspace. "
            "Inspect it using the available read-only tools. Do not assume claims are true unless the artifacts support them. "
            "Do not mention that you are the same model that produced the work.\n\n"
            "Return ONLY the requested JSON object."
        )
        command = [
            "pi", "--mode", "rpc", "--no-session", "--no-context-files", "--no-extensions", "--no-skills",
            "--tools", "read,grep,find,ls", "--model", model, "--system-prompt", str(JUDGE_PROMPT),
        ]
        env = {"AIOS_BENCH_JUDGE": "1", "AIOS_BENCH_TASK_ID": task_id}
        client = PiRPCClient(model, judge_workspace, timeout, environment=env)
        original = client._command
        client._command = lambda: command  # type: ignore[method-assign]
        try:
            result = client.run(request)
            text = _assistant_text(result.stdout)
            parsed = _validate(_extract_json(text))
            parsed.update({"status": "ok", "raw_response": text, "duration_seconds": None})
            return parsed
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "raw_response": _assistant_text(result.stdout) if "result" in locals() else "",
            }
        finally:
            client._command = original  # type: ignore[method-assign]
