from pathlib import Path
from types import SimpleNamespace

from aios_bench.validation import validate_negative_baseline


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
