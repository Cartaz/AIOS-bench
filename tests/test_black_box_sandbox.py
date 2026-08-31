from pathlib import Path

from core.benchmark.sandbox import workspace_sandbox


def test_black_box_verifier_uses_private_network_namespace(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "piagent" / "model" / "runs" / "run" / "workspaces" / "task"
    workspace.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    plan = workspace_sandbox("blackbox-verifier", workspace, "required")
    command = plan.wrap(["python", "solution/reconstruct.py"])

    assert plan.grader_hidden is True
    assert plan.strategy == "bubblewrap_repo_hidden_workspace_only_network_isolated"
    assert "--unshare-net" in command
