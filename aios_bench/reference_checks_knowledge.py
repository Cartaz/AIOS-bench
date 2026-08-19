from .reference_checks_core import read,load,ok
import re,json

def check(t,w,fx):
    if t=='knowledge_001':
        d=load(w,'reports/unresolved_actions.json')
        if not isinstance(d,list) or len(d)!=3:return ok(False,'expected three actions')
        good=all((w/e.get('source_doc','')).is_file() and e.get('evidence_quote','') in read(w,e['source_doc']) for e in d)
        return ok(good and not any('Q3 budget' in json.dumps(e) for e in d),'three grounded unresolved actions')
    if t=='knowledge_002':
        load(w,'reports/procedure_diff.json');x=read(w,'reports/procedure_diff.md')
        good=all(re.search(rf'{s}\s*:',x,re.I) for s in ['additions','removals','changed','unchanged']) and bool(re.search(r'\[(previous|current|next_draft)\.md:\d+\]',x))
        return ok(good,'structured procedure diff')
    if t=='knowledge_003':
        d,x=load(w,'reports/claim_evidence.json'),read(w,'reports/evidence_review.md')
        if not isinstance(d,list) or len(d)<3:return ok(False,'claim matrix too small')
        good=all((w/e.get('source_doc','')).is_file() and e.get('evidence_quote','') in read(w,e['source_doc']) for e in d)
        good &= bool(re.search(r'authoritative_source\s*:\s*procedures/current\.md',x,re.I)) and bool(re.search(r'criteria\s*:\s*\S+',x,re.I)) and bool(re.search(r'uncertainty\s*:\s*(low|medium|high)',x,re.I))
        return ok(good,'claim/evidence review verified')
    return None
