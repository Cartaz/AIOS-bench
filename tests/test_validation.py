from pathlib import Path
from types import SimpleNamespace

from aios_bench.tasks import load_tasks
from aios_bench.validation import validate_negative_baseline, validate_parametric_baseline


ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path, *, solved: bool) -> Path:
    workspace = tmp_path / "benchmarks" / "fixtures" / "workspace"
    workspace.mkdir(parents=True)
    if solved:
        (workspace / "answer.txt").write_text("already solved", encoding="utf-8")
    return tmp_path


def _task():
    return SimpleNamespace(
        id="test_task",
        acceptance=({"type": "exists", "path": "answer.txt", "weight": 1, "fatal": True},),
    )


def test_negative_preflight_accepts_unsolved_fixture(tmp_path: Path):
    result = validate_negative_baseline(_repo(tmp_path, solved=False), [_task()])
    assert result["ok"] is True
    assert result["checked_tasks"] == 1
    assert result["failures"] == []


def test_negative_preflight_rejects_fixture_that_already_passes(tmp_path: Path):
    result = validate_negative_baseline(_repo(tmp_path, solved=True), [_task()])
    assert result["ok"] is False
    assert result["failures"][0]["reason"] == "untouched fixture passes grader"


def test_parametric_preflight_checks_determinism_variation_and_negative_baseline():
    tasks = load_tasks(ROOT / "benchmarks" / "tasks", "frontier_v4")
    result = validate_parametric_baseline(
        ROOT,
        tasks,
        base_seed=42,
        parameters={
            "expense_report": {
                "rows": 32,
                "malformed_rows": 2,
                "distractor_files": 1,
                "months": 4,
            }
        },
    )

    assert result["ok"] is True
    assert result["checked_tasks"] == 1
    observation = result["observations"][0]
    assert observation["same_seed_deterministic"] is True
    assert observation["different_seed_changes_variant"] is True
    assert observation["untouched_variant_fails"] is True
    assert observation["variant_digest"] != observation["comparison_variant_digest"]
