import json
from pathlib import Path

import pytest

from aios_bench.tasks import load_tasks


def _catalog(tmp_path: Path, items: list[dict], name: str = "coding") -> Path:
    directory = tmp_path / "frontier_v3"
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(items), encoding="utf-8")
    return tmp_path


def _task(**changes) -> dict:
    value = {
        "id": "coding_001", "category": "coding", "prompt": "Do it", "tier": 3,
        "acceptance": [{"type": "reference", "task_id": "coding_001"}],
    }
    value.update(changes)
    return value


def test_catalog_rejects_path_traversal_task_ids(tmp_path: Path):
    root = _catalog(tmp_path, [_task(id="../escape")])
    with pytest.raises(ValueError, match="Unsafe task id"):
        load_tasks(root)


def test_catalog_rejects_mismatched_reference_oracle(tmp_path: Path):
    root = _catalog(tmp_path, [_task(acceptance=[{"type": "reference", "task_id": "other"}])])
    with pytest.raises(ValueError, match="matching reference"):
        load_tasks(root)


def test_catalog_rejects_category_filename_mismatch(tmp_path: Path):
    root = _catalog(tmp_path, [_task(category="browser")])
    with pytest.raises(ValueError, match="category"):
        load_tasks(root)


def test_catalog_loads_valid_behavioral_acceptance(tmp_path: Path):
    root = _catalog(tmp_path, [_task(behavioral_acceptance=[
        {"type": "preserved_state", "path": "keep.txt"},
        {"type": "required_evidence", "event_type": "tool_call", "data": {"tool": "probe"}},
    ])])

    task = load_tasks(root)[0]

    assert task.behavioral_acceptance == (
        {"type": "preserved_state", "path": "keep.txt"},
        {"type": "required_evidence", "event_type": "tool_call", "data": {"tool": "probe"}},
    )


def test_catalog_rejects_invalid_behavioral_acceptance(tmp_path: Path):
    root = _catalog(tmp_path, [_task(behavioral_acceptance=[
        {"type": "preserved_state", "path": "../outside"},
    ])])

    with pytest.raises(ValueError, match="Invalid behavioral_acceptance"):
        load_tasks(root)
