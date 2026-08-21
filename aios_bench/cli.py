from __future__ import annotations
import argparse,json,random
from pathlib import Path
from .dashboard import build_dashboard
from .experiments import annotate_repeat
from .models import Trajectory
from .report import write_summary
from .config import AGENTS
from .frontier_v3_runner import FrontierV3Runner
from .scoring import overall_score
from .statistics import augment_summary_file
from .tasks import load_tasks
from .validation import validate_negative_baseline
ROOT=Path(__file__).resolve().parents[1]; TASKS=ROOT/"benchmarks"/"tasks"; PUBLISHED=ROOT/"results"; RESULTS=PUBLISHED/".local"
def _add_harness_flags(p):
    for name,cfg in AGENTS.items():p.add_argument(f"--{name}",action="store_true",help=f"Run the {cfg.display_name} suite")
    p.add_argument("--all",action="store_true",help="Run every configured harness in repeated experimental blocks")
def _selected_harnesses(args):
    selected=[n for n in AGENTS if getattr(args,n,False)]
    if args.all:selected.append("__all__")
    if len(selected)>1:raise SystemExit("Select one harness or --all, not both.")
    return list(AGENTS) if selected==["__all__"] else selected
def _summary(root:Path, output:Path|None=None):
    path=write_summary(root,output);augment_summary_file(path,root);return path
def main():
    p=argparse.ArgumentParser(prog="aiosbench",description="AIOS-bench local agent benchmark")
    _add_harness_flags(p); p.add_argument("--model",default="unknown",help="Model identifier for longitudinal comparisons"); p.add_argument("--timeout",type=float,default=900,help="Per-task timeout in seconds"); p.add_argument("--total-timeout",type=float,default=None,help="Optional whole-suite timeout per harness"); p.add_argument("--no-resume",action="store_true",help="Run every task even if a previous result exists"); p.add_argument("--run-id",default=None,help="Explicit run identifier; omit to create a timestamped isolated run"); p.add_argument("--repeats",type=int,default=1,help="Independent repeated suite runs"); p.add_argument("--seed",type=int,default=42,help="Base orchestration seed for repeat ordering; does not set model sampling RNG"); p.add_argument("--dashboard",action="store_true",help="Build the local comparison dashboard after the run"); p.add_argument("--keep-raw",action="store_true",help="Keep raw event/stdout/dependency artifacts after the run"); p.add_argument("command",nargs="?",choices=["run","list","score","dashboard","publish","validate"],default="run"); p.add_argument("path",nargs="?",type=Path); args=p.parse_args()
    harnesses=_selected_harnesses(args)
    if args.command=="list":
        for t in load_tasks(TASKS):print(f"{t.id}\t{t.category}\t{t.mode}\t{t.prompt}")
        return
    if args.command=="score":
        if not args.path:raise SystemExit("score requires a JSON trajectory path")
        print(f"{overall_score(Trajectory(**json.loads(args.path.read_text(encoding='utf-8')))):.2f}"); return
    if args.command=="dashboard":
        d=build_dashboard(RESULTS);s=_summary(RESULTS);print(f"Dashboard: {d}");print(f"Summary:   {s}");return
    if args.command=="publish":
        d=build_dashboard(RESULTS,PUBLISHED);s=_summary(RESULTS,PUBLISHED);print(f"Published dashboard: {d}");print(f"Published summary:   {s}");return
    if args.command=="validate":
        result=validate_negative_baseline(ROOT,load_tasks(TASKS));print(json.dumps(result,indent=2))
        if not result["ok"]:raise SystemExit(2)
        return
    if not harnesses:raise SystemExit("Select a harness, e.g. aiosbench --piagent --model Qwen, or use --all")
    if args.repeats<1:raise SystemExit("--repeats must be >= 1")
    tasks=load_tasks(TASKS);exit_code=0
    for repeat in range(1,args.repeats+1):
        orchestration_seed=args.seed+repeat-1
        order=list(harnesses);random.Random(orchestration_seed).shuffle(order)
        for index,harness in enumerate(order,1):
            print(f"\n=== Repeat {repeat}/{args.repeats} | Harness {index}/{len(order)}: {AGENTS[harness].display_name} | orchestration_seed={orchestration_seed} ===\n")
            run_id=args.run_id
            if run_id and args.repeats>1:run_id=f"{run_id}-r{repeat:02d}"
            runner=FrontierV3Runner(ROOT,AGENTS[harness],RESULTS,args.timeout,args.total_timeout,resume=not args.no_resume,model=args.model,keep_raw=args.keep_raw,run_id=run_id)
            try:
                exit_code=max(exit_code,runner.run(tasks))
            except BaseException:
                runner.abort(tasks);annotate_repeat(runner.run_dir,repeat=repeat,orchestration_seed=orchestration_seed)
                raise
            annotate_repeat(runner.run_dir,repeat=repeat,orchestration_seed=orchestration_seed)
    s=_summary(RESULTS);print(f"\nSummary:   {s}")
    if args.dashboard:
        d=build_dashboard(RESULTS);print(f"Dashboard: {d}")
    raise SystemExit(exit_code)
if __name__=="__main__":main()
