from __future__ import annotations
import argparse,json
from pathlib import Path
from .dashboard import build_dashboard
from .models import Trajectory
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
def main():
    p=argparse.ArgumentParser(prog="aiosbench",description="AIOS-bench local agent benchmark")
    _add_harness_flags(p); p.add_argument("--model",default="unknown",help="Model identifier for longitudinal comparisons"); p.add_argument("--timeout",type=float,default=900,help="Per-task timeout in seconds"); p.add_argument("--total-timeout",type=float,default=None,help="Optional whole-suite timeout per harness"); p.add_argument("--no-resume",action="store_true",help="Run every task even if a previous result exists"); p.add_argument("--run-id",default=None,help="Explicit run identifier; omit to create a timestamped isolated run"); p.add_argument("--dashboard",action="store_true",help="Build the local comparison dashboard after the run"); p.add_argument("--keep-raw",action="store_true",help="Keep raw event/stdout/dependency artifacts after the run"); p.add_argument("command",nargs="?",choices=["run","list","score","dashboard","publish"],default="run"); p.add_argument("path",nargs="?",type=Path); args=p.parse_args()
    harnesses=_selected_harnesses(args)
    if args.command=="list":
        for t in load_tasks(TASKS):print(f"{t.id}\t{t.category}\t{t.mode}\t{t.prompt}")
        return
    if args.command=="score":
        if not args.path:raise SystemExit("score requires a JSON trajectory path")
        print(f"{overall_score(Trajectory(**json.loads(args.path.read_text(encoding='utf-8')))):.2f}"); return
    if args.command=="dashboard":
        d=build_dashboard(RESULTS);s=write_summary(RESULTS);print(f"Dashboard: {d}");print(f"Summary:   {s}");return
    if args.command=="publish":
        d=build_dashboard(RESULTS,PUBLISHED);s=write_summary(RESULTS,PUBLISHED);print(f"Published dashboard: {d}");print(f"Published summary:   {s}");return
    if not harnesses:raise SystemExit("Select a harness, e.g. aiosbench --piagent --model Qwen, or use --all")
    tasks=load_tasks(TASKS);exit_code=0
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
