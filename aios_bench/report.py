from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def load_results(root: Path) -> list[dict]:
    rows = []
    for path in root.glob("*/**/results.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_summary(root: Path) -> dict:
    rows = load_results(root)
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("harness", "unknown"), row.get("model", "unknown"))].append(row)

    comparisons = []
    for (harness, model), items in sorted(groups.items()):
        scores = [float(x.get("score", 0)) for x in items]
        comparisons.append({
            "harness": harness,
            "model": model,
            "tasks": len(items),
            "passed": sum(bool(x.get("success")) for x in items),
            "success_rate": sum(bool(x.get("success")) for x in items) / len(items) * 100 if items else 0,
            "mean_score": sum(scores) / len(scores) if scores else 0,
            "runtime_seconds": sum(float(x.get("duration_seconds", 0)) for x in items),
            "telemetry_rate": sum(bool(x.get("telemetry_available")) for x in items) / len(items) * 100 if items else 0,
        })
    return {"runs": comparisons, "result_count": len(rows)}


def write_summary(root: Path) -> Path:
    path = root / "summary.json"
    path.write_text(json.dumps(build_summary(root), indent=2), encoding="utf-8")
    return path
