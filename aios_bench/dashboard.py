from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path


def _rows(results_root: Path) -> list[dict]:
    rows = []
    for path in results_root.glob("*/**/results.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_dashboard(results_root: Path) -> Path:
    results_root.mkdir(parents=True, exist_ok=True)
    rows = _rows(results_root)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("harness", row.get("agent", "unknown")), row.get("model", "unknown"))].append(row)

    summaries = []
    for (harness, model), items in sorted(grouped.items()):
        passed = sum(bool(x.get("success")) for x in items)
        total = len(items)
        scores = [float(x.get("score", 100.0 if x.get("success") else 0.0)) for x in items]
        seconds = sum(float(x.get("duration_seconds", 0)) for x in items)
        categories: dict[str, list[float]] = defaultdict(list)
        for x in items:
            categories[x.get("category", "unknown")].append(float(x.get("score", 0)))
        summaries.append({"harness": harness, "model": model, "passed": passed, "total": total,
                          "success": (passed / total * 100 if total else 0),
                          "score": (sum(scores) / len(scores) if scores else 0),
                          "runtime": seconds / 60,
                          "categories": {k: sum(v) / len(v) for k, v in categories.items()}})

    cards = "".join(
        f'<tr><td>{escape(x["harness"])}</td><td>{escape(x["model"])}</td>'
        f'<td><strong>{x["score"]:.1f}</strong></td><td>{x["passed"]}/{x["total"]}</td>'
        f'<td>{x["success"]:.1f}%</td><td>{x["runtime"]:.1f} min</td></tr>'
        for x in summaries
    )
    data = json.dumps(summaries, ensure_ascii=False)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOS-bench Dashboard</title>
<style>
:root{{color-scheme:dark}} body{{font-family:system-ui,sans-serif;margin:32px;background:#111;color:#eee}} h1{{margin-bottom:4px}} .meta{{color:#999;margin-bottom:24px}} table{{border-collapse:collapse;width:100%;max-width:1100px}} th,td{{padding:12px;border-bottom:1px solid #333;text-align:left}} th{{color:#aaa}} .score{{font-weight:700}} .panel{{margin-top:28px;max-width:1100px;padding:20px;border:1px solid #333;border-radius:12px}} code{{color:#ccc}}
</style></head><body><h1>AIOS-bench</h1>
<div class="meta">Harness × model comparison. Scores are persisted so stronger models can be compared longitudinally.</div>
<div class="panel"><table><thead><tr><th>Harness</th><th>Model</th><th>Score</th><th>Passed</th><th>Success</th><th>Runtime</th></tr></thead>
<tbody>{cards or '<tr><td colspan="6">No benchmark results yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Longitudinal comparison</h2><p>Run the same harness with a new model identifier. Historical runs remain separate, allowing <code>harness × model</code> comparisons over time.</p></div>
<script>window.AIOS_BENCH_RESULTS={data};</script>
</body></html>'''
    output = results_root / "dashboard.html"
    output.write_text(html, encoding="utf-8")
    return output
