from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dashboard import build_dashboard
from .models import Trajectory
from .runner import AGENTS, BenchmarkRunner
from .scoring import overall_score
from .tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"
RESULTS = ROOT / "results"


def _add_harness_flags(parser: argparse.ArgumentParser) -> None:
    for name, config in AGENTS.items():
        parser.add_argument(f"--{name}", action="store_true", help=f"Run the {config.display_name} suite")


def _selected_harness(args) -> str | None:
    selected = [name for name in AGENTS if getattr(args, name, False)]
    if len(selected) > 1:
        raise SystemExit("Select exactly one harness.")
    return selected[0] if selected else None


def main() -> None:
    parser = argparse.ArgumentParser(prog="aiosbench", description="AIOS-bench local agent benchmark")
    _add_harness_flags(parser)
    parser.add_argument("--model", default="unknown", help="Model identifier for longitudinal comparisons")
    parser.add_argument("--timeout", type=float, default=900, help="Per-task timeout in seconds")
    parser.add_argument("--total-timeout", type=float, default=None, help="Optional whole-suite timeout")
    parser.add_argument("--no-resume", action="store_true", help="Run every task even if a previous result exists")
    parser.add_argument("--dashboard", action="store_true", help="Open/build the comparison dashboard after the run")
    parser.add_argument("command", nargs="?", choices=["run", "list", "score", "dashboard"], default="run")
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()

    harness = _selected_harness(args)
    if args.command == "list":
        for task in load_tasks(TASKS):
            print(f"{task.id}\t{task.category}\t{task.mode}\t{task.prompt}")
        return
    if args.command == "score":
        if not args.path:
            raise SystemExit("score requires a JSON trajectory path")
        data = json.loads(args.path.read_text(encoding="utf-8"))
        print(f"{overall_score(Trajectory(**data)):.2f}")
        return
    if args.command == "dashboard":
        path = build_dashboard(RESULTS)
        print(path)
        return
    if not harness:
        raise SystemExit("Select a harness, e.g. aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL")

    runner = BenchmarkRunner(ROOT, AGENTS[harness], RESULTS, args.timeout, args.total_timeout,
                            resume=not args.no_resume, model=args.model)
    code = runner.run(load_tasks(TASKS))
    dashboard = build_dashboard(RESULTS)
    print(f"Dashboard: {dashboard}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
