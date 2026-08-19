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
        d=load(w,'reports/audit_matrix.json'); p=run(w,['python','tools/investigation_helper.py','--audit','reports/audit_matrix.json','--output',str(eval_path(w,'lh3'))])
        good=isinstance(d,list) and len(d)==5 and all(any(e.get('requirement_id')==f'R{i}' for e in d) for i in range(1,6)) and p.returncode==0
        return ok(good,'five requirement audit verified')
    return None
