from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AGENTS
from .dashboard import build_dashboard
from .experiments import annotate_repeat, make_experiment_id
from .frontier_v3_runner import FrontierV3Runner
from .models import Trajectory
from .report import write_summary
from .scheduler import MatchedInterleavedScheduler
from .scoring import overall_score
from .statistics import augment_summary_file
from .tasks import load_tasks
from .validation import validate_negative_baseline

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"
PUBLISHED = ROOT / "results"
RESULTS = PUBLISHED / ".local"


def _add_harness_flags(parser: argparse.ArgumentParser) -> None:
    for name, config in AGENTS.items():
        parser.add_argument(f"--{name}", action="store_true", help=f"Run the {config.display_name} suite")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every configured harness in matched task-level interleaved blocks",
    )


def _selected_harnesses(args: argparse.Namespace) -> list[str]:
    selected = [name for name in AGENTS if getattr(args, name, False)]
    if args.all:
        selected.append("__all__")
    if len(selected) > 1:
        raise SystemExit("Select one harness or --all, not both.")
    return list(AGENTS) if selected == ["__all__"] else selected


def _summary(root: Path, output: Path | None = None) -> Path:
    path = write_summary(root, output)
    augment_summary_file(path, root)
    return path


def _runner_kwargs(args: argparse.Namespace) -> dict:
    return {
        "resume": not args.no_resume,
        "model": args.model,
        "keep_raw": args.keep_raw,
        "server_metrics_url": args.server_metrics_url,
        "server_metrics_model": args.server_metrics_model,
        "max_output_tokens": args.max_output_tokens,
        "metrics_poll_interval": args.metrics_poll_interval,
    }


def _run_single_harness(args: argparse.Namespace, harness: str, tasks: list) -> int:
    exit_code = 0
    for repeat in range(1, args.repeats + 1):
        orchestration_seed = args.seed + repeat - 1
        run_id = args.run_id
        if run_id and args.repeats > 1:
            run_id = f"{run_id}-r{repeat:02d}"
        print(
            f"\n=== Repeat {repeat}/{args.repeats} | {AGENTS[harness].display_name} "
            f"| orchestration_seed={orchestration_seed} ===\n"
        )
        runner = FrontierV3Runner(
            ROOT,
            AGENTS[harness],
            RESULTS,
            args.timeout,
            args.total_timeout,
            run_id=run_id,
            **_runner_kwargs(args),
        )
        try:
            exit_code = max(exit_code, runner.run(tasks))
        except BaseException:
            runner.abort(tasks)
            annotate_repeat(runner.run_dir, repeat=repeat, orchestration_seed=orchestration_seed)
            raise
        annotate_repeat(runner.run_dir, repeat=repeat, orchestration_seed=orchestration_seed)
    return exit_code


def _run_matched_interleaved(args: argparse.Namespace, harnesses: list[str], tasks: list) -> int:
    exit_code = 0
    experiment_id = args.run_id or make_experiment_id()
    for repeat in range(1, args.repeats + 1):
        orchestration_seed = args.seed + repeat - 1
        run_id = experiment_id if args.repeats == 1 else f"{experiment_id}-r{repeat:02d}"
        runners = {
            harness: FrontierV3Runner(
                ROOT,
                AGENTS[harness],
                RESULTS,
                args.timeout,
                args.total_timeout,
                run_id=run_id,
                **_runner_kwargs(args),
            )
            for harness in harnesses
        }
        scheduler = MatchedInterleavedScheduler(
            runners,
            tasks,
            experiment_id=experiment_id,
            repeat=repeat,
            orchestration_seed=orchestration_seed,
        )
        result = scheduler.run()
        exit_code = max(exit_code, result.exit_code)
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(prog="aiosbench", description="AIOS-bench local agent benchmark")
    _add_harness_flags(parser)
    parser.add_argument("--model", default="unknown", help="Model identifier for longitudinal comparisons")
    parser.add_argument("--timeout", type=float, default=900, help="Per-task timeout in seconds")
    parser.add_argument("--total-timeout", type=float, default=None, help="Optional active execution budget per harness")
    parser.add_argument("--no-resume", action="store_true", help="Run every task even if a previous result exists")
    parser.add_argument("--run-id", default=None, help="Explicit run/experiment identifier")
    parser.add_argument("--repeats", type=int, default=1, help="Independent repeated suite runs")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base orchestration seed for block ordering; does not set model sampling RNG",
    )
    parser.add_argument(
        "--server-metrics-url",
        default=None,
        help="llama.cpp Prometheus endpoint or server origin (requires llama-server --metrics)",
    )
    parser.add_argument(
        "--server-metrics-model",
        default=None,
        help="Optional llama.cpp router model id added to the /metrics query",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=65536,
        help="Server-verified per-task output-token runaway cap; 0 disables the guard",
    )
    parser.add_argument(
        "--metrics-poll-interval",
        type=float,
        default=1.0,
        help="Seconds between server-metrics polls while a task is running",
    )
    parser.add_argument("--dashboard", action="store_true", help="Build the local comparison dashboard after the run")
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw event/stdout/dependency artifacts after the run")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run", "list", "score", "dashboard", "publish", "validate"],
        default="run",
    )
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
        trajectory = Trajectory(**json.loads(args.path.read_text(encoding="utf-8")))
        print(f"{overall_score(trajectory):.2f}")
        return
    if args.command == "dashboard":
        dashboard = build_dashboard(RESULTS)
        summary = _summary(RESULTS)
        print(f"Dashboard: {dashboard}")
        print(f"Summary:   {summary}")
        return
    if args.command == "publish":
        dashboard = build_dashboard(RESULTS, PUBLISHED)
        summary = _summary(RESULTS, PUBLISHED)
        print(f"Published dashboard: {dashboard}")
        print(f"Published summary:   {summary}")
        return
    if args.command == "validate":
        result = validate_negative_baseline(ROOT, load_tasks(TASKS))
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            raise SystemExit(2)
        return

    if not harnesses:
        raise SystemExit("Select a harness, e.g. aiosbench --piagent --model Qwen, or use --all")
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    if args.max_output_tokens < 0:
        raise SystemExit("--max-output-tokens must be >= 0")
    if args.metrics_poll_interval <= 0:
        raise SystemExit("--metrics-poll-interval must be > 0")

    tasks = load_tasks(TASKS)
    if len(harnesses) == 1:
        exit_code = _run_single_harness(args, harnesses[0], tasks)
    else:
        exit_code = _run_matched_interleaved(args, harnesses, tasks)

    summary = _summary(RESULTS)
    print(f"\nSummary:   {summary}")
    if args.dashboard:
        dashboard = build_dashboard(RESULTS)
        print(f"Dashboard: {dashboard}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
