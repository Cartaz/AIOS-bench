from __future__ import annotations
import argparse,json
from pathlib import Path
from .dashboard import build_dashboard
from .models import Task,Trajectory
from .report import write_summary
from .runner import AGENTS
from .frontier_v3_runner import FrontierV3Runner
from .scoring import overall_score
from .tasks import load_tasks
ROOT=Path(__file__).resolve().parents[1]; TASKS=ROOT/"benchmarks"/"tasks"; PUBLISHED=ROOT/"results"; RESULTS=PUBLISHED/".local"
def _add_harness_flags(p):
    for name,cfg in AGENTS.items():p.add_argument(f"--{name}",action="store_true",help=f"Run the {cfg.display_name} suite")
    p.add_argument("--all",action="store_true",help="Run every configured harness sequentially")
def _selected_harnesses(args):
    selected=[n for n in AGENTS if getattr(args,n,False)]
    if args.all:selected.append("__all__")
    if len(selected)>1:raise SystemExit("Select one harness or --all, not both.")
    return list(AGENTS) if selected==["__all__"] else selected

def _select_tasks(tasks:list[Task], task_ids:list[str]|None, categories:list[str]|None)->list[Task]:
    requested_ids=set(task_ids or ());requested_categories=set(categories or ())
    if not requested_ids and not requested_categories:return tasks
    by_id={task.id:task for task in tasks};known_categories={task.category for task in tasks}
    unknown_ids=sorted(requested_ids-by_id.keys());unknown_categories=sorted(requested_categories-known_categories)
    if unknown_ids:raise SystemExit(f"Unknown task id(s): {', '.join(unknown_ids)}")
    if unknown_categories:raise SystemExit(f"Unknown category/categories: {', '.join(unknown_categories)}")
    selected={task.id for task in tasks if task.id in requested_ids or task.category in requested_categories}
    stack=list(selected)
    while stack:
        task=by_id[stack.pop()]
        for dependency in task.depends_on:
            if dependency not in selected:
                selected.add(dependency);stack.append(dependency)
    return [task for task in tasks if task.id in selected]

def main():
    p=argparse.ArgumentParser(prog="aiosbench",description="AIOS-bench local agent benchmark")
    _add_harness_flags(p); p.add_argument("--model",default="unknown",help="Model identifier for longitudinal comparisons"); p.add_argument("--timeout",type=float,default=900,help="Per-task timeout in seconds"); p.add_argument("--total-timeout",type=float,default=None,help="Optional whole-suite timeout per harness"); p.add_argument("--no-resume",action="store_true",help="Run every selected task even if a previous result exists"); p.add_argument("--run-id",default=None,help="Explicit run identifier; omit to create a timestamped isolated run"); p.add_argument("--dashboard",action="store_true",help="Build the local comparison dashboard after the run"); p.add_argument("--keep-raw",action="store_true",help="Keep raw event/stdout/dependency artifacts after the run"); p.add_argument("--task",action="append",default=None,help="Run one task id; repeat to select multiple tasks (dependencies are included)"); p.add_argument("--category",action="append",default=None,help="Run one task category; repeat to select multiple categories (dependencies are included)"); p.add_argument("command",nargs="?",choices=["run","list","score","dashboard","publish"],default="run"); p.add_argument("path",nargs="?",type=Path); args=p.parse_args()
    harnesses=_selected_harnesses(args)
    if args.command=="list":
        tasks=_select_tasks(load_tasks(TASKS),args.task,args.category)
        for t in tasks:print(f"{t.id}\t{t.category}\t{t.mode}\t{t.prompt}")
        return
    if args.command=="score":
        if not args.path:raise SystemExit("score requires a JSON trajectory path")
        print(f"{overall_score(Trajectory(**json.loads(args.path.read_text(encoding='utf-8')))):.2f}"); return
    if args.command=="dashboard":
        d=build_dashboard(RESULTS);s=write_summary(RESULTS);print(f"Dashboard: {d}");print(f"Summary:   {s}");return
    if args.command=="publish":
        d=build_dashboard(RESULTS,PUBLISHED);s=write_summary(RESULTS,PUBLISHED);print(f"Published dashboard: {d}");print(f"Published summary:   {s}");return
    if not harnesses:raise SystemExit("Select a harness, e.g. aiosbench --piagent --model Qwen, or use --all")
    tasks=_select_tasks(load_tasks(TASKS),args.task,args.category);exit_code=0
    for index,harness in enumerate(harnesses,1):
        print(f"\n=== Harness {index}/{len(harnesses)}: {AGENTS[harness].display_name} ===\n")
        runner=FrontierV3Runner(ROOT,AGENTS[harness],RESULTS,args.timeout,args.total_timeout,resume=not args.no_resume,model=args.model,keep_raw=args.keep_raw,run_id=args.run_id)
        try:
            exit_code=max(exit_code,runner.run(tasks))
        except BaseException:
            runner.abort(tasks)
            raise
    s=write_summary(RESULTS);print(f"\nSummary:   {s}")
    if args.dashboard:
        d=build_dashboard(RESULTS);print(f"Dashboard: {d}")
    raise SystemExit(exit_code)
if __name__=="__main__":main()
