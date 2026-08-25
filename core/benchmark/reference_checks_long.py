from .fixtures import LONG_HORIZON_MIN_BYTES
from .reference_checks_core import read,load,run,same,eval_path,ok
from pathlib import Path
import re

def check(t,w,fx):
    if t=='long_horizon_001':
        x=read(w,'reports/long_horizon_changelog.md')
        corpus=w/'research/long_horizon_corpus'
        corpus_bytes=sum(p.stat().st_size for p in corpus.rglob('*') if p.is_file()) if corpus.is_dir() else 0
        validator_state=w/'.state/validator_runs.json'
        history=load(w,'.state/validator_runs.json').get('history',[]) if validator_state.is_file() else []
        recovered=(
            any(item.get('status')=='failed' and item.get('error')=='validator state corruption' for item in history)
            and int(load(w,'.state/validator_runs.json').get('runs',0))>=4
        ) if validator_state.is_file() else False
        good=(corpus_bytes>=LONG_HORIZON_MIN_BYTES and same(w,'tools/validator.py',fx) and recovered and 'validator state corruption' in x.lower() and bool(re.search(r'recovery\s*:\s*\S+',x,re.I)) and all((w/f'.state/checkpoint_{n}.json').is_file() for n in (1,3,5)) and all(token in x for token in ('LH-047','240 ms','Priya N.')))
        return ok(good,f'large corpus ({corpus_bytes} bytes), grounded release gate, recovery and checkpoints verified')
    if t=='long_horizon_002':
        req=['tools/step1_summary.py','tools/step2_chart.py','tools/step3_report.py']
        if not all((w/p).is_file() for p in req): return ok(False,'pipeline stage missing')
        summary,chart,report,fail=eval_path(w,'lh2.json'),eval_path(w,'lh2.svg'),eval_path(w,'lh2.md'),eval_path(w,'fail.svg')
        a=run(w,['python','tools/step1_summary.py','--input','data/expenses.csv','--output',str(summary)]); b=run(w,['python','tools/step2_chart.py','--input',str(summary),'--output',str(chart)]); c=run(w,['python','tools/step3_report.py','--summary',str(summary),'--chart',str(chart),'--output',str(report)])
        summary.unlink(missing_ok=True); d=run(w,['python','tools/step2_chart.py','--input',str(summary),'--output',str(fail)])
        return ok(a.returncode==b.returncode==c.returncode==0 and d.returncode!=0,'pipeline dependency chain verified')
    if t=='long_horizon_003':
        d=load(w,'reports/audit_matrix.json')
        if not isinstance(d,list) or len(d)!=5:return ok(False,'expected five requirement rows')
        requirements=read(w,'notes/requirements.md')
        seen=set()
        for e in d:
            rid=e.get('requirement_id');quote=e.get('evidence_quote','')
            if rid not in {f'R{i}' for i in range(1,6)} or rid in seen:return ok(False,'missing or duplicate requirement id')
            if not isinstance(quote,str) or not quote or quote not in requirements or rid not in quote:return ok(False,'requirement evidence is not grounded')
            seen.add(rid)
        if not (w/'reports/final_audit.md').is_file():return ok(False,'final audit missing')
        p=run(w,['python','tools/investigation_helper.py','--audit','reports/audit_matrix.json','--output',str(eval_path(w,'lh3'))])
        return ok(p.returncode==0 and seen=={f'R{i}' for i in range(1,6)},'five grounded requirement rows and helper output verified')
    return None
