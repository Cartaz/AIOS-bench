from .reference_checks_core import read,load,run,eval_path,ok
import hashlib,json,re
from pathlib import Path

def check(t,w,fx,run_dir=None):
    if t=="browser_001":
        x=read(w,"reports/browser_research.md");cfg=load(fx.parent,"expected_sources.json");urls=re.findall(r"https?://[^\s)\"]+",x);dom={re.sub(r"^www\.","",re.match(r"https?://([^/]+)",u).group(1).lower()) for u in urls}
        good=len(dom&set(cfg["whitelist"]))>=3 and "pep-9999" not in x and "transaction_v1.html" not in x and bool(re.search(r"default isolation level\s*:\s*DEFERRED\b",x,re.I)) and bool(re.search(r"accessed\s*:\s*\d{4}-\d{2}-\d{2}",x,re.I))
        return ok(good,"browser research grounded")
    if t=="browser_002":
        x=read(w,"reports/browser_implementation_memo.md");cfg=load(fx.parent,"expected_sources.json");urls=re.findall(r"https?://[^\s)\"]+",x);dom={re.sub(r"^www\.","",re.match(r"https?://([^/]+)",u).group(1).lower()) for u in urls}
        good=len(dom&set(cfg["whitelist"]))>=4 and all(re.search(rf"^#+\s+{s}\b",x,re.I|re.M) for s in ["Prerequisites","Commands","Compatibility","Verification"])
        good &= bool(re.search(r"decision\s*:\s*(adopt|reject|postpone)\b",x,re.I)) and bool(re.search(r"(conflict|discrepancy)\s*:\s*\S+",x,re.I))
        return ok(good,"implementation memo grounded")
    if t=="long_horizon_001":
        x=read(w,"reports/long_horizon_changelog.md");good=(fx.parent/"long_horizon_corpus.md").stat().st_size>=30000 and "validator state corruption" in x.lower() and bool(re.search(r"recovery\s*:\s*\S+",x,re.I)) and all((w/f".state/checkpoint_{n}.json").is_file() for n in (1,3,5))
        return ok(good,"large corpus, recovery and checkpoints verified")
    if t=="long_horizon_002":
        req=["tools/step1_summary.py","tools/step2_chart.py","tools/step3_report.py"]
        if not all((w/p).is_file() for p in req):return ok(False,"pipeline stage missing")
        summary,chart,report,fail=eval_path(w,"lh2.json"),eval_path(w,"lh2.svg"),eval_path(w,"lh2.md"),eval_path(w,"fail.svg")
        a=run(w,["python","tools/step1_summary.py","--input","data/expenses.csv","--output",str(summary)]);b=run(w,["python","tools/step2_chart.py","--input",str(summary),"--output",str(chart)]);c=run(w,["python","tools/step3_report.py","--summary",str(summary),"--chart",str(chart),"--output",str(report)])
        summary.unlink(missing_ok=True);d=run(w,["python","tools/step2_chart.py","--input",str(summary),"--output",str(fail)])
        return ok(a.returncode==b.returncode==c.returncode==0 and d.returncode!=0,"pipeline dependency chain verified")
    if t=="long_horizon_003":
        d=load(w,"reports/audit_matrix.json");p=run(w,["python","tools/investigation_helper.py","--audit","reports/audit_matrix.json","--output",str(eval_path(w,"lh3"))]);good=isinstance(d,list) and len(d)==5 and all(any(e.get("requirement_id")==f"R{i}" for e in d) for i in range(1,6)) and p.returncode==0
        return ok(good,"five requirement audit verified")
    if t.startswith("memory_"):
        m=w/".agent_memory/preferences.json"
        if not m.is_file():return ok(False,"durable memory missing")
        d=load(w,".agent_memory/preferences.json")
        durable=(d.get("preference_token")=="7K9X2A" and d.get("tooling_style")=="simple" and d.get("vcs_policy")=="no-commit")
        if t=="memory_001":
            raw=json.dumps(d).lower();good=durable and d.get("primary_language")=="Python" and "transient_instruction" not in d and "red theme" not in raw
            return ok(good,"cold memory stores durable preferences only")
        if t=="memory_002":
            p=run(w,["python","tools/preferred_tool.py","--input","data/expenses.csv","--output",str(eval_path(w,"m2"))]);tool=read(w,"tools/preferred_tool.py")
            return ok(p.returncode==0 and durable and d.get("primary_language")=="Python" and "7K9X2A" in tool,"warm memory used")
        if t=="memory_003":
            good=durable and d.get("primary_language")=="TypeScript" and d.get("previous_primary_language")=="Python" and (w/"tools/updated_tool.ts").is_file()
            return ok(good,"memory update preserved unrelated durable state and history")
        p=run(w,["python","tools/security_tool.py","--input","data/expenses.csv","--output",str(eval_path(w,"sec"))]);g=run(w,["git","rev-list","--count","HEAD"]);good=durable and d.get("primary_language")=="TypeScript" and d.get("previous_primary_language")=="Python" and (w/"tools/general_tool.ts").is_file() and (w/"tools/security_tool.py").is_file() and p.returncode==0 and g.stdout.strip()=="1"
        return ok(good,"memory consistency and no-new-commit verified")
    if t.startswith("subagents_"):
        if run_dir is None:return ok(False,"telemetry unavailable")
        row=None
        for ln in (run_dir/"results.jsonl").read_text().splitlines():
            try:r=json.loads(ln)
            except json.JSONDecodeError:continue
            if r.get("task_id")==t:row=r
        ev=(row or {}).get("events",[]);starts=sum(e.get("type")=="subagent_start" and not (e.get("data") or {}).get("inferred",False) for e in ev);need=1 if t=="subagents_001" else 2;rp="reports/subagent_comparison.md" if t=="subagents_001" else "reports/decision_memo.md";x=read(w,rp);good=starts>=need
        if t=="subagents_001":good &= (w/"reports/reconciliation.json").is_file() and len(load(w,"reports/reconciliation.json"))>=3 and "## Verified" in x and "## Rejected" in x
        elif t=="subagents_002":good &= "CVE" in x and "99.99%" not in x
        else:good &= "## Rejected" in x and bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b",x,re.I))
        return ok(bool(good),f"delegation telemetry={starts}")
    if t=="tool_use_001":
        d=load(w,"reports/file_classification.json");by={e.get("path"):e for e in d} if isinstance(d,list) else {};exp={"data/expenses.csv":"authoritative","data/sales.csv":"authoritative","data/legacy_sales.csv":"authoritative","archive/sales_2023.csv":"decoy"};good=isinstance(d,list) and len(d)>=4
        for p,c in exp.items():good &= by.get(p,{}).get("classification")==c and by.get(p,{}).get("evidence_hash")==hashlib.sha256((w/p).read_bytes()).hexdigest()
        return ok(bool(good),"classification and inspection hashes verified")
    if t=="tool_use_002":
        x=read(w,"reports/effective_config.md");good="8081" in x and bool(re.search(r"production\b",x,re.I)) and bool(re.search(r"README\.md\s*->\s*docs/README\.md\s*->\s*config/app\.yaml",x,re.I)) and bool(re.search(r"consumer\s*:\s*tools/run_server\.py",x,re.I)) and "8080" not in x
        return ok(good,"indirect configuration chain verified")
    return None
