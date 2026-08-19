from __future__ import annotations

import json
from pathlib import Path
from html import escape


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
    latest: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row.get("harness", row.get("agent", "unknown")), row.get("model", "unknown"))
        latest.setdefault(key, []).append(row)

    summary = []
    for (harness, model), items in sorted(latest.items()):
        passed = sum(bool(x.get("success")) for x in items)
        total = len(items)
        seconds = sum(float(x.get("duration_seconds", 0)) for x in items)
        summary.append((harness, model, passed, total, seconds))

    cards = "".join(
        f'<tr><td>{escape(h)}</td><td>{escape(m)}</td><td><strong>{p}/{t}</strong></td>'
        f'<td>{(p/t*100 if t else 0):.1f}%</td><td>{s/60:.1f} min</td></tr>'
        for h, m, p, t, s in summary
    )
    payload = json.dumps(summary)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOS-bench Dashboard</title>
<style>
body{{font-family:system-ui,sans-serif;margin:40px;background:#111;color:#eee}} table{{border-collapse:collapse;width:100%;max-width:1000px}} th,td{{padding:12px;border-bottom:1px solid #333;text-align:left}} th{{color:#aaa}} .meta{{color:#aaa;margin-bottom:24px}}
</style></head><body><h1>AIOS-bench</h1>
<div class="meta">Local agent benchmark · longitudinal results are grouped by harness and model.</div>
<table><thead><tr><th>Harness</th><th>Model</th><th>Passed</th><th>Success</th><th>Runtime</th></tr></thead>
<tbody>{cards or '<tr><td colspan="5">No benchmark results yet.</td></tr>'}</tbody></table>
<script>window.AIOS_BENCH_SUMMARY={payload};</script>
</body></html>'''
    output = results_root / "dashboard.html"
    output.write_text(html, encoding="utf-8")
    return output
