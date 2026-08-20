import shutil,subprocess,hashlib,json
from datetime import datetime
from .fixtures import materialize_long_horizon_corpus
from .runner import BenchmarkRunner

SEMANTIC_FILES = (
    'adapters.py', 'evaluators.py', 'fixtures.py', 'frontier_v3_runner.py',
    'manifest.py', 'models.py', 'pi_rpc.py', 'runner.py', 'sandbox.py',
    'scoring.py', 'tasks.py', 'telemetry.py',
)

class FrontierV3Runner(BenchmarkRunner):
    def __init__(self,repo_root,agent,results_dir,task_timeout,total_timeout,resume=True,model='unknown',keep_raw=False,run_id=None):
        if run_id is None: run_id=datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S_%f')+'_frontier-v3'
        super().__init__(repo_root,agent,results_dir,task_timeout,total_timeout,resume=resume,model=model,keep_raw=keep_raw,run_id=run_id)
    def _revision(self):
        h=hashlib.sha256()
        # A result is comparable only when the task definition *and* the
        # deterministic oracle/fixture are identical.  Hashing just the JSON
        # catalog allowed stale results to be silently resumed after a fixture
        # or reference-check change.
        roots=[
            self.repo_root/'benchmarks/tasks/frontier_v3',
            self.repo_root/'benchmarks/fixtures',
        ]
        for root in roots:
            for p in sorted(
                path for path in root.rglob('*')
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'
            ):
                h.update(p.relative_to(self.repo_root).as_posix().encode())
                h.update(p.read_bytes())
        for p in sorted((self.repo_root/'aios_bench').glob('reference_checks*.py')):
            h.update(p.name.encode())
            h.update(p.read_bytes())
        for name in SEMANTIC_FILES:
            p=self.repo_root/'aios_bench'/name
            h.update(p.name.encode())
            h.update(p.read_bytes())
        return h.hexdigest()
    def _current_suite_revision(self):
        return self._revision()
    def _suite_name(self):
        return 'frontier_v3'
    def _catalog_task_count(self):
        out=[]
        for p in sorted((self.repo_root/'benchmarks/tasks/frontier_v3').glob('*.json')):out.extend(x['id'] for x in json.loads(p.read_text(encoding='utf-8')))
        return out
    def _state(self,category):
        p=self.run_dir/'persistent_state'/category;p.mkdir(parents=True,exist_ok=True);return p
    def _workspace(self,task):
        path=super()._workspace(task)
        if task.id=='long_horizon_001':
            materialize_long_horizon_corpus(path)
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
        trajectory=super().run_task(task,timeout)
        if task.category in {'memory','learning'}:
            state=self._state(task.category);name='.agent_memory' if task.category=='memory' else 'skills';src=self.run_dir/'workspaces'/task.id/name
            if src.is_dir():
                dst=state/name
                if dst.exists():shutil.rmtree(dst)
                shutil.copytree(src,dst)
        return trajectory
