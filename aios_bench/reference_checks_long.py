from .reference_checks_core import read,load,run,ok
from pathlib import Path
import re

def check(t,w,fx):
    if t=='long_horizon_001':
        x=read(w,'reports/long_horizon_changelog.md')
        good=(fx.parent/'long_horizon_corpus.md').stat().st_size>=3000 and 'validator state corruption' in x.lower() and bool(re.search(r'recovery\s*:\s*\S+',x,re.I)) and all((w/f'.state/checkpoint_{n}.json').is_file() for n in (1,3,5))
        return ok(good,'large corpus, recovery and checkpoints verified')
    if t=='long_horizon_002':
        req=['tools/step1_summary.py','tools/step2_chart.py','tools/step3_report.py']
        if not all((w/p).is_file() for p in req): return ok(False,'pipeline stage missing')
        a=run(w,['python','tools/step1_summary.py','--input','data/expenses.csv','--output','/tmp/lh2.json']); b=run(w,['python','tools/step2_chart.py','--input','/tmp/lh2.json','--output','/tmp/lh2.svg']); c=run(w,['python','tools/step3_report.py','--summary','/tmp/lh2.json','--chart','/tmp/lh2.svg','--output','/tmp/lh2.md'])
        Path('/tmp/lh2.json').unlink(missing_ok=True); d=run(w,['python','tools/step2_chart.py','--input','/tmp/lh2.json','--output','/tmp/fail.svg'])
        return ok(a.returncode==b.returncode==c.returncode==0 and d.returncode!=0,'pipeline dependency chain verified')
    if t=='long_horizon_003':
        d=load(w,'reports/audit_matrix.json'); p=run(w,['python','tools/investigation_helper.py','--audit','reports/audit_matrix.json','--output','/tmp/lh3'])
        good=isinstance(d,list) and len(d)==5 and all(any(e.get('requirement_id')==f'R{i}' for e in d) for i in range(1,6)) and p.returncode==0
        return ok(good,'five requirement audit verified')
    return None
