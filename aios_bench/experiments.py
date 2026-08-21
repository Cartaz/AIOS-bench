from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_SCHEMA = "aios-bench/repeat/v1"


def _write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def annotate_repeat(run_dir: Path, *, repeat: int, orchestration_seed: int) -> None:
    """Attach repeat identity to a completed or aborted run and its raw rows."""
    metadata_path = run_dir / "run.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.update({
            "experiment_schema": EXPERIMENT_SCHEMA,
            "repeat": int(repeat),
            "orchestration_seed": int(orchestration_seed),
        })
        _write_json_atomic(metadata_path, metadata)

    checkpoint = run_dir / "results.jsonl"
    if not checkpoint.is_file():
        return
    output: list[str] = []
    for line in checkpoint.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            output.append(line)
            continue
        if isinstance(row, dict):
            row.update({
                "experiment_schema": EXPERIMENT_SCHEMA,
                "repeat": int(repeat),
                "orchestration_seed": int(orchestration_seed),
            })
            output.append(json.dumps(row, ensure_ascii=False))
        else:
            output.append(line)
    temporary = checkpoint.with_name(f".{checkpoint.name}.tmp")
    temporary.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
    temporary.replace(checkpoint)
