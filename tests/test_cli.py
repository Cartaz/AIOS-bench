from pathlib import Path

import pytest

from aios_bench import cli


def test_list_does_not_require_a_harness(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aiosbench", "list"])
    cli.main()
    output = capsys.readouterr().out
    assert "autonomy_001" in output
    assert "tool_use_003" in output


def test_list_can_filter_one_task(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--task", "coding_003", "list"])
    cli.main()
    output = capsys.readouterr().out
    assert "coding_003" in output
    assert "coding_002" not in output


def test_task_selection_includes_dependency_chain():
    tasks = cli.load_tasks(cli.TASKS)
    selected = cli._select_tasks(tasks, ["memory_003"], None)
    assert [task.id for task in selected] == ["memory_001", "memory_002", "memory_003"]


def test_category_selection_keeps_catalog_order():
    tasks = cli.load_tasks(cli.TASKS)
    selected = cli._select_tasks(tasks, None, ["learning"])
    assert [task.id for task in selected] == ["learning_001", "learning_002", "learning_003"]


def test_unknown_task_selection_is_rejected():
    tasks = cli.load_tasks(cli.TASKS)
    with pytest.raises(SystemExit, match="Unknown task"):
        cli._select_tasks(tasks, ["missing_999"], None)


def test_publish_reads_local_results_and_writes_only_snapshots(
    monkeypatch, tmp_path: Path, capsys
):
    local = tmp_path / "results" / ".local"
    published = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS", local)
    monkeypatch.setattr(cli, "PUBLISHED", published)
    monkeypatch.setattr("sys.argv", ["aiosbench", "publish"])

    cli.main()

    assert (published / "summary.json").is_file()
    assert (published / "dashboard.html").is_file()
    assert not (published / "results.jsonl").exists()
    assert "Published dashboard" in capsys.readouterr().out


def test_multiple_harness_flags_are_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--opencode", "--piagent"])
    with pytest.raises(SystemExit, match="Select one harness"):
        cli.main()
