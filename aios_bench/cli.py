from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from benchmark.scoring import aggregate, evaluate

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark" / "tasks" / "pilot.json"
FIXTURES = ROOT / "benchmark" / "fixtures"


def load_tasks() -> list[dict]:
    return json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]


def cmd_list(_: argparse.Namespace) -> int:
    tasks = load_tasks()
    for t in tasks:
        print(f"{t['id']:28} {t['category']:14} {t['mode']}")
    print(f"\n{len(tasks)} tasks")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    tasks = load_tasks()
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)), "duplicate task IDs"
    for t in tasks:
        assert t.get("id") and t.get("category") and t.get("prompt")
        assert t.get("evaluator", {}).get("type")
    print(f"OK: {len(tasks)} tasks validated")
    return 0


def _copy_fixture(name: str | None, dst: Path) -> None:
    if not name:
        return
    src = FIXTURES / name
    if not src.exists():
        raise FileNotFoundError(f"fixture not found: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def cmd_run(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    if args.task:
        tasks = [t for t in tasks if t["id"] == args.task]
    if not tasks:
        raise SystemExit("No matching tasks")
    out = Path(args.output or f"results/{args.run_id}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    adapter = Path(args.adapter).resolve()
    with out.open("w", encoding="utf-8") as fp:
        for task in tasks:
            with tempfile.TemporaryDirectory(prefix="aios-bench-") as td:
                workspace = Path(td)
                _copy_fixture(task.get("fixture"), workspace)
                payload = {"protocol":"aios-bench/0.1","task":task,"workspace":str(workspace),"run_id":args.run_id}
                proc = subprocess.run([os.fspath(adapter), json.dumps(payload)], capture_output=True, text=True, cwd=ROOT)
                if proc.returncode != 0:
                    traj = {"agent": args.agent, "task_id":task["id"], "success":False,"errors":1,"notes":proc.stderr[-4000:]}
                else:
                    try:
                        traj = json.loads(proc.stdout.strip().splitlines()[-1])
                    except Exception:
                        traj = {"agent": args.agent,"task_id":task["id"],"success":False,"errors":1,"notes":"Adapter did not emit valid JSON trajectory."}
                result = evaluate(task, traj, workspace)
                fp.write(json.dumps({"trajectory":traj,"evaluation":result}, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"{task['id']}: {'PASS' if result['passed'] else 'FAIL'} {result['quality_score']:.1f}")
    print(f"Results: {out}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    rows = [json.loads(x) for x in Path(args.results).read_text(encoding="utf-8").splitlines() if x.strip()]
    results = [r["evaluation"] for r in rows]
    print(json.dumps(aggregate(results), indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="aios-bench")
    sub = p.add_subparsers(required=True)
    s = sub.add_parser("list"); s.set_defaults(func=cmd_list)
    s = sub.add_parser("validate"); s.set_defaults(func=cmd_validate)
    s = sub.add_parser("run"); s.add_argument("--adapter", required=True); s.add_argument("--agent", default="unknown"); s.add_argument("--run-id", required=True); s.add_argument("--output"); s.add_argument("--task"); s.set_defaults(func=cmd_run)
    s = sub.add_parser("score"); s.add_argument("results"); s.set_defaults(func=cmd_score)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
