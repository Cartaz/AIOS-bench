import os, shutil, subprocess
from .runner import BenchmarkRunner

class FrontierV3Runner(BenchmarkRunner):
    def _state(self, category):
        p=self.run_dir/'persistent_state'/category; p.mkdir(parents=True,exist_ok=True); return p
    def _workspace(self, task):
        path=super()._workspace(task)
        if task.category in {'memory','learning'} and task.mode=='warm':
            state=self._state(task.category); name='.agent_memory' if task.category=='memory' else 'skills'; src=state/name
            if src.is_dir():
                dst=path/name
                if dst.exists(): shutil.rmtree(dst)
                shutil.copytree(src,dst)
        if task.id=='learning_003':
            p=path/'skills/reporting_workflow.md'; text=p.read_text(encoding='utf-8') if p.is_file() else '# Reporting workflow\n'
            text=text.replace('Total revenue = sum of `revenue`','Total revenue = sum of the `units` column').replace('Total revenue = sum of revenue','Total revenue = sum of the `units` column')
            p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
        if task.id=='memory_004':
            subprocess.run(['git','init','-q'],cwd=path,check=True); subprocess.run(['git','config','user.email','bench@aios-bench.local'],cwd=path,check=True); subprocess.run(['git','config','user.name','AIOS-bench'],cwd=path,check=True); subprocess.run(['git','add','-A'],cwd=path,check=True); subprocess.run(['git','commit','-qm','fixture baseline'],cwd=path,check=True)
        return path
    def run_task(self, task, timeout):
        os.environ['AIOS_BENCH_RUN_DIR']=str(self.run_dir)
        trajectory=super().run_task(task,timeout)
        if task.category in {'memory','learning'}:
            state=self._state(task.category); name='.agent_memory' if task.category=='memory' else 'skills'; src=self.run_dir/'workspaces'/task.id/name
            if src.is_dir():
                dst=state/name
                if dst.exists(): shutil.rmtree(dst)
                shutil.copytree(src,dst)
        return trajectory
