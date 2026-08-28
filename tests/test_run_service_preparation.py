from __future__ import annotations

from pathlib import Path

from core.run_service import BenchmarkService, PreparedRun, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def _request() -> RunRequest:
    return RunRequest(
        suite="frontier_v3",
        harnesses=("piagent",),
        task_ids=("autonomy_001",),
        model="test",
    )


def test_catalog_rejects_unknown_suite_before_loading_files(monkeypatch) -> None:
    service = BenchmarkService(ROOT)
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("catalog loader must not run")

    monkeypatch.setattr("core.run_service.load_tasks", fail_if_called)
    try:
        service.catalog("../../escape")
    except ValueError as exc:
        assert "Unknown suite" in str(exc)
    else:
        raise AssertionError("unknown suite must be rejected")
    assert called is False


def test_prepared_run_reuses_validated_task_selection(monkeypatch, tmp_path: Path) -> None:
    service = BenchmarkService(ROOT)
    service.results_root = tmp_path
    prepared = service.prepare(_request())
    assert isinstance(prepared, PreparedRun)
    assert [task.id for task in prepared.tasks] == ["autonomy_001"]

    monkeypatch.setattr(
        service,
        "validate_request",
        lambda request: (_ for _ in ()).throw(AssertionError("must not revalidate")),
    )

    class Runner:
        def run(self, tasks):
            assert [task.id for task in tasks] == ["autonomy_001"]
            return 0

        def abort(self, tasks):
            raise AssertionError("run should not abort")

    monkeypatch.setattr(service, "_build_runner", lambda *args, **kwargs: Runner())
    summary = tmp_path / "summary.json"
    summary.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("core.run_service.write_summary", lambda root: summary)
    monkeypatch.setattr("core.run_service.augment_summary_file", lambda path, root: None)

    result = service.run(prepared)
    assert result["exit_code"] == 0
    assert result["cancelled"] is False
