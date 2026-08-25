from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AGENTS
from .dashboard import build_dashboard
from .doctor import apply_profile_environment, run_wizard
from .experiments import annotate_repeat, make_experiment_id
from .frontier_v3_runner import FrontierV3Runner
from .frontier_v4_runner import FrontierV4Runner
from .models import Trajectory
from .parametric import ConfigTraversalPressure, ExpensePressure
from .publication import render_derived, verify_publication, write_publication_manifest
from .report import write_summary
from .scheduler import MatchedInterleavedScheduler
from .scoring import overall_score
from .smoke import discover_smoke_run_dirs, make_smoke_id, select_smoke_tasks, write_smoke_report
from .statistics import augment_summary_file
from .tasks import load_tasks
from .validation import validate_parametric_baseline, validate_static_baseline

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"
PUBLISHED = ROOT / "results"
RESULTS = PUBLISHED / ".local"
SMOKE_RESULTS = PUBLISHED / ".smoke"
SUITES = ("frontier_v3", "frontier_v4")


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


def _v4_parameters(args: argparse.Namespace) -> dict[str, dict[str, int]]:
    try:
        expense = ExpensePressure(
            rows=args.v4_expense_rows,
            malformed_rows=args.v4_expense_malformed,
            distractor_files=args.v4_expense_distractors,
            months=args.v4_expense_months,
        )
    except ValueError as exc:
        raise SystemExit(f"invalid Frontier v4 expense pressure: {exc}") from exc
    try:
        config = ConfigTraversalPressure(
            chain_depth=args.v4_config_chain_depth,
            distractor_files=args.v4_config_distractors,
            extra_settings=args.v4_config_extra_settings,
        )
    except ValueError as exc:
        raise SystemExit(f"invalid Frontier v4 config pressure: {exc}") from exc
    return {
        "expense_report": expense.to_dict(),
        "config_traversal": config.to_dict(),
    }


def _build_runner(
    args: argparse.Namespace,
    harness: str,
    *,
    run_id: str | None,
    orchestration_seed: int,
):
    common = dict(
        repo_root=ROOT,
        agent=AGENTS[harness],
        results_dir=getattr(args, "_results_dir", RESULTS),
        task_timeout=args.timeout,
        total_timeout=args.total_timeout,
        run_id=run_id,
        **_runner_kwargs(args),
    )
    if args.suite == "frontier_v4":
        return FrontierV4Runner(
            **common,
            variant_base_seed=orchestration_seed,
            parametric_parameters=_v4_parameters(args),
        )
    return FrontierV3Runner(**common)


def _run_single_harness(args: argparse.Namespace, harness: str, tasks: list) -> int:
    exit_code = 0
    for repeat in range(1, args.repeats + 1):
        orchestration_seed = args.seed + repeat - 1
        run_id = args.run_id
        if run_id and args.repeats > 1:
            run_id = f"{run_id}-r{repeat:02d}"
        print(
            f"\n=== {args.suite} | Repeat {repeat}/{args.repeats} | {AGENTS[harness].display_name} "
            f"| orchestration_seed={orchestration_seed} ===\n"
        )
        runner = _build_runner(
            args,
            harness,
            run_id=run_id,
            orchestration_seed=orchestration_seed,
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
    experiment_id = args.run_id or make_experiment_id(args.suite)
    for repeat in range(1, args.repeats + 1):
        orchestration_seed = args.seed + repeat - 1
        run_id = experiment_id if args.repeats == 1 else f"{experiment_id}-r{repeat:02d}"
        runners = {
            harness: _build_runner(
                args,
                harness,
                run_id=run_id,
                orchestration_seed=orchestration_seed,
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
    parser.add_argument(
        "--suite",
        choices=SUITES,
        default="frontier_v3",
        help="Benchmark suite; Frontier v3 remains the static default",
    )
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
        help="Base orchestration seed; in Frontier v4 it also deterministically derives task variants",
    )
    parser.add_argument("--v4-expense-rows", type=int, default=48, help="Frontier v4 expense-family row pressure coordinate")
    parser.add_argument("--v4-expense-malformed", type=int, default=2, help="Frontier v4 expense-family malformed-row pressure coordinate")
    parser.add_argument("--v4-expense-distractors", type=int, default=3, help="Frontier v4 expense-family distractor-file pressure coordinate")
    parser.add_argument("--v4-expense-months", type=int, default=6, help="Frontier v4 expense-family temporal-span pressure coordinate")
    parser.add_argument("--v4-config-chain-depth", type=int, default=3, help="Frontier v4 config-family reference-chain depth coordinate")
    parser.add_argument("--v4-config-distractors", type=int, default=3, help="Frontier v4 config-family distractor-file coordinate")
    parser.add_argument("--v4-config-extra-settings", type=int, default=2, help="Frontier v4 config-family extra-setting coordinate")
    parser.add_argument(
        "--server-metrics-url",
        default=None,
        help="llama.cpp Prometheus endpoint or server origin (requires llama-server --metrics)",
    )
    parser.add_argument("--server-metrics-model", default=None, help="Optional llama.cpp router model id added to the /metrics query")
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
    parser.add_argument("--setup", action="store_true", help="With doctor: guided install and benchmark-profile setup")
    parser.add_argument("--check", action="store_true", help="With doctor: non-interactive readiness check")
    parser.add_argument("--repair", action="store_true", help="With doctor: re-run guided setup for missing/broken components")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run", "smoke", "list", "score", "dashboard", "publish", "verify", "validate", "doctor"],
        default="run",
    )
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()

    if args.command == "doctor":
        if sum(bool(value) for value in (args.setup, args.check, args.repair)) > 1:
            raise SystemExit("doctor accepts only one of --setup, --check or --repair")
        raise SystemExit(run_wizard(setup=args.setup, check_only=args.check, repair=args.repair))
    if args.setup or args.check or args.repair:
        raise SystemExit("--setup, --check and --repair are only valid with the doctor command")

    profile = apply_profile_environment()
    if args.model == "unknown" and isinstance(profile.get("model"), str) and profile["model"].strip():
        args.model = profile["model"].strip()

    harnesses = _selected_harnesses(args)

    if args.command == "list":
        for task in load_tasks(TASKS, args.suite):
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
        outputs = render_derived(RESULTS, PUBLISHED)
        manifest = write_publication_manifest(RESULTS, PUBLISHED)
        print(f"Published dashboard: {outputs['dashboard.html']}")
        print(f"Published summary:   {outputs['summary.json']}")
        print(f"Publication seal:    {manifest}")
        return
    if args.command == "verify":
        result = verify_publication(RESULTS, PUBLISHED)
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            raise SystemExit(2)
        return

    tasks = load_tasks(TASKS, args.suite)
    if args.command == "validate":
        if args.suite == "frontier_v4":
            result = validate_parametric_baseline(
                ROOT,
                tasks,
                base_seed=args.seed,
                parameters=_v4_parameters(args),
            )
        else:
            result = validate_static_baseline(ROOT, tasks)
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

    if args.command == "smoke":
        if args.suite != "frontier_v3":
            raise SystemExit("smoke currently targets the Frontier v3 integration contracts")
        if not args.model or args.model == "unknown":
            raise SystemExit("smoke requires an explicit --model so model binding can be verified")
        try:
            tasks = select_smoke_tasks(tasks, harnesses)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        smoke_id = args.run_id or make_smoke_id()
        args.run_id = smoke_id
        args.no_resume = True
        args._results_dir = SMOKE_RESULTS
        print("Smoke profile: " + ", ".join(task.id for task in tasks))
        print(f"Smoke output:  {SMOKE_RESULTS}")

        if len(harnesses) == 1:
            exit_code = _run_single_harness(args, harnesses[0], tasks)
        else:
            exit_code = _run_matched_interleaved(args, harnesses, tasks)

        run_dirs = discover_smoke_run_dirs(SMOKE_RESULTS, smoke_id)
        report_path = write_smoke_report(SMOKE_RESULTS, smoke_id, run_dirs, tasks)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        print(f"\nSmoke report:         {report_path}")
        print(f"Integration OK:       {report['integration_ok']}")
        print(f"Strict model ready:   {report['strict_model_ready']}")
        print(f"Server metrics ready: {report['server_metrics_ready']}")
        raise SystemExit(0 if report["integration_ok"] else max(exit_code, 1))

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
