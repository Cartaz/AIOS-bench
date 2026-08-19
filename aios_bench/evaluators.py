from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .reference_checks import check_task

class EvaluationError(ValueError):
    pass

def _safe_path(workspace: Path, relative_path: str) -> Path:
    path=(workspace/relative_path).resolve(); root=workspace.resolve()
    if root not in path.parents and path != root: raise EvaluationError(f"path escapes workspace: {relative_path}")
    return path

def file_exists(workspace: Path, relative_path: str) -> bool: return _safe_path(workspace,relative_path).is_file()
def file_contains(workspace: Path, relative_path: str, text: str) -> bool:
    p=_safe_path(workspace,relative_path); return p.is_file() and text.lower() in p.read_text(encoding="utf-8",errors="replace").lower()
def file_sha256(workspace: Path, relative_path: str) -> str:
    p=_safe_path(workspace,relative_path)
    if not p.is_file(): raise EvaluationError(f"missing artifact: {relative_path}")
    return hashlib.sha256(p.read_bytes()).hexdigest()
def _fixture_sha256(relative_path: str) -> str:
    root=os.environ.get("AIOS_BENCH_FIXTURE_ROOT")
    if not root: raise EvaluationError("AIOS_BENCH_FIXTURE_ROOT is not set")
    p=Path(root)/relative_path
    if not p.is_file(): raise EvaluationError(f"missing fixture baseline: {relative_path}")
    return hashlib.sha256(p.read_bytes()).hexdigest()
def _run_check_command(workspace: Path, command: str, timeout: float=30.0):
    p=subprocess.run(command,cwd=workspace,shell=True,text=True,capture_output=True,timeout=timeout,check=False)
    return p.returncode==0,(p.stdout+"\n"+p.stderr).strip()[-4000:]

def evaluate_artifacts(
    workspace: Path,
    checks: list[dict[str,Any]],
    run_dir: Path|None=None,
    events: list[dict[str, Any]] | None=None,
) -> dict[str,Any]:
    results=[]
    for check in checks:
        kind=check["type"]; path=check.get("path",""); detail=""
        try:
            if kind=="exists": passed=file_exists(workspace,path)
            elif kind=="contains": passed=file_contains(workspace,path,check["text"])
            elif kind=="contains_any": passed=any(file_contains(workspace,path,t) for t in check["texts"])
            elif kind=="regex":
                p=_safe_path(workspace,path); passed=p.is_file() and re.search(check["pattern"],p.read_text(encoding="utf-8",errors="replace"),re.MULTILINE) is not None
            elif kind=="min_lines":
                p=_safe_path(workspace,path); passed=p.is_file() and len(p.read_text(encoding="utf-8",errors="replace").splitlines())>=int(check["lines"])
            elif kind=="json_valid":
                p=_safe_path(workspace,path); json.loads(p.read_text(encoding="utf-8")) if p.is_file() else (_ for _ in ()).throw(ValueError("missing file")); passed=True
            elif kind=="sha256": passed=file_sha256(workspace,path)==check["sha256"]
            elif kind=="unchanged": passed=file_sha256(workspace,path)==_fixture_sha256(path)
            elif kind=="command": passed,detail=_run_check_command(workspace,check["command"],float(check.get("timeout",30)))
            elif kind=="reference":
                passed,detail=check_task(
                    check["task_id"], workspace,
                    Path(os.environ["AIOS_BENCH_FIXTURE_ROOT"]), run_dir,
                    events=events or [],
                )
            elif kind=="max_files":
                p=_safe_path(workspace,path or "."); n=sum(1 for x in p.rglob("*") if x.is_file()) if p.exists() else 0; passed=n<=int(check["max"]); detail=f"file_count={n}"
            else: raise EvaluationError(f"unknown check type: {kind}")
        except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc: passed=False; detail=str(exc)
        results.append({"check":check,"passed":passed,"weight":float(check.get("weight",1.0)),"detail":detail})
    total=sum(r["weight"] for r in results) or 1.0; earned=sum(r["weight"] for r in results if r["passed"]); fatal=any(not r["passed"] and r["check"].get("fatal",False) for r in results); score=earned/total
    return {"passed":not fatal and score>=0.80,"acceptance_score":score,"checks_passed":sum(r["passed"] for r in results),"checks_total":len(results),"results":results}

def evaluate_json(workspace: Path, spec_path: str|Path, run_dir: Path|None=None) -> dict[str,Any]:
    p=Path(spec_path); p=p if p.is_absolute() else workspace/p; return evaluate_artifacts(workspace,json.loads(p.read_text(encoding="utf-8"))["checks"],run_dir=run_dir)
def registry() -> dict[str,Callable[...,dict[str,Any]]]: return {"artifacts":evaluate_artifacts,"json":evaluate_json}
