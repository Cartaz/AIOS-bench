from .reference_checks_core import read,load,run,same,eval_path,ok
from pathlib import Path
import re,json

_STOPWORDS={"the","and","for","from","with","this","that","into","only","when","then"}
def _terms(x): return {t for t in re.findall(r"[a-z0-9_.-]+",str(x).lower()) if len(t)>2 and t not in _STOPWORDS}
def _aligned(a,b):
    x,y=_terms(a),_terms(b)
    if not x or not y:return False
    z=x&y
    return len(z)>=2 and len(z)/len(x)>=0.4

def check(t,w,fx):
    if t=="autonomy_001":
        first,alternate=eval_path(w,"a1.md"),eval_path(w,"a1a.md")
        a=run(w,["python","tools/expense_report.py","--input","data/expenses.csv","--output",str(first)]); b=run(w,["python","tools/expense_report.py","--input","data/expenses_alt.csv","--output",str(alternate)])
        if a.returncode or b.returncode:return ok(False,"expense tool failed")
        x,y=first.read_text(errors="replace"),alternate.read_text(errors="replace")
        return ok("91.07" in x and "742.50" in y and re.search(r"(skipped|malformed).{0,30}1",x,re.I|re.S) and "91.07" not in read(w,"tools/expense_report.py"),"expense tool executes on both datasets")
    if t=="autonomy_002":
        d=load(w,"reports/action_tracker.json")
        if not isinstance(d,list) or len(d)!=4:return ok(False,"expected four actions")
        seen=set()
        for e in d:
            s=w/e.get("source_doc","");q=e.get("evidence_quote","");action=e.get("action","")
            if not s.is_file() or not q or q not in s.read_text(encoding="utf-8") or not _aligned(action,q):return ok(False,"fabricated or misaligned evidence")
            key=re.sub(r"\W+"," ",str(action).lower()).strip()
            if not key or key in seen:return ok(False,"duplicate or empty action")
            seen.add(key)
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
    if t=="learning_001":
        x=read(w,"skills/reporting_workflow.md")
        if "580" in x or "91.07" in x:return ok(False,"workflow hard-codes fixture totals")
        first,alternate=eval_path(w,"l1"),eval_path(w,"l1a")
        a=run(w,["python","skills/reporting_workflow.py","--input","data/sales.csv","--output",str(first)]);b=run(w,["python","skills/reporting_workflow.py","--input","data/sales_alt.csv","--output",str(alternate)])
        good=a.returncode==b.returncode==0 and "580" in first.read_text(errors="replace") and "742" in alternate.read_text(errors="replace") and re.search(r"generalization\s*:",x,re.I)
        return ok(bool(good),"learned workflow transfers")
    if t=="learning_002":
        x=read(w,"reports/learning_transfer.md");out=eval_path(w,"l2");p=run(w,["python","skills/reporting_workflow.py","--input","data/sales_schema_shift.csv","--output",str(out)])
        rendered=out.read_text(errors="replace") if out.exists() else ""
        good=p.returncode==0 and "580" in rendered and all(re.search(z,x,re.I) for z in [r"transferred\s+steps\s*:",r"adapted\s+steps\s*:",r"adaptation\s+reason\s*:",r"txn_date|gross_usd"])
        return ok(good,"learning transfer verified on shifted-schema outcome")
    if t=="learning_003":
        x,r=read(w,"skills/reporting_workflow.md"),read(w,"reports/learning_correction.md");output=eval_path(w,"l3");p=run(w,["python","skills/reporting_workflow.py","--input","data/sales.csv","--output",str(output)]);out=output.read_text(errors="replace") if output.exists() else ""
        good="sum of the `units`" not in x and re.search(r"sum.*revenue",x,re.I) and re.search(r"independent\s+validation\s*:\s*\S+",r,re.I) and p.returncode==0 and "580" in out
        return ok(bool(good),"planted learning error corrected")
    return None
