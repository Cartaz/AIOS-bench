from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .fixtures.seed import seed
from .models import load_tasks
from .scoring import aggregate, evaluate

ROOT = Path(__file__).resolve().parents[1]


def cmd_list(_: argparse.Namespace) -> int:
    for task in load_tasks():
        print(f"{task.id}\t{task.category}\t{task.mode}\t{task.prompt}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    tasks = load_tasks()
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate task id")
    print(f"Validated {len(tasks)} tasks")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    all_tasks = load_tasks()
    selected = all_tasks if args.suite == "pilot" else [t for t in all_tasks if t.id in set(args.task)]
    if args.category:
        selected = [t for t in selected if t.category in args.category]
    if args.mode:
        selected = [t for t in selected if t.mode == args.mode]
    if not selected:
        raise SystemExit("No tasks selected")

    out = Path(args.output or f"results/{args.run_id}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(args.workspace or f"runs/{args.run_id}")
    run_root.mkdir(parents=True, exist_ok=True)
    persistent = run_root / "workspace"

    with out.open("w", encoding="utf-8") as fh:
        for task in selected:
            # Cold tasks are isolated. Warm/longitudinal tasks share state so that
            # memory and skills can persist across the selected task sequence.
            if task.mode == "cold":
                workspace = run_root / "tasks" / task.id
                if workspace.exists():
                    shutil.rmtree(workspace)
            else:
                workspace = persistent
            seed(workspace)
            workspace.mkdir(parents=True, exist_ok=True)

            payload = {
                "protocol": "aios-bench/0.1",
                "task": task.__dict__,
                "workspace": str(workspace.resolve()),
                "run_id": args.run_id,
            }
            try:
                proc = subprocess.run(
                    args.adapter + [json.dumps(payload)],
                    text=True,
                    capture_output=True,
                    timeout=task.timeout_s,
                )
            except subprocess.TimeoutExpired:
                proc = None

            if proc is None:
                traj = {
                    "agent": args.agent,
                    "task_id": task.id,
                    "success": False,
                    "errors": 1,
                    "notes": f"Timed out after {task.timeout_s}s",
                    "events": [],
                }
            elif proc.returncode != 0:
                traj = {
                    "agent": args.agent,
                    "task_id": task.id,
                    "success": False,
                    "errors": 1,
                    "notes": proc.stderr[-4000:],
                    "events": [],
                }
            else:
                try:
                    traj = json.loads(proc.stdout.strip().splitlines()[-1])
                except (json.JSONDecodeError, IndexError):
                    traj = {
                        "agent": args.agent,
                        "task_id": task.id,
                        "success": False,
                        "errors": 1,
                        "notes": "Adapter did not emit valid JSON trajectory",
                        "events": [],
                    }
            result = evaluate(task.__dict__, traj, workspace)
            fh.write(json.dumps({"trajectory": traj, "result": result}, ensure_ascii=False) + "\n")
            print(f"{task.id}: {'PASS' if result['passed'] else 'FAIL'} {result['quality_score']:.1f}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    rows = []
    for line in Path(args.path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line)["result"])
    print(json.dumps(aggregate(rows), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="aios-bench")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("list"); s.set_defaults(func=cmd_list)
    s = sub.add_parser("validate"); s.set_defaults(func=cmd_validate)
    s = sub.add_parser("run")
    s.add_argument("--adapter", nargs="+", required=True)
    s.add_argument("--agent", default="unknown")
    s.add_argument("--suite", default="pilot")
    s.add_argument("--run-id", required=True)
    s.add_argument("--output")
    s.add_argument("--workspace")
    s.add_argument("--mode", choices=["cold", "warm", "longitudinal"])
    s.add_argument("--category", action="append")
    s.add_argument("--task", action="append", default=[])
    s.set_defaults(func=cmd_run)
    s = sub.add_parser("score")
    s.add_argument("path")
    s.set_defaults(func=cmd_score)
    return sub.get_default("func")(p.parse_args())

if __name__ == "__main__":
    raise SystemExit(main())
