from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .judge import run_judge
from .tasks import load_tasks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if not dx or not dy:
        return None
    return num / (dx * dy) ** 0.5


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = (i + j - 1) / 2 + 1
        for k in range(i, j):
            ranks[order[k]] = rank
        i = j
    return ranks


def _load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    results_path = run_dir / "results.jsonl"
    if not results_path.is_file():
        raise FileNotFoundError(f"Missing results.jsonl: {results_path}")
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return metadata, results


def rejudge_run(*, repo_root: Path, run_dir: Path, timeout: float, model_override: str | None = None) -> Path:
    metadata, results = _load_run(run_dir)
    model = model_override or metadata.get("model")
    if not model:
        raise ValueError("Run metadata does not contain a model; use --model")

    tasks = {task.id: task for task in load_tasks(repo_root / "benchmarks" / "tasks")}
    output_path = run_dir / "judge_calibration.jsonl"
    records: list[dict[str, Any]] = []
    total = len(results)

    print("\n=== LLM Judge calibration ===\n", flush=True)
    print(f"Model: {model}", flush=True)
    print(f"Tasks: {total}", flush=True)
    print(f"Timeout: {timeout:.0f}s per task\n", flush=True)

    with output_path.open("w", encoding="utf-8") as out:
        for index, result in enumerate(results, 1):
            task_id = result["task_id"]
            task = tasks.get(task_id)
            objective_score = float(result.get("score", 0.0))
            started = time.perf_counter()
            print(f"[{index}/{total}] {task_id} [T{task.tier if task else '?'}] ...", flush=True)

            if task is None:
                record = {"task_id": task_id, "status": "error", "error": "task not found in current catalog"}
            else:
                workspace = run_dir / "workspaces" / task_id
                if not workspace.is_dir():
                    record = {"task_id": task_id, "status": "error", "error": f"missing workspace: {workspace}"}
                else:
                    judge = run_judge(
                        model=model,
                        task_id=task.id,
                        category=task.category,
                        tier=task.tier,
                        task_prompt=task.prompt,
                        workspace=workspace,
                        run_dir=run_dir,
                        timeout=timeout,
                    )
                    record = {
                        "task_id": task_id,
                        "category": task.category,
                        "tier": task.tier,
                        "objective_score": objective_score,
                        "objective_passed": bool(result.get("success", result.get("passed", False))),
                        "judge": judge,
                    }

            records.append(record)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

            elapsed = time.perf_counter() - started
            judge = record.get("judge") or {}
            if judge.get("status") == "ok":
                judge_score = float(judge["score"])
                gap = judge_score - objective_score
                print(f"    JUDGE  {judge_score:.1f}/100  {elapsed:.1f}s  objective={objective_score:.1f}  gap={gap:+.1f}", flush=True)
            elif record.get("status") == "error":
                print(f"    ERROR  {record.get('error', 'unknown error')}  {elapsed:.1f}s", flush=True)
            else:
                print(f"    ERROR  judge failed: {judge.get('error', 'unknown error')}  {elapsed:.1f}s", flush=True)

    pairs = [
        (float(r["objective_score"]), float(r["judge"]["score"]))
        for r in records
        if r.get("judge", {}).get("status") == "ok"
    ]
    objective = [x for x, _ in pairs]
    judged = [y for _, y in pairs]
    discordant = sorted(
        [
            {
                "task_id": r["task_id"],
                "objective_score": r["objective_score"],
                "judge_score": r["judge"]["score"],
                "gap": round(r["judge"]["score"] - r["objective_score"], 2),
            }
            for r in records
            if r.get("judge", {}).get("status") == "ok"
        ],
        key=lambda x: abs(x["gap"]),
        reverse=True,
    )[:10]
    summary = {
        "run_id": metadata.get("run_id"),
        "model": model,
        "task_count": len(records),
        "judge_ok": len(pairs),
        "judge_error": len(records) - len(pairs),
        "objective_mean": round(sum(objective) / len(objective), 2) if objective else None,
        "judge_mean": round(sum(judged) / len(judged), 2) if judged else None,
        "objective_judge_pearson": round(_pearson(objective, judged), 4) if pairs else None,
        "objective_judge_spearman": round(_pearson(_rank(objective), _rank(judged)), 4) if pairs else None,
        "mean_absolute_gap": round(sum(abs(y - x) for x, y in pairs) / len(pairs), 2) if pairs else None,
        "largest_disagreements": discordant,
    }
    (run_dir / "judge_calibration_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("\nJudge calibration complete", flush=True)
    print(f"{len(pairs)}/{len(records)} evaluated successfully", flush=True)
    if judged:
        print(f"Average judge score: {sum(judged) / len(judged):.1f}/100", flush=True)
    print(f"Judge errors: {len(records) - len(pairs)}", flush=True)
    return output_path
