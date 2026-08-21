import json
from pathlib import Path

from aios_bench.smoke import (
    BROWSER_TASK_ID,
    CORE_TASK_ID,
    SUBAGENT_TASK_ID,
    build_smoke_report,
    discover_smoke_run_dirs,
    select_smoke_tasks,
)
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"


def _ids(tasks):
    return [task.id for task in tasks]


def _write_run(
    root: Path,
    harness: str,
    smoke_id: str,
    rows: list[dict],
    *,
    resolved: str = "Ornith",
    strict: bool = True,
    metrics: bool = True,
) -> Path:
    run_dir = root / harness / "Ornith" / "runs" / smoke_id
    run_dir.mkdir(parents=True)
    metadata = {
        "harness": harness,
        "run_id": smoke_id,
        "manifest": {
            "model": {
                "requested": "Ornith",
                "resolved": resolved,
                "resolution": "adapter_pinned",
                "verification": "declared_digest" if strict else "declared_model",
                "strictly_comparable": strict,
            },
            "server_metrics": {"enabled": metrics},
        },
    }
    (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return run_dir


def test_smoke_selection_is_capability_aware():
    tasks = load_tasks(TASKS, "frontier_v3")
    assert _ids(select_smoke_tasks(tasks, ["piagent"])) == [CORE_TASK_ID]
    assert _ids(select_smoke_tasks(tasks, ["hermes"])) == [CORE_TASK_ID, BROWSER_TASK_ID]
    assert _ids(select_smoke_tasks(tasks, ["opencode"])) == [CORE_TASK_ID, SUBAGENT_TASK_ID]
    assert _ids(select_smoke_tasks(tasks, ["agentzero"])) == [
        CORE_TASK_ID,
        BROWSER_TASK_ID,
        SUBAGENT_TASK_ID,
    ]
    assert _ids(select_smoke_tasks(tasks, ["hermes", "piagent", "opencode", "agentzero"])) == [
        CORE_TASK_ID,
        BROWSER_TASK_ID,
        SUBAGENT_TASK_ID,
    ]


def test_smoke_report_accepts_expected_unsupported_rows(tmp_path: Path):
    tasks = load_tasks(TASKS, "frontier_v3")
    selected = select_smoke_tasks(tasks, ["piagent", "agentzero"])
    smoke_id = "smoke-contract"
    pi = _write_run(
        tmp_path,
        "piagent",
        smoke_id,
        [
            {"task_id": CORE_TASK_ID, "status": "completed", "success": True, "score": 100, "events": []},
            {"task_id": BROWSER_TASK_ID, "status": "unsupported", "success": False, "score": None, "events": []},
            {"task_id": SUBAGENT_TASK_ID, "status": "unsupported", "success": False, "score": None, "events": []},
        ],
    )
    agentzero = _write_run(
        tmp_path,
        "agentzero",
        smoke_id,
        [
            {"task_id": CORE_TASK_ID, "status": "completed", "success": True, "score": 100, "events": [{"type": "tool_call"}]},
            {"task_id": BROWSER_TASK_ID, "status": "completed", "success": True, "score": 100, "events": [{"type": "tool_call"}]},
            {"task_id": SUBAGENT_TASK_ID, "status": "completed", "success": True, "score": 100, "events": [{"type": "subagent_start"}]},
        ],
    )

    report = build_smoke_report({"piagent": [pi], "agentzero": [agentzero]}, selected)
    assert report["integration_ok"] is True
    assert report["strict_model_ready"] is True
    assert report["server_metrics_ready"] is True
    pi_report = next(item for item in report["harnesses"] if item["harness"] == "piagent")
    unsupported = [task for task in pi_report["runs"][0]["tasks"] if not task["expected_supported"]]
    assert {task["task_id"] for task in unsupported} == {BROWSER_TASK_ID, SUBAGENT_TASK_ID}
    assert all(task["ok"] for task in unsupported)


def test_smoke_report_fails_model_binding_even_when_task_passes(tmp_path: Path):
    tasks = load_tasks(TASKS, "frontier_v3")
    selected = select_smoke_tasks(tasks, ["piagent"])
    run_dir = _write_run(
        tmp_path,
        "piagent",
        "smoke-model",
        [{"task_id": CORE_TASK_ID, "status": "completed", "success": True, "score": 100, "events": []}],
        resolved="DifferentModel",
    )
    report = build_smoke_report({"piagent": [run_dir]}, selected)
    assert report["integration_ok"] is False
    assert report["harnesses"][0]["runs"][0]["model"]["binding_ok"] is False


def test_smoke_readiness_dimensions_are_independent(tmp_path: Path):
    tasks = load_tasks(TASKS, "frontier_v3")
    selected = select_smoke_tasks(tasks, ["piagent"])
    run_dir = _write_run(
        tmp_path,
        "piagent",
        "smoke-readiness",
        [{"task_id": CORE_TASK_ID, "status": "completed", "success": True, "score": 100, "events": []}],
        strict=False,
        metrics=False,
    )
    report = build_smoke_report({"piagent": [run_dir]}, selected)
    assert report["integration_ok"] is True
    assert report["strict_model_ready"] is False
    assert report["server_metrics_ready"] is False


def test_smoke_discovery_uses_metadata_not_model_path(tmp_path: Path):
    _write_run(
        tmp_path,
        "piagent",
        "smoke-find-r01",
        [{"task_id": CORE_TASK_ID, "status": "completed", "success": True}],
    )
    _write_run(
        tmp_path,
        "piagent",
        "other-run",
        [{"task_id": CORE_TASK_ID, "status": "completed", "success": True}],
    )
    found = discover_smoke_run_dirs(tmp_path, "smoke-find")
    assert list(found) == ["piagent"]
    assert [path.name for path in found["piagent"]] == ["smoke-find-r01"]
