from pathlib import Path

import pytest

from aios_bench import cli


def test_active_cli_harnesses_exclude_codex():
    assert "codex" not in cli.AGENTS
    assert tuple(cli.AGENTS) == ("hermes", "piagent", "opencode", "goose", "letta", "agentzero")


def test_list_does_not_require_a_harness(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aiosbench", "list"])
    cli.main()
    output = capsys.readouterr().out
    assert "autonomy_001" in output
    assert "tool_use_003" in output


def test_publish_reads_local_results_and_writes_only_snapshots(monkeypatch, tmp_path: Path, capsys):
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
    monkeypatch.setattr("sys.argv", ["aiosbench", "--hermes", "--piagent"])
    with pytest.raises(SystemExit, match="Select one harness"):
        cli.main()


def test_repeat_count_must_be_positive(monkeypatch):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--piagent", "--repeats", "0"])
    with pytest.raises(SystemExit, match="--repeats must be >= 1"):
        cli.main()
