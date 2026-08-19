from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def load_results(root: Path) -> list[dict]:
    rows = []
    seen_paths: set[Path] = set()
    for path in root.glob("*/**/results.jsonl"):
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_summary(root: Path) -> dict:
    rows = load_results(root)
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("harness", "unknown"), row.get("model", "unknown"), row.get("run_id", "legacy"))].append(row)

    comparisons = []
    for (harness, model, run_id), items in sorted(groups.items()):
        scores = [float(x.get("score", 0)) for x in items]
        comparisons.append({
            "run_id": run_id,
            "harness": harness,
            "model": model,
            "suite": items[0].get("suite", "legacy"),
            "suite_revision": items[0].get("suite_revision", "legacy"),
            "git_commit": items[0].get("git_commit", "unknown"),
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
