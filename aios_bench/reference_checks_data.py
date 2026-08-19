from .reference_checks_core import read,load,run,same,ok
from pathlib import Path
import re,json

def check(t,w,fx):
    if t=="autonomy_001":
        a=run(w,["python","tools/expense_report.py","--input","data/expenses.csv","--output","/tmp/a1.md"]); b=run(w,["python","tools/expense_report.py","--input","data/expenses_alt.csv","--output","/tmp/a1a.md"])
        if a.returncode or b.returncode:return ok(False,"expense tool failed")
        x,y=Path("/tmp/a1.md").read_text(errors="replace"),Path("/tmp/a1a.md").read_text(errors="replace")
        return ok("91.07" in x and "742.50" in y and re.search(r"(skipped|malformed).{0,30}1",x,re.I|re.S) and "91.07" not in read(w,"tools/expense_report.py"),"expense tool executes on both datasets")
    if t=="autonomy_002":
        d=load(w,"reports/action_tracker.json")
        if not isinstance(d,list) or len(d)!=4:return ok(False,"expected four actions")
        for e in d:
            s=w/e.get("source_doc","");q=e.get("evidence_quote","")
            if not s.is_file() or not q or q not in s.read_text(encoding="utf-8"):return ok(False,"fabricated evidence")
        return ok(not any("Q3 budget" in json.dumps(e) for e in d),"grounded action tracker")
    if t in {"autonomy_003","coding_002","tool_use_003"}:
        for f in ["tests/test_broken_tool.py","tests/test_off_by_one.py","data/expenses.csv","data/sales.csv","notes/meeting_notes.md","procedures/current.md","procedures/previous.md"]:
            if not same(w,f,fx):return ok(False,f"protected file modified: {f}")
        return ok(run(w,["python","-m","pytest","-q","tests/test_broken_tool.py","tests/test_off_by_one.py"],45).returncode==0,"hidden regression tests pass")
    if t=="coding_001":
        if not same(w,"tests/test_hidden_report_cli.py",fx):return ok(False,"hidden test modified")
        return ok(run(w,["python","-m","pytest","-q","tests/test_hidden_report_cli.py"],45).returncode==0,"hidden CLI tests pass")
    if t=="coding_003":
        req=["projects/report_tool/parse.py","projects/report_tool/validate.py","projects/report_tool/report.py"]
        if not all((w/p).is_file() for p in req) or not same(w,"tests/test_cli_contract.py",fx):return ok(False,"refactor contract incomplete")
        return ok(run(w,["python","-m","pytest","-q","tests/test_cli_contract.py"],45).returncode==0,"CLI contract preserved")
    if t=="coding_004":
        if not same(w,"tests/test_robust.py",fx):return ok(False,"hidden robustness test modified")
        p=run(w,["python","-m","pytest","-q","tests/test_robust.py"],45);x,r=read(w,"tools/robust_report.py"),read(w,"README.md")
        return ok(p.returncode==0 and re.search(r"@dataclass|TypedDict|class\s+\w+\s*\(",x) is not None and all(re.search(rf"^#+\s+{s}\b",r,re.I|re.M) for s in ["Usage","Examples","Error handling"]),"robust utility verified")
    if t=="knowledge_001":
        d=load(w,"reports/unresolved_actions.json")
        if not isinstance(d,list) or len(d)!=3:return ok(False,"expected three actions")
        good=all((w/e.get("source_doc","")).is_file() and e.get("evidence_quote","") in read(w,e["source_doc"]) for e in d)
        return ok(good and not any("Q3 budget" in json.dumps(e) for e in d),"three grounded unresolved actions")
    if t=="knowledge_002":
        load(w,"reports/procedure_diff.json");x=read(w,"reports/procedure_diff.md")
        return ok(all(re.search(rf"{s}\s*:",x,re.I) for s in ["additions","removals","changed","unchanged"]) and bool(re.search(r"\[(previous|current|next_draft)\.md:\d+\]",x)),"structured procedure diff")
    if t=="knowledge_003":
        d,x=load(w,"reports/claim_evidence.json"),read(w,"reports/evidence_review.md")
        if not isinstance(d,list) or len(d)<3:return ok(False,"claim matrix too small")
        good=all((w/e.get("source_doc","")).is_file() and e.get("evidence_quote","") in read(w,e["source_doc"]) for e in d)
        good &= bool(re.search(r"authoritative_source\s*:\s*(notes/)?meeting_notes",x,re.I)) and bool(re.search(r"criteria\s*:\s*\S+",x,re.I)) and bool(re.search(r"uncertainty\s*:\s*(low|medium|high)",x,re.I))
        return ok(good,"claim/evidence review verified")
    if t=="learning_001":
        x=read(w,"skills/reporting_workflow.md")
        if "580" in x or "91.07" in x:return ok(False,"workflow hard-codes fixture totals")
        a=run(w,["python","skills/reporting_workflow.py","--input","data/sales.csv","--output","/tmp/l1"]);b=run(w,["python","skills/reporting_workflow.py","--input","data/sales_alt.csv","--output","/tmp/l1a"])
        good=a.returncode==b.returncode==0 and "580" in Path("/tmp/l1").read_text(errors="replace") and "742" in Path("/tmp/l1a").read_text(errors="replace") and re.search(r"generalization\s*:",x,re.I)
        return ok(bool(good),"learned workflow transfers")
    if t=="learning_002":
        x=read(w,"reports/learning_transfer.md");p=run(w,["python","skills/reporting_workflow.py","--input","data/sales_schema_shift.csv","--output","/tmp/l2"])
        good=p.returncode==0 and all(re.search(z,x,re.I) for z in [r"transferred\s+steps\s*:",r"adapted\s+steps\s*:",r"adaptation\s+reason\s*:",r"txn_date|gross_usd"])
        return ok(good,"learning transfer verified")
    if t=="learning_003":
        x,r=read(w,"skills/reporting_workflow.md"),read(w,"reports/learning_correction.md");p=run(w,["python","skills/reporting_workflow.py","--input","data/sales.csv","--output","/tmp/l3"]);out=Path("/tmp/l3").read_text(errors="replace") if Path("/tmp/l3").exists() else ""
        good="sum of the `units`" not in x and re.search(r"sum.*revenue",x,re.I) and re.search(r"independent\s+validation\s*:\s*\S+",r,re.I) and p.returncode==0 and "580" in out
        return ok(bool(good),"planted learning error corrected")
    return None
