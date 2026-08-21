from __future__ import annotations

import math
from html import escape
from pathlib import Path
from typing import Any

from .report import build_summary, load_results, summarize_rows
from .statistics import (
    aggregate_repeat_rows,
    failure_distributions,
    paired_comparisons,
    server_efficiency_groups,
)


def _rows(results_root: Path) -> list[dict[str, Any]]:
    """Compatibility wrapper around the report module's canonical loader."""
    return load_results(results_root)


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compatibility wrapper using the same aggregation as summary.json."""
    return summarize_rows(rows)


def _display(value: Any, default: str = "unknown") -> str:
    return escape(str(value) if value not in (None, "") else default)


def _score(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.1f}" if math.isfinite(number) else "n/a"


def _percent(value: Any) -> str:
    try:
        number = float(value) * 100
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.1f}%" if math.isfinite(number) else "n/a"


def _interval(value: Any, *, percent: bool = False) -> str:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return "n/a"
    if percent:
        return f"{_percent(value[0])} – {_percent(value[1])}"
    return f"{_score(value[0])} – {_score(value[1])}"


def _breakdown_card(run: dict[str, Any], field: str, prefix: str = "") -> str:
    title = f'{_display(run.get("harness"))} × {_display(run.get("model"))}'
    identity = (
        f'{_display(run.get("suite"))} · {_display(run.get("suite_revision"))[:12]} · '
        f'{_display(run.get("run_id"))}'
    )
    parts = [f'<div class="card"><strong>{title}</strong><br><small>{identity}</small>']
    values = run.get(field)
    if isinstance(values, dict):
        for name, raw_value in sorted(values.items(), key=lambda item: str(item[0])):
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric):
                continue
            width = max(0.0, min(100.0, numeric))
            label = f"{prefix}{_display(name)}"
            parts.append(
                f'<p><small>{label}</small><br>{numeric:.1f}/100</p>'
                f'<div class="bar"><div class="fill" style="width:{width:.1f}%"></div></div>'
            )
    parts.append("</div>")
    return "".join(parts)


def _reliability_rows(groups: list[dict[str, Any]]) -> str:
    return "".join(
        '<tr>'
        f'<td>{_display(item.get("harness"))}</td>'
        f'<td>{_display(item.get("model"))}</td>'
        f'<td>{int(item.get("repeat_count", 0))}</td>'
        f'<td>{int(item.get("successes", 0))}/{int(item.get("attempts", 0))}</td>'
        f'<td>{_percent(item.get("attempt_success_rate"))}</td>'
        f'<td>{_interval(item.get("attempt_wilson_95"), percent=True)}</td>'
        f'<td>{_score(item.get("median_score"))}</td>'
        f'<td>{_interval(item.get("score_range"))}</td>'
        '</tr>'
        for item in groups
    )


def _paired_rows(comparisons: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in comparisons:
        if not item.get("comparable"):
            rows.append(
                '<tr>'
                f'<td>{_display(item.get("harness_a"))}</td>'
                f'<td>{_display(item.get("harness_b"))}</td>'
                f'<td colspan="7"><small>not comparable: {_display(item.get("reason"))}</small></td>'
                '</tr>'
            )
            continue
        rows.append(
            '<tr>'
            f'<td>{_display(item.get("harness_a"))}</td>'
            f'<td>{_display(item.get("harness_b"))}</td>'
            f'<td>{int(item.get("matched_tasks", 0))}</td>'
            f'<td>{int(item.get("matched_observations", 0))}</td>'
            f'<td>{_score(item.get("mean_score_delta_a_minus_b"))}</td>'
            f'<td>{_interval(item.get("cluster_bootstrap_95"))}</td>'
            f'<td>{_score(item.get("sign_flip_p_value"))}</td>'
            f'<td>{int(item.get("wins_a", 0))}/{int(item.get("wins_b", 0))}/{int(item.get("ties", 0))}</td>'
            f'<td>{int(item.get("a_pass_b_fail", 0))}/{int(item.get("b_pass_a_fail", 0))}</td>'
            '</tr>'
        )
    return "".join(rows)


def _failure_rows(groups: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in groups:
        counts = item.get("counts") if isinstance(item.get("counts"), dict) else {}
        rendered = " · ".join(
            f'{_display(kind)}={int(count)}' for kind, count in sorted(counts.items())
        ) or "none"
        rows.append(
            '<tr>'
            f'<td>{_display(item.get("harness"))}</td>'
            f'<td>{_display(item.get("model"))}</td>'
            f'<td>{int(item.get("observations", 0))}</td>'
            f'<td>{rendered}</td>'
            '</tr>'
        )
    return "".join(rows)


def _efficiency_rows(groups: list[dict[str, Any]]) -> str:
    return "".join(
        '<tr>'
        f'<td>{_display(item.get("harness"))}</td>'
        f'<td>{_display(item.get("model"))}</td>'
        f'<td>{int(item.get("server_verified_tasks", 0))}</td>'
        f'<td>{int(item.get("prompt_tokens", 0)):,}</td>'
        f'<td>{int(item.get("output_tokens", 0)):,}</td>'
        f'<td>{_score(item.get("prompt_tokens_per_second"))}</td>'
        f'<td>{_score(item.get("generation_tokens_per_second"))}</td>'
        '</tr>'
        for item in groups
    )


def build_dashboard(results_root: Path, output_dir: Path | None = None) -> Path:
    results_root.mkdir(parents=True, exist_ok=True)
    summary = build_summary(results_root)
    summaries = summary["runs"]
    latest = summary["leaderboard"]
    raw_rows = load_results(results_root)
    filters = {
        "suite": summary.get("selected_suite"),
        "suite_revision": summary.get("selected_suite_revision"),
    }
    reliability = aggregate_repeat_rows(raw_rows, **filters)
    paired = paired_comparisons(raw_rows, **filters)
    failures = failure_distributions(raw_rows, **filters)
    efficiency = server_efficiency_groups(raw_rows, **filters)
    selected = (
        f'{_display(summary.get("selected_suite"))} · '
        f'{_display(summary.get("selected_suite_revision"))}'
        if summary.get("selected_suite") and summary.get("selected_suite_revision")
        else "none"
    )

    cards = "".join(
        '<tr>'
        f'<td>{_display(item.get("harness"))}</td>'
        f'<td>{_display(item.get("model"))}</td>'
        f'<td>{_display(item.get("suite"))}</td>'
        f'<td><code>{_display(item.get("suite_revision"))[:12]}</code></td>'
        f'<td><code>{_display(item.get("execution_fingerprint"), "unreported")[:12]}</code></td>'
        f'<td>{_display(item.get("run_id"))}</td>'
        f'<td><strong>{_score(item.get("mean_score"))}</strong></td>'
        f'<td>{int(item.get("passed", 0))}/{int(item.get("comparable_tasks", 0))}</td>'
        f'<td>{int(item.get("unsupported", 0))}</td>'
        f'<td>{int(item.get("blocked", 0))}</td>'
        f'<td>{float(item.get("success_rate", 0)):.1f}%</td>'
        f'<td>{float(item.get("runtime_seconds", 0)) / 60:.1f} min</td>'
        '</tr>'
        for item in latest
    )
    history = "".join(
        '<tr>'
        f'<td>{_display(item.get("run_id"))}</td>'
        f'<td>{_display(item.get("harness"))}</td>'
        f'<td>{_display(item.get("model"))}</td>'
        f'<td>{_display(item.get("suite"))}</td>'
        f'<td><code>{_display(item.get("suite_revision"))[:12]}</code></td>'
        f'<td><code>{_display(item.get("execution_fingerprint"), "unreported")[:12]}</code></td>'
        f'<td>{_display(item.get("status"))}</td>'
        f'<td>{_score(item.get("mean_score"))}</td>'
        f'<td>{int(item.get("passed", 0))}/{int(item.get("comparable_tasks", 0))}</td>'
        f'<td>{int(item.get("unsupported", 0))}</td>'
        f'<td>{int(item.get("blocked", 0))}</td>'
        f'<td>{_display(item.get("eligibility_reason"))}</td>'
        f'<td><code>{_display(item.get("git_commit"))[:12]}{("*" if item.get("git_dirty") else "")}</code></td>'
        '</tr>'
        for item in sorted(
            summaries,
            key=lambda item: (
                str(item.get("finished_at") or ""),
                str(item.get("started_at") or ""),
                str(item.get("run_id") or ""),
            ),
            reverse=True,
        )
    )
    capabilities = "".join(_breakdown_card(item, "categories") for item in latest)
    tiers = "".join(_breakdown_card(item, "tiers", "Tier ") for item in latest)
    reliability_table = _reliability_rows(reliability)
    paired_table = _paired_rows(paired)
    failure_table = _failure_rows(failures)
    efficiency_table = _efficiency_rows(efficiency)

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOS-bench Dashboard</title>
<style>:root{{color-scheme:dark}}body{{font-family:system-ui,sans-serif;margin:32px;background:#111;color:#eee}}h1{{margin-bottom:4px}}.meta{{color:#999;margin-bottom:24px}}table{{border-collapse:collapse;width:100%;max-width:1400px}}th,td{{padding:12px;border-bottom:1px solid #333;text-align:left;vertical-align:top}}th{{color:#aaa}}code{{font-size:.9em}}.panel{{margin-top:28px;max-width:1400px;padding:20px;border:1px solid #333;border-radius:12px;overflow:auto}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:20px}}.card{{border:1px solid #333;border-radius:12px;padding:16px}}.bar{{height:8px;background:#333;border-radius:4px;overflow:hidden}}.fill{{height:100%;background:#aaa}}small{{color:#999}}</style></head><body><h1>AIOS-bench</h1>
<div class="meta">Harness × model comparison — newest observed suite revision: {selected}. Capability, reliability and efficiency are reported separately.</div>
<div class="panel"><h2>Latest capability leaderboard</h2><table><thead><tr><th>Harness</th><th>Model</th><th>Suite</th><th>Revision</th><th>Profile</th><th>Run</th><th>Score</th><th>Passed</th><th>Unsupported</th><th>Blocked</th><th>Success</th><th>Runtime</th></tr></thead><tbody>{cards or '<tr><td colspan="12">No eligible benchmark results yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Reliability across repeats</h2><p><small>Attempt-level pass rate and Wilson 95% interval. Score range is descriptive; capability scoring is unchanged.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Repeats</th><th>Passed attempts</th><th>Pass rate</th><th>Wilson 95%</th><th>Median score</th><th>Score range</th></tr></thead><tbody>{reliability_table or '<tr><td colspan="8">No repeated observations yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Paired harness comparisons</h2><p><small>Strict same-model matched observations only. Δ = score(A) − score(B); CI is task-cluster bootstrap; p is paired sign-flip.</small></p><table><thead><tr><th>A</th><th>B</th><th>Tasks</th><th>Observations</th><th>Mean Δ</th><th>95% CI</th><th>p</th><th>W/L/T</th><th>A-only pass / B-only pass</th></tr></thead><tbody>{paired_table or '<tr><td colspan="9">No strict matched comparisons yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Failure taxonomy</h2><table><thead><tr><th>Harness</th><th>Model</th><th>Observations</th><th>Counts</th></tr></thead><tbody>{failure_table or '<tr><td colspan="4">No classified observations yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Server-verified efficiency</h2><p><small>Only llama.cpp server-verified rows are included. Endpoint counters require an exclusive benchmark server for clean attribution.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Verified tasks</th><th>Prompt tokens</th><th>Output tokens</th><th>Prompt tok/s</th><th>Generation tok/s</th></tr></thead><tbody>{efficiency_table or '<tr><td colspan="7">No server-verified efficiency data yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Run history</h2><table><thead><tr><th>Run</th><th>Harness</th><th>Model</th><th>Suite</th><th>Revision</th><th>Profile</th><th>Status</th><th>Score</th><th>Passed</th><th>Unsupported</th><th>Blocked</th><th>Eligibility</th><th>Git commit</th></tr></thead><tbody>{history or '<tr><td colspan="13">No benchmark runs yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Difficulty tiers</h2><p><small>T3 = advanced, T4 = expert, T5 = frontier.</small></p><div id="tiers" class="grid">{tiers}</div></div>
<div class="panel"><h2>Capability breakdown</h2><div id="capabilities" class="grid">{capabilities}</div></div>
</body></html>'''
    destination = output_dir or results_root
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "dashboard.html"
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(output)
    return output
