from pathlib import Path

import pytest

from aios_bench import cli


def test_active_cli_harnesses_exclude_codex():
    assert "codex" not in cli.AGENTS
    assert tuple(cli.AGENTS) == ("hermes", "piagent", "opencode", "goose", "letta", "agentzero")


def test_list_does_not_require_a_harness_and_defaults_to_v3(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aiosbench", "list"])
    cli.main()
    output = capsys.readouterr().out
    ids = {line.split("\t", 1)[0] for line in output.splitlines() if line.strip()}
    assert "autonomy_001" in ids
    assert "tool_use_003" in ids
    assert "autonomy_expense_001" not in ids


def test_frontier_v4_list_is_explicit_opt_in(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--suite", "frontier_v4", "list"])
    cli.main()
    output = capsys.readouterr().out
    ids = {line.split("\t", 1)[0] for line in output.splitlines() if line.strip()}
    assert ids == {"autonomy_expense_001"}


def test_frontier_v4_rejects_invalid_pressure_coordinates(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["aiosbench", "--suite", "frontier_v4", "--v4-expense-rows", "5", "validate"],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 expense pressure"):
        cli.main()


def test_publish_reads_local_results_writes_sealed_snapshots_and_verifies(monkeypatch, tmp_path: Path, capsys):
    local = tmp_path / "results" / ".local"
    published = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS", local)
    monkeypatch.setattr(cli, "PUBLISHED", published)
    monkeypatch.setattr("sys.argv", ["aiosbench", "publish"])
    cli.main()
    assert (published / "summary.json").is_file()
    assert (published / "dashboard.html").is_file()
    assert (published / "publication.json").is_file()
    assert not (published / "results.jsonl").exists()
    assert "Publication seal" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["aiosbench", "verify"])
    cli.main()
    assert '"ok": true' in capsys.readouterr().out.lower()


def test_multiple_harness_flags_are_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--hermes", "--piagent"])
    with pytest.raises(SystemExit, match="Select one harness"):
        cli.main()


def test_repeat_count_must_be_positive(monkeypatch):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--piagent", "--repeats", "0"])
    with pytest.raises(SystemExit, match="--repeats must be >= 1"):
        cli.main()
