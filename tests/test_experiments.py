import json
from pathlib import Path

from aios_bench.experiments import annotate_repeat


def test_repeat_annotation_updates_manifest_and_rows(tmp_path: Path):
    (tmp_path / "run.json").write_text(json.dumps({"run_id": "r"}), encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(json.dumps({"task_id": "t", "score": 100}) + "\n", encoding="utf-8")
    annotate_repeat(tmp_path, repeat=2, orchestration_seed=43)
    metadata = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "results.jsonl").read_text(encoding="utf-8"))
    assert metadata["repeat"] == row["repeat"] == 2
    assert metadata["orchestration_seed"] == row["orchestration_seed"] == 43
    assert metadata["experiment_schema"] == "aios-bench/repeat/v1"
