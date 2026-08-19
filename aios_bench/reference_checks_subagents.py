from .reference_checks_core import read,load,ok
from pathlib import Path

def check(t,w,fx,run_dir=None):
    if not t.startswith('subagents_'): return None
    if run_dir is None:return ok(False,'run directory unavailable')
    log=run_dir/'logs'/f'{t}.stdout.log'
    text=log.read_text(encoding='utf-8',errors='replace').lower() if log.is_file() else ''
    starts=sum(text.count(x) for x in ['subagent start','subagent_start','spawn subagent','delegate to subagent','delegated stream'])
    need=1 if t=='subagents_001' else 2
    report=w/'reports/subagent_comparison.md' if t=='subagents_001' else w/'reports/decision_memo.md'
    if not report.is_file():return ok(False,'decision report missing')
    x=report.read_text(encoding='utf-8',errors='replace')
    good=starts>=need
    if t=='subagents_001':good &= (w/'reports/reconciliation.json').is_file() and len(load(w,'reports/reconciliation.json'))>=3 and '## Verified' in x and '## Rejected' in x
    elif t=='subagents_002':good &= 'CVE' in x and '99.99%' not in x
    else:good &= '## Rejected' in x and any(k in x.lower() for k in ['decision: adopt','decision: reject','decision: postpone','decision: investigate'])
    return ok(bool(good),f'delegation telemetry starts={starts}, required={need}')
