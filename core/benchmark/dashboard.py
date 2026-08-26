from __future__ import annotations

import math
from html import escape
from pathlib import Path
from typing import Any

from .report import build_summary, load_results, summarize_rows
from .resource_reporting import resource_efficiency_groups
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


def _bytes(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(number):
        return "n/a"
    gib = 1024 ** 3
    mib = 1024 ** 2
    if abs(number) >= gib:
        return f"{number / gib:.2f} GiB"
    return f"{number / mib:.1f} MiB"


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


def _resource_rows(groups: list[dict[str, Any]], side: str) -> str:
    rows: list[str] = []
    for item in groups:
        metrics = item.get(side)
        if not isinstance(metrics, dict):
            continue
        rows.append(
            '<tr>'
            f'<td>{_display(item.get("harness"))}</td>'
            f'<td>{_display(item.get("model"))}</td>'
            f'<td>{int(metrics.get("measured_tasks", 0))}</td>'
            f'<td>{_bytes(metrics.get("rss_peak_task_mean_bytes"))}</td>'
            f'<td>{_bytes(metrics.get("rss_peak_max_bytes"))}</td>'
            f'<td>{_bytes(metrics.get("rss_peak_delta_task_mean_bytes"))}</td>'
            f'<td>{_score(metrics.get("cpu_task_mean_percent"))}%</td>'
            f'<td>{int(metrics.get("vram_attributed_tasks", 0))}</td>'
            f'<td>{_bytes(metrics.get("vram_baseline_task_mean_bytes"))}</td>'
            f'<td>{_bytes(metrics.get("vram_peak_task_mean_bytes"))}</td>'
            f'<td>{_bytes(metrics.get("vram_peak_max_bytes"))}</td>'
            f'<td>{_bytes(metrics.get("vram_peak_delta_task_mean_bytes"))}</td>'
            f'<td>{_score(metrics.get("gpu_engine_time_task_mean_percent"))}%</td>'
            '</tr>'
        )
    return "".join(rows)


def _failure_text(value: Any) -> str:
    counts = value if isinstance(value, dict) else {}
    return " · ".join(
        f'{_display(kind)}={int(count)}' for kind, count in sorted(counts.items())
    ) or "none"


def _parameters_text(value: Any) -> str:
    parameters = value if isinstance(value, dict) else {}
    return " · ".join(
        f'{_display(name)}={_display(raw)}' for name, raw in sorted(parameters.items())
    ) or "none"


def _pressure_axis_rows(landscapes: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for landscape in landscapes:
        axes = landscape.get("axes") if isinstance(landscape.get("axes"), dict) else {}
        for axis, cells in sorted(axes.items()):
            if not isinstance(cells, list):
                continue
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                rows.append(
                    '<tr>'
                    f'<td>{_display(landscape.get("harness"))}</td>'
                    f'<td>{_display(landscape.get("model"))}</td>'
                    f'<td>{_display(landscape.get("variant_family"))}</td>'
                    f'<td>{_display(axis)}</td>'
                    f'<td>{_display(cell.get("value"))}</td>'
                    f'<td>{int(cell.get("observations", 0))}</td>'
                    f'<td>{int(cell.get("unique_variants", 0))}</td>'
                    f'<td>{_percent(cell.get("pass_rate"))}</td>'
                    f'<td>{_interval(cell.get("wilson_95"), percent=True)}</td>'
                    f'<td>{_score(cell.get("mean_score"))}</td>'
                    f'<td>{_score(cell.get("median_score"))}</td>'
                    f'<td>{_failure_text(cell.get("failure_counts"))}</td>'
                    '</tr>'
                )
    return "".join(rows)


def _pressure_cell_rows(landscapes: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for landscape in landscapes:
        cells = landscape.get("full_vector_cells") if isinstance(landscape.get("full_vector_cells"), list) else []
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            rows.append(
                '<tr>'
                f'<td>{_display(landscape.get("harness"))}</td>'
                f'<td>{_display(landscape.get("model"))}</td>'
                f'<td>{_display(landscape.get("variant_family"))}</td>'
                f'<td>{_parameters_text(cell.get("parameters"))}</td>'
                f'<td>{int(cell.get("observations", 0))}</td>'
                f'<td>{int(cell.get("unique_variants", 0))}</td>'
                f'<td>{_percent(cell.get("pass_rate"))}</td>'
                f'<td>{_interval(cell.get("wilson_95"), percent=True)}</td>'
                f'<td>{_score(cell.get("mean_score"))}</td>'
                f'<td>{_failure_text(cell.get("failure_counts"))}</td>'
                '</tr>'
            )
    return "".join(rows)


def _pressure_pair_rows(comparisons: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in comparisons:
        if not item.get("comparable"):
            rows.append(
                '<tr>'
                f'<td>{_display(item.get("harness_a"))}</td>'
                f'<td>{_display(item.get("harness_b"))}</td>'
                f'<td>{_display(item.get("variant_family"))}</td>'
                f'<td>{_parameters_text(item.get("parameters"))}</td>'
                f'<td colspan="5"><small>not comparable: {_display(item.get("reason"))}</small></td>'
                '</tr>'
            )
            continue
        rows.append(
            '<tr>'
            f'<td>{_display(item.get("harness_a"))}</td>'
            f'<td>{_display(item.get("harness_b"))}</td>'
            f'<td>{_display(item.get("variant_family"))}</td>'
            f'<td>{_parameters_text(item.get("parameters"))}</td>'
            f'<td>{int(item.get("matched_observations", 0))}</td>'
            f'<td>{_score(item.get("mean_score_delta_a_minus_b"))}</td>'
            f'<td>{_score(item.get("median_score_delta_a_minus_b"))}</td>'
            f'<td>{int(item.get("wins_a", 0))}/{int(item.get("wins_b", 0))}/{int(item.get("ties", 0))}</td>'
            f'<td>{int(item.get("a_pass_b_fail", 0))}/{int(item.get("b_pass_a_fail", 0))}</td>'
            '</tr>'
        )
    return "".join(rows)


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
    resources = resource_efficiency_groups(raw_rows, **filters)
    landscapes = summary.get("pressure_landscapes") if isinstance(summary.get("pressure_landscapes"), list) else []
    pressure_pairs = summary.get("pressure_paired_comparisons") if isinstance(summary.get("pressure_paired_comparisons"), list) else []
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
    client_resource_table = _resource_rows(resources, "client")
    server_resource_table = _resource_rows(resources, "server")
    pressure_axis_table = _pressure_axis_rows(landscapes)
    pressure_cell_table = _pressure_cell_rows(landscapes)
    pressure_pair_table = _pressure_pair_rows(pressure_pairs)

    resource_headers = (
        '<th>Harness</th><th>Model</th><th>Tasks</th><th>Mean task RSS peak</th>'
        '<th>Max RSS peak</th><th>Mean RSS Δ</th><th>Mean CPU</th>'
        '<th>VRAM tasks</th><th>Mean VRAM baseline</th><th>Mean VRAM peak</th>'
        '<th>Max VRAM peak</th><th>Mean VRAM Δ</th><th>Mean GPU engine</th>'
    )

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOS-bench Dashboard</title>
<style>:root{{color-scheme:dark}}body{{font-family:system-ui,sans-serif;margin:32px;background:#111;color:#eee}}h1{{margin-bottom:4px}}.meta{{color:#999;margin-bottom:24px}}table{{border-collapse:collapse;width:100%;max-width:1400px}}th,td{{padding:12px;border-bottom:1px solid #333;text-align:left;vertical-align:top;white-space:nowrap}}th{{color:#aaa}}code{{font-size:.9em}}.panel{{margin-top:28px;max-width:1400px;padding:20px;border:1px solid #333;border-radius:12px;overflow:auto}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:20px}}.card{{border:1px solid #333;border-radius:12px;padding:16px}}.bar{{height:8px;background:#333;border-radius:4px;overflow:hidden}}.fill{{height:100%;background:#aaa}}small{{color:#999}}</style></head><body><h1>AIOS-bench</h1>
<div class="meta">Harness × model comparison — newest observed suite revision: {selected}. Capability, reliability, pressure response and efficiency are reported separately.</div>
<div class="panel"><h2>Latest capability leaderboard</h2><table><thead><tr><th>Harness</th><th>Model</th><th>Suite</th><th>Revision</th><th>Profile</th><th>Run</th><th>Score</th><th>Passed</th><th>Unsupported</th><th>Blocked</th><th>Success</th><th>Runtime</th></tr></thead><tbody>{cards or '<tr><td colspan="12">No eligible benchmark results yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Reliability across repeats</h2><p><small>Attempt-level pass rate and Wilson 95% interval. Score range is descriptive; capability scoring is unchanged.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Repeats</th><th>Passed attempts</th><th>Pass rate</th><th>Wilson 95%</th><th>Median score</th><th>Score range</th></tr></thead><tbody>{reliability_table or '<tr><td colspan="8">No repeated observations yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Paired harness comparisons</h2><p><small>Strict same-model matched observations only. Δ = score(A) − score(B); CI is task-cluster bootstrap; p is paired sign-flip.</small></p><table><thead><tr><th>A</th><th>B</th><th>Tasks</th><th>Observations</th><th>Mean Δ</th><th>95% CI</th><th>p</th><th>W/L/T</th><th>A-only pass / B-only pass</th></tr></thead><tbody>{paired_table or '<tr><td colspan="9">No strict matched comparisons yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Frontier v4 pressure response — marginal axes</h2><p><small>Each row conditions on one observed coordinate value and marginalizes over other observed coordinates. Coordinates are workload descriptors, not assumed monotonic difficulty levels.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Family</th><th>Axis</th><th>Value</th><th>Obs.</th><th>Variants</th><th>Pass rate</th><th>Wilson 95%</th><th>Mean score</th><th>Median</th><th>Failure mix</th></tr></thead><tbody>{pressure_axis_table or '<tr><td colspan="12">No selected Frontier v4 pressure observations yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Frontier v4 joint pressure cells</h2><p><small>Joint cells preserve the complete generated pressure vector; no interpolation is performed between unobserved cells.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Family</th><th>Pressure vector</th><th>Obs.</th><th>Variants</th><th>Pass rate</th><th>Wilson 95%</th><th>Mean score</th><th>Failure mix</th></tr></thead><tbody>{pressure_cell_table or '<tr><td colspan="10">No joint pressure cells yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Matched harness deltas by pressure cell</h2><p><small>Strict same-model comparisons only. A pair is matched on experiment, repeat, task, task seed and variant digest. Δ = score(A) − score(B); these cell deltas are descriptive.</small></p><table><thead><tr><th>A</th><th>B</th><th>Family</th><th>Pressure vector</th><th>Matched</th><th>Mean Δ</th><th>Median Δ</th><th>W/L/T</th><th>A-only pass / B-only pass</th></tr></thead><tbody>{pressure_pair_table or '<tr><td colspan="9">No strict matched pressure-cell comparisons yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Failure taxonomy</h2><table><thead><tr><th>Harness</th><th>Model</th><th>Observations</th><th>Counts</th></tr></thead><tbody>{failure_table or '<tr><td colspan="4">No classified observations yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Server-verified efficiency</h2><p><small>Only llama.cpp server-verified rows are included. Endpoint counters require an exclusive benchmark server for clean attribution.</small></p><table><thead><tr><th>Harness</th><th>Model</th><th>Verified tasks</th><th>Prompt tokens</th><th>Output tokens</th><th>Prompt tok/s</th><th>Generation tok/s</th></tr></thead><tbody>{efficiency_table or '<tr><td colspan="7">No server-verified efficiency data yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Client resource cost</h2><p><small>AIOS-bench + harness process-tree cost. Memory peaks are reported as the mean per-task peak plus the maximum observed peak; memory is never summed across tasks. GPU/VRAM values are DRM client-attributed when available.</small></p><table><thead><tr>{resource_headers}</tr></thead><tbody>{client_resource_table or '<tr><td colspan="13">No client resource telemetry yet.</td></tr>'}</tbody></table></div>
<div class="panel"><h2>Inference server / model resource cost</h2><p><small>Inference-server process-tree cost from the optional remote resource agent. VRAM baseline represents the loaded server/model footprint; VRAM Δ highlights additional task-time pressure such as context/KV growth.</small></p><table><thead><tr>{resource_headers}</tr></thead><tbody>{server_resource_table or '<tr><td colspan="13">No inference-server resource telemetry yet.</td></tr>'}</tbody></table></div>
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
