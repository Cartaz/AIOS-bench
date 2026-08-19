from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dashboard import build_dashboard
from .models import Trajectory
from .report import write_summary
from .runner import AGENTS, BenchmarkRunner
from .scoring import overall_score
from .tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"
RESULTS = ROOT / "results"


def _add_harness_flags(parser: argparse.ArgumentParser) -> None:
    for name, config in AGENTS.items():
        parser.add_argument(f"--{name}", action="store_true", help=f"Run the {config.display_name} suite")
    parser.add_argument("--all", action="store_true", help="Run every configured harness sequentially")


def _selected_harnesses(args) -> list[str]:
    selected = [name for name in AGENTS if getattr(args, name, False)]
    if args.all:
        selected.append("__all__")
    if len(selected) > 1:
        raise SystemExit("Select one harness or --all, not both.")
    if selected == ["__all__"]:
        return list(AGENTS)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(prog="aiosbench", description="AIOS-bench local agent benchmark")
    _add_harness_flags(parser)
    parser.add_argument("--model", default="unknown", help="Model identifier for longitudinal comparisons")
    parser.add_argument("--timeout", type=float, default=900, help="Per-task timeout in seconds")
    parser.add_argument("--total-timeout", type=float, default=None, help="Optional whole-suite timeout per harness")
    parser.add_argument("--no-resume", action="store_true", help="Run every task even if a previous result exists")
    parser.add_argument("--dashboard", action="store_true", help="Build the comparison dashboard after the run")
    parser.add_argument("command", nargs="?", choices=["run", "list", "score", "dashboard"], default="run")
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()

    harnesses = _selected_harnesses(args)
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
        dashboard = build_dashboard(RESULTS)
        summary = write_summary(RESULTS)
        print(f"Dashboard: {dashboard}")
        print(f"Summary:   {summary}")
        return
    if not harnesses:
        raise SystemExit("Select a harness, e.g. aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL, or use --all")

    tasks = load_tasks(TASKS)
    exit_code = 0
    for index, harness in enumerate(harnesses, 1):
        print(f"\n=== Harness {index}/{len(harnesses)}: {AGENTS[harness].display_name} ===\n")
        runner = BenchmarkRunner(ROOT, AGENTS[harness], RESULTS, args.timeout, args.total_timeout,
                                 resume=not args.no_resume, model=args.model)
        code = runner.run(tasks)
        exit_code = max(exit_code, code)
        build_dashboard(RESULTS)
        write_summary(RESULTS)

    dashboard = build_dashboard(RESULTS)
    summary = write_summary(RESULTS)
    print(f"\nDashboard: {dashboard}")
    print(f"Summary:   {summary}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
