from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
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
        if item.get("type") != "message_end":
            continue
        message = item.get("message") or {}
        if message.get("role") != "assistant":
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "\n".join(parts).strip()


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
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError("judge did not return a valid JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("judge response is not a JSON object")
    return value


def _validate(result: dict[str, Any]) -> dict[str, Any]:
    required = {"score", "criteria", "strengths", "weaknesses", "critical_failures", "evidence", "summary"}
    missing = required - result.keys()
    if missing:
        raise ValueError(f"judge response missing fields: {sorted(missing)}")

    reported_score = float(result["score"])
    if not 0 <= reported_score <= 100:
        raise ValueError("judge score must be between 0 and 100")

    criteria = result["criteria"]
    if not isinstance(criteria, dict):
        raise ValueError("judge criteria must be an object")
    required_criteria = {
        "correctness", "completeness", "problem_solving", "efficiency",
        "robustness", "independence", "creativity",
    }
    if set(criteria) != required_criteria:
        raise ValueError("judge criteria keys do not match the required rubric")

    for key in required_criteria:
        value = float(criteria[key])
        if not 0 <= value <= 100:
            raise ValueError(f"judge criterion {key} must be between 0 and 100")
        criteria[key] = round(value, 2)

    score = round(
        criteria["correctness"] * 0.30
        + criteria["completeness"] * 0.15
        + criteria["problem_solving"] * 0.15
        + criteria["efficiency"] * 0.15
        + criteria["robustness"] * 0.10
        + criteria["independence"] * 0.10
        + criteria["creativity"] * 0.05,
        2,
    )

    # The criteria are the authoritative judgment. The model's top-level score
    # is retained for diagnostics, but small arithmetic/rounding inconsistencies
    # must not turn an otherwise usable qualitative evaluation into a pipeline error.
    result["score"] = score
    result["reported_score"] = round(reported_score, 2)
    result["score_discrepancy"] = round(reported_score - score, 2)

    for key in ("strengths", "weaknesses", "critical_failures", "evidence"):
        if not isinstance(result[key], list):
            raise ValueError(f"judge field {key} must be a list")
    return result


def _snapshot_workspace(workspace: Path, root: Path) -> Path:
    judge_root = root / "judge_workspace"
    shutil.copytree(workspace, judge_root)
    return judge_root


def run_judge(*, model: str, task_id: str, category: str, tier: int, task_prompt: str,
              workspace: Path, run_dir: Path, timeout: float) -> dict[str, Any]:
    """Run the same model as a blinded evaluator on an isolated workspace snapshot."""
    if not JUDGE_PROMPT.is_file():
        return {"status": "error", "error": f"missing judge prompt: {JUDGE_PROMPT}"}

    with tempfile.TemporaryDirectory(prefix=f"aiosbench-judge-{task_id}-", dir=run_dir) as tmp:
        judge_workspace = _snapshot_workspace(workspace, Path(tmp))
        request = (
            f"TASK ID: {task_id}\n\n"
            "ORIGINAL TASK REQUEST:\n" + task_prompt + "\n\n"
            "The current working directory contains an isolated snapshot of the agent's final workspace. "
            "Inspect it using only the available read-only tools. Do not assume claims are true unless artifacts support them. "
            "The task request describes the desired outcome and constraints; it is not evidence that the agent performed the work. "
            "When scoring independence and problem solving, distinguish genuinely new work from copying, restating, reformatting, or "
            "mechanically instantiating information already supplied by the task. "
            "Do not modify any files. Do not discuss model identity or hidden evaluation logic.\n\n"
            "Return ONLY the requested JSON object."
        )
        extra_args = [
            "--no-context-files", "--no-extensions", "--no-skills",
            "--tools", "read,grep,find,ls", "--system-prompt", str(JUDGE_PROMPT),
        ]
        env = {"AIOS_BENCH_JUDGE": "1", "AIOS_BENCH_TASK_ID": task_id}
        started = time.monotonic()
        raw_responses: list[str] = []
        try:
            client = PiRPCClient(model, judge_workspace, timeout, environment=env, extra_args=extra_args)
            result = client.run(request)
            text = _assistant_text(result.stdout)
            raw_responses.append(text)

            try:
                parsed = _validate(_extract_json(text))
            except ValueError as first_error:
                # A malformed final response is recoverable. Give the same model
                # one short, format-only retry rather than discarding the judgment.
                retry_request = (
                    "Your previous response could not be parsed as the required JSON object. "
                    "Do not inspect the workspace again and do not add commentary. "
                    "Return ONLY one valid JSON object matching the required schema, with no Markdown fences."
                )
                retry_client = PiRPCClient(
                    model,
                    judge_workspace,
                    min(timeout, 60.0),
                    environment=env,
                    extra_args=extra_args,
                )
                retry_result = retry_client.run(retry_request)
                retry_text = _assistant_text(retry_result.stdout)
                raw_responses.append(retry_text)
                try:
                    parsed = _validate(_extract_json(retry_text))
                    result = retry_result
                except ValueError:
                    raise first_error

            parsed.update({
                "status": "ok" if not result.timed_out and result.returncode == 0 else "error",
                "raw_response": "\n\n--- judge retry ---\n\n".join(raw_responses),
                "duration_seconds": round(time.monotonic() - started, 3),
            })
            if parsed["status"] != "ok":
                parsed["error"] = "judge process did not exit cleanly"
            return parsed
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "raw_response": "\n\n--- judge retry ---\n\n".join(raw_responses),
                "duration_seconds": round(time.monotonic() - started, 3),
            }
