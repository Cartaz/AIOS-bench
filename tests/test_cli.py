import json
from pathlib import Path

import pytest

from aios_bench import cli


def test_active_cli_harnesses_exclude_codex():
    assert "codex" not in cli.AGENTS
    assert tuple(cli.AGENTS) == (
        "hermes", "piagent", "opencode", "goose", "letta", "agentzero", "claude",
    )


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
    assert ids == {
        "autonomy_expense_001",
        "stateful_support_001",
        "support_dependency_001",
        "data_cross_artifact_001",
        "retrieval_wide_001",
        "reasoning_epistemic_001",
        "tool_use_config_001",
        "tool_use_lineage_001",
        "tool_recovery_001",
    }


def test_frontier_v4_rejects_invalid_pressure_coordinates(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["aiosbench", "--suite", "frontier_v4", "--v4-expense-rows", "5", "validate"],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 expense pressure"):
        cli.main()


def test_frontier_v4_rejects_invalid_dependency_pressure(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-dependency-accounts",
            "2",
            "validate",
        ],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 dependency pressure"):
        cli.main()


def test_frontier_v4_rejects_invalid_lineage_pressure(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-lineage-depth",
            "2",
            "validate",
        ],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 lineage pressure"):
        cli.main()


def test_frontier_v4_rejects_invalid_retrieval_pressure(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-retrieval-corpus-size",
            "10",
            "validate",
        ],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 retrieval pressure"):
        cli.main()


def test_frontier_v4_rejects_invalid_cross_artifact_pressure(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-cross-rows",
            "12",
            "validate",
        ],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 cross-artifact pressure"):
        cli.main()


def test_frontier_v4_rejects_invalid_epistemic_pressure(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-epistemic-pairs",
            "10",
            "--v4-epistemic-registry-size",
            "12",
            "validate",
        ],
    )
    with pytest.raises(SystemExit, match="invalid Frontier v4 epistemic-twin pressure"):
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


def test_smoke_requires_explicit_model(monkeypatch):
    monkeypatch.setattr("sys.argv", ["aiosbench", "--piagent", "smoke"])
    with pytest.raises(SystemExit, match="smoke requires an explicit --model"):
        cli.main()


def test_smoke_is_frontier_v3_only(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["aiosbench", "--piagent", "--model", "Ornith", "--suite", "frontier_v4", "smoke"],
    )
    with pytest.raises(SystemExit, match="Frontier v3 integration contracts"):
        cli.main()


def test_smoke_uses_separate_results_root_and_writes_report(monkeypatch, tmp_path: Path, capsys):
    local = tmp_path / "results" / ".local"
    smoke = tmp_path / "results" / ".smoke"
    monkeypatch.setattr(cli, "RESULTS", local)
    monkeypatch.setattr(cli, "SMOKE_RESULTS", smoke)

    def fake_run(args, harness, tasks):
        assert harness == "piagent"
        assert getattr(args, "_results_dir") == smoke
        assert [task.id for task in tasks] == ["tool_use_001"]
        run_dir = smoke / harness / "Ornith" / "runs" / args.run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text(
            json.dumps({
                "harness": harness,
                "run_id": args.run_id,
                "manifest": {
                    "model": {
                        "requested": "Ornith",
                        "resolved": "Ornith",
                        "resolution": "adapter_pinned",
                        "verification": "declared_model",
                        "strictly_comparable": False,
                    },
                    "server_metrics": {"enabled": False},
                },
            }),
            encoding="utf-8",
        )
        (run_dir / "results.jsonl").write_text(
            json.dumps({
                "task_id": "tool_use_001",
                "status": "completed",
                "success": True,
                "score": 100,
                "telemetry_available": True,
                "events": [{"type": "tool_call"}],
            }) + "\n",
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(cli, "_run_single_harness", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["aiosbench", "--piagent", "--model", "Ornith", "--run-id", "smoke-cli", "smoke"],
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    report = json.loads((smoke / "smoke-cli.json").read_text(encoding="utf-8"))
    assert report["integration_ok"] is True
    assert report["strict_model_ready"] is False
    assert report["server_metrics_ready"] is False
    assert not local.exists()
    output = capsys.readouterr().out
    assert "Integration OK:       True" in output
