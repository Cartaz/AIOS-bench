import hashlib,json,shutil,subprocess
from datetime import datetime

from .failures import classify_failure
from .fixtures import materialize_long_horizon_corpus
from .runner import BenchmarkRunner
from .server_metrics import build_server_metrics_client
from .task_execution import run_frontier_task

SEMANTIC_FILES = (
    'adapters.py', 'evaluators.py', 'experiments.py', 'failures.py', 'fixtures.py',
    'frontier_v3_runner.py', 'manifest.py', 'models.py', 'pi_rpc.py', 'runner.py',
    'sandbox.py', 'scheduler.py', 'scoring.py', 'task_execution.py', 'tasks.py',
    'telemetry.py',
)
SEMANTIC_DIRS = ('server_metrics',)

class FrontierV3Runner(BenchmarkRunner):
    def __init__(
        self,repo_root,agent,results_dir,task_timeout,total_timeout,resume=True,
        model='unknown',keep_raw=False,run_id=None,server_metrics_url=None,
        server_metrics_model=None,max_output_tokens=65536,metrics_poll_interval=1.0,
    ):
        self.server_metrics=build_server_metrics_client(
            server_metrics_url,model=server_metrics_model,
        )
        self.server_metrics_model=server_metrics_model
        self.max_output_tokens=max_output_tokens
        self.metrics_poll_interval=metrics_poll_interval
        if run_id is None: run_id=datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S_%f')+'_frontier-v3'
        super().__init__(repo_root,agent,results_dir,task_timeout,total_timeout,resume=resume,model=model,keep_raw=keep_raw,run_id=run_id)
    def _execution_manifest(self):
        manifest=super()._execution_manifest()
        manifest['server_metrics']={
            'source':self.server_metrics.source,
            'enabled':bool(self.server_metrics.enabled),
            'endpoint':self.server_metrics.public_endpoint,
            'model_filter':self.server_metrics_model,
            'output_token_cap':self.max_output_tokens,
            'poll_interval_seconds':self.metrics_poll_interval,
            'scope':'endpoint_aggregate',
            'requires_exclusive_server':True,
        }
        return manifest
    def _revision(self):
        h=hashlib.sha256()
        # A result is comparable only when the task definition *and* the
        # deterministic oracle/fixture are identical. Hash execution semantics
        # too so telemetry/taxonomy/scheduler changes cannot reuse stale rows.
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
        for directory in SEMANTIC_DIRS:
            root=self.repo_root/'aios_bench'/directory
            for p in sorted(path for path in root.rglob('*.py') if '__pycache__' not in path.parts):
                h.update(p.relative_to(self.repo_root).as_posix().encode())
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
    def _write_noncomparable(self,task,status,reason,assessment=None):
        failure_kind=classify_failure(
            status=status,success=False,execution_success=False,
            evaluation_passed=None,events=(),
        )
        item={
            **self._result_identity(task),'agent':self.agent.name,'success':False,
            'status':status,'failure_kind':failure_kind,'score':None,'comparable':False,
            'duration_seconds':0.0,'reason':reason,'telemetry_available':False,
            'events':[],'evaluation':None,'usage_source':'unavailable',
            'efficiency_comparable':False,'server_usage':None,
        }
        if assessment is not None:item['capability_assessment']=assessment.to_dict()
        self._write_result(item)
        self._log({'event':f'task_{status}','task_id':task.id,'failure_kind':failure_kind,**reason})
    def run_task(self,task,timeout):
        trajectory=run_frontier_task(self,task,timeout)
        if task.category in {'memory','learning'}:
            state=self._state(task.category);name='.agent_memory' if task.category=='memory' else 'skills';src=self.run_dir/'workspaces'/task.id/name
            if src.is_dir():
                dst=state/name
                if dst.exists():shutil.rmtree(dst)
                shutil.copytree(src,dst)
        return trajectory
