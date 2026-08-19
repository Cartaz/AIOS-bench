"""AIOS-bench adapter for Hermes Agent."""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from pathlib import Path

def main() -> int:
    payload = json.loads(sys.argv[1]); task = payload["task"]
    workspace = Path(payload["workspace"]); state_dir = Path(payload["state_dir"])
    prompt = "AIOS-bench task. Work only in this workspace. Complete the requested task. Do not reveal private chain-of-thought; provide a concise final summary.\n\n" + task["prompt"]
    cmd = [os.environ.get("HERMES_COMMAND", "hermes"), "chat", "--verbose"]
    for env_name, flag in (("HERMES_PROVIDER", "--provider"),("HERMES_MODEL", "--model"),("HERMES_TOOLSETS", "--toolsets")):
        value = os.environ.get(env_name)
        if value: cmd += [flag, value]
    cmd += ["-q", prompt]
    before = {str(p.relative_to(workspace)): p.stat().st_mtime_ns for p in workspace.rglob("*") if p.is_file()}
    start = time.perf_counter(); env = os.environ.copy(); env["HOME"] = str(state_dir); env["USERPROFILE"] = str(state_dir)
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=int(os.environ.get("AIOS_TIMEOUT", "1800")), env=env)
    duration = time.perf_counter() - start; text = proc.stdout; low = text.lower()
    errors = len(re.findall(r"\b(error|exception|failed|failure)\b", low)); retries = len(re.findall(r"\b(retry|retrying)\b", low))
    tool_calls = len(re.findall(r"\b(tool|terminal|python|read_file|write_file|browser)\b", low))
    after = {str(p.relative_to(workspace)): p for p in workspace.rglob("*") if p.is_file()}
    writes = [p for name,p in after.items() if name not in before or p.stat().st_mtime_ns != before[name]]
    trajectory = {"agent":"hermes","task_id":task["id"],"success":proc.returncode == 0,"duration_s":round(duration,3),"input_tokens":0,"output_tokens":0,"tool_calls":tool_calls,"errors":errors+(1 if proc.returncode else 0),"retries":retries,"human_interventions":0,"files_read":0,"files_written":len(writes),"memory_reads":0,"memory_writes":0,"skills_created":0,"subagents":0,"events":[{"type":"process","exit_code":proc.returncode}],"notes":(proc.stderr+"\n"+text)[-6000:]}
    print(json.dumps(trajectory, ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
