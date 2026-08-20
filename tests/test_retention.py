from pathlib import Path

from aios_bench.retention import prune_run_artifacts


def test_retention_keeps_failures_and_removes_redundant_success_logs(tmp_path: Path) -> None:
    run = tmp_path / "run"
    logs = run / "logs"
    workspace = run / "workspaces" / "coding_001"
    logs.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (run / "results.jsonl").write_text(
        '{"task_id":"coding_001","status":"completed"}\n'
        '{"task_id":"browser_001","status":"timeout"}\n',
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text("raw\n", encoding="utf-8")
    (logs / "coding_001.stdout.log").write_text("success log\n", encoding="utf-8")
    (logs / "browser_001.stdout.log").write_text("failure log\n", encoding="utf-8")
    (logs / "coding_001.stderr.log").write_text("", encoding="utf-8")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "package.js").write_text("noise", encoding="utf-8")
    (workspace / "result.md").write_text("keep", encoding="utf-8")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (workspace / ".aios-bench-eval").mkdir()
    (workspace / ".aios-bench-eval" / "oracle.tmp").write_text("internal", encoding="utf-8")

    result = prune_run_artifacts(run)

    assert result["raw_kept"] is False
    assert not (run / "events.jsonl").exists()
    assert not (logs / "coding_001.stdout.log").exists()
    assert (logs / "browser_001.stdout.log").exists()
    assert not (logs / "coding_001.stderr.log").exists()
    assert not (workspace / "node_modules").exists()
    assert not (workspace / ".git").exists()
    assert not (workspace / ".aios-bench-eval").exists()
    assert (workspace / "result.md").exists()
    assert (run / "retention.json").exists()


def test_retention_can_keep_raw_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "events.jsonl").write_text("raw\n", encoding="utf-8")

    result = prune_run_artifacts(run, keep_raw=True)

    assert result["raw_kept"] is True
    assert (run / "events.jsonl").exists()
