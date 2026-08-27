from __future__ import annotations

import json

import pytest

from aios_bench import cli


def test_qa_is_frontier_v4_only(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["aiosbench", "--suite", "frontier_v3", "qa"])

    with pytest.raises(SystemExit, match="currently tracked for Frontier v4"):
        cli.main()


def test_qa_reports_valid_pilot_without_requiring_promotion(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "validate_parametric_baseline",
        lambda *args, **kwargs: {
            "ok": True,
            "observations": [
                {
                    "task_id": task.id,
                    "same_seed_deterministic": True,
                    "different_seed_changes_variant": True,
                    "untouched_variant_fails": True,
                    "golden_variant_passes": True,
                    "adversarial_witness_rejected": True,
                }
                for task in args[1]
            ],
        },
    )
    monkeypatch.setattr("sys.argv", ["aiosbench", "--suite", "frontier_v4", "qa"])

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == "aios-bench/task-qa-report/v6"
    assert result["ok"] is True
    assert result["task_count"] == 8
    assert result["promotion_ready_count"] == 0
    assert result["all_promotion_ready"] is False
    assert all(item["lifecycle"] == "pilot" for item in result["tasks"])
    assert all(item["automated_checks"]["adversarial_witness_rejected"] == "passed" for item in result["tasks"])
