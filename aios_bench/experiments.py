from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


EXPERIMENT_SCHEMA = "aios-bench/experiment/v2"


@dataclass(frozen=True)
class TaskBlock:
    index: int
    task_id: str
    block_seed: int
    task_seed: int
    harness_order: tuple[str, ...]


def _write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def make_experiment_id(suite: str = "frontier_v3") -> str:
    safe_suite = str(suite).strip().lower().replace("_", "-")
    if safe_suite not in {"frontier-v3", "frontier-v4"}:
        raise ValueError(f"unsupported experiment suite: {suite}")
    return datetime.now().astimezone().strftime(
        f"%Y-%m-%d_%H%M%S_%f_{safe_suite}-exp"
    )


def derive_seed(base_seed: int, *parts: object) -> int:
    payload = ":".join([str(int(base_seed)), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def matched_schedule(task_ids: Iterable[str], harnesses: Iterable[str], orchestration_seed: int) -> list[TaskBlock]:
    """Return deterministic task blocks with independently shuffled harness order.

    Every harness sees the same task/block seed. Only the order inside each task
    block changes, spreading host/server drift across harnesses without changing
    task semantics.
    """
    names = tuple(harnesses)
    blocks: list[TaskBlock] = []
    for index, task_id in enumerate(task_ids, 1):
        block_seed = derive_seed(orchestration_seed, "block", task_id)
        task_seed = derive_seed(orchestration_seed, "task", task_id)
        order = list(names)
        random.Random(block_seed).shuffle(order)
        blocks.append(TaskBlock(index, str(task_id), block_seed, task_seed, tuple(order)))
    return blocks


def annotate_experiment(
    run_dir: Path,
    *,
    experiment_id: str,
    repeat: int,
    orchestration_seed: int,
    schedule_mode: str,
    task_blocks: dict[str, TaskBlock] | None = None,
) -> None:
    """Attach experiment and matched-block identity to run metadata and raw rows."""
    metadata_path = run_dir / "run.json"
    metadata: dict = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.update({
            "experiment_schema": EXPERIMENT_SCHEMA,
            "experiment_id": experiment_id,
            "repeat": int(repeat),
            "orchestration_seed": int(orchestration_seed),
            "schedule_mode": schedule_mode,
        })
        _write_json_atomic(metadata_path, metadata)

    model = ((metadata.get("manifest") or {}).get("model") or {}) if isinstance(metadata, dict) else {}
    model_fingerprint = model.get("identity_fingerprint")
    model_strict = bool(model.get("strictly_comparable"))

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
        if not isinstance(row, dict):
            output.append(line)
            continue
        row.update({
            "experiment_schema": EXPERIMENT_SCHEMA,
            "experiment_id": experiment_id,
            "repeat": int(repeat),
            "orchestration_seed": int(orchestration_seed),
            "schedule_mode": schedule_mode,
            "model_identity_fingerprint": model_fingerprint,
            "model_strictly_comparable": model_strict,
        })
        block = (task_blocks or {}).get(str(row.get("task_id")))
        if block is not None:
            row.update({
                "block_index": block.index,
                "block_seed": block.block_seed,
                "task_seed": block.task_seed,
            })
        output.append(json.dumps(row, ensure_ascii=False))
    temporary = checkpoint.with_name(f".{checkpoint.name}.tmp")
    temporary.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
    temporary.replace(checkpoint)


def annotate_repeat(run_dir: Path, *, repeat: int, orchestration_seed: int) -> None:
    """Compatibility wrapper for sequential single-harness repetitions."""
    annotate_experiment(
        run_dir,
        experiment_id=f"{run_dir.name}-repeat-series",
        repeat=repeat,
        orchestration_seed=orchestration_seed,
        schedule_mode="sequential",
    )
