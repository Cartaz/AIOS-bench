import os,shutil,subprocess,hashlib,json
from datetime import datetime,timezone
from .runner import BenchmarkRunner

class FrontierV3Runner(BenchmarkRunner):
    def __init__(self,repo_root,agent,results_dir,task_timeout,total_timeout,resume=True,model='unknown',keep_raw=False,run_id=None):
        if run_id is None: run_id=datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S')+'_frontier-v3'
        super().__init__(repo_root,agent,results_dir,task_timeout,total_timeout,resume=resume,model=model,keep_raw=keep_raw,run_id=run_id)
    def _revision(self):
        h=hashlib.sha256()
        for p in sorted((self.repo_root/'benchmarks/tasks/frontier_v3').glob('*.json')):h.update(p.read_bytes())
        return h.hexdigest()
    def _write_metadata(self,finished_at=None):
        existing={}
        if getattr(self,'metadata_path',None) and self.metadata_path.exists():
            try: existing=json.loads(self.metadata_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError: pass
        m={'benchmark':'AIOS-bench','suite':'frontier_v3','suite_revision':self._revision(),'harness':self.agent.name,'model':self.model,'model_id':self.model,'run_id':self.run_id,'started_at':existing.get('started_at',datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')),'git_commit':self._git_commit_safe(),'task_count':len(self._catalog_task_count())}
        if finished_at is not None:m['finished_at']=finished_at
        elif existing.get('finished_at'):m['finished_at']=existing['finished_at']
        self.metadata_path.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    def _git_commit_safe(self):
        try:return subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo_root,text=True,stderr=subprocess.DEVNULL).strip()
        except Exception:return 'unknown'
    def _catalog_task_count(self):
        out=[]
        for p in sorted((self.repo_root/'benchmarks/tasks/frontier_v3').glob('*.json')):out.extend(x['id'] for x in json.loads(p.read_text(encoding='utf-8')))
        return out
    def _write_result(self,item):
        item['suite']='frontier_v3';item['suite_revision']=self._revision();super()._write_result(item)
    def _state(self,category):
        p=self.run_dir/'persistent_state'/category;p.mkdir(parents=True,exist_ok=True);return p
    def _workspace(self,task):
        path=super()._workspace(task)
        if task.category in {'memory','learning'} and task.mode=='warm':
            state=self._state(task.category);name='.agent_memory' if task.category=='memory' else 'skills';src=state/name
            if src.is_dir():
                dst=path/name
                if dst.exists():shutil.rmtree(dst)
                shutil.copytree(src,dst)
        if task.id=='learning_003':
            p=path/'skills/reporting_workflow.md';text=p.read_text(encoding='utf-8') if p.is_file() else '# Reporting workflow\n';text=text.replace('Total revenue = sum of `revenue`','Total revenue = sum of the `units` column').replace('Total revenue = sum of revenue','Total revenue = sum of the `units` column');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
        if task.id=='memory_004':
            subprocess.run(['git','init','-q'],cwd=path,check=True);subprocess.run(['git','config','user.email','bench@aios-bench.local'],cwd=path,check=True);subprocess.run(['git','config','user.name','AIOS-bench'],cwd=path,check=True);subprocess.run(['git','add','-A'],cwd=path,check=True);subprocess.run(['git','commit','-qm','fixture baseline'],cwd=path,check=True)
        return path
    def run_task(self,task,timeout):
        os.environ['AIOS_BENCH_RUN_DIR']=str(self.run_dir);trajectory=super().run_task(task,timeout)
        if task.category in {'memory','learning'}:
            state=self._state(task.category);name='.agent_memory' if task.category=='memory' else 'skills';src=self.run_dir/'workspaces'/task.id/name
            if src.is_dir():
                dst=state/name
                if dst.exists():shutil.rmtree(dst)
                shutil.copytree(src,dst)
        return trajectory
