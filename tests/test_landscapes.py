import json
from pathlib import Path

from aios_bench.dashboard import build_dashboard
from aios_bench.landscapes import pressure_landscapes, pressure_paired_comparisons
from aios_bench.report import build_summary


def _row(
    harness: str,
    *,
    score: float = 100,
    success: bool = True,
    rows: int = 48,
    malformed: int = 2,
    distractors: int = 3,
    months: int = 6,
    seed: int = 101,
    digest: str = "variant-a",
    fingerprint: str = "strict-model-fp",
    landscape_profile: str = "stable-landscape-profile",
    experiment: str = "exp-1",
    repeat: int = 1,
) -> dict:
    return {
        "harness": harness,
        "agent": harness,
        "model": "ornith",
        "suite": "frontier_v4",
        "suite_revision": "revision-v4",
        "task_id": "autonomy_expense_001",
        "task_revision": 4,
        "category": "autonomy",
        "tier": 3,
        "status": "completed" if success else "failed",
        "success": success,
        "score": score,
        "comparable": True,
        "failure_kind": "PASS" if success else "WRONG",
        "variant_schema": "aios-bench/parametric/v1",
        "variant_family": "expense_report",
        "variant_seed": seed,
        "variant_digest": digest,
        "variant_parameters": {
            "rows": rows,
            "malformed_rows": malformed,
            "distractor_files": distractors,
            "months": months,
        },
        "execution_fingerprint": f"profile-{rows}-{malformed}-{distractors}-{months}",
        "landscape_execution_fingerprint": landscape_profile,
        "model_identity_fingerprint": fingerprint,
        "model_strictly_comparable": True,
        "schedule_mode": "matched_interleaved",
        "experiment_id": experiment,
        "repeat": repeat,
        "task_seed": seed,
    }


def test_pressure_landscape_preserves_joint_cells_and_marginal_axes():
    observations = [
        _row("piagent", rows=48, score=100, seed=101, digest="a"),
        _row("piagent", rows=48, malformed=4, score=49, success=False, seed=102, digest="b"),
        _row("piagent", rows=96, score=80, seed=103, digest="c"),
    ]

    groups = pressure_landscapes(
        observations,
        suite="frontier_v4",
        suite_revision="revision-v4",
    )

    assert len(groups) == 1
    group = groups[0]
    assert group["landscape_execution_fingerprint"] == "stable-landscape-profile"
    assert group["pressure_axes"] == ["distractor_files", "malformed_rows", "months", "rows"]
    assert len(group["full_vector_cells"]) == 3
    row_axis = {cell["value"]: cell for cell in group["axes"]["rows"]}
    assert row_axis[48]["aggregation"] == "marginal_over_other_coordinates"
    assert row_axis[48]["observations"] == 2
    assert row_axis[48]["unique_variants"] == 2
    assert row_axis[48]["pass_rate"] == 0.5
    assert row_axis[96]["mean_score"] == 80
    assert row_axis[48]["failure_counts"] == {"PASS": 1, "WRONG": 1}


def test_pressure_landscapes_never_mix_model_identities_or_execution_profiles():
    groups = pressure_landscapes([
        _row("piagent", fingerprint="fp-a", landscape_profile="profile-a"),
        _row("piagent", fingerprint="fp-b", landscape_profile="profile-a", seed=102, digest="b"),
        _row("piagent", fingerprint="fp-a", landscape_profile="profile-b", seed=103, digest="c"),
    ])
    assert len(groups) == 3
    identities = {
        (group["model_identity_fingerprint"], group["landscape_execution_fingerprint"])
        for group in groups
    }
    assert identities == {("fp-a", "profile-a"), ("fp-b", "profile-a"), ("fp-a", "profile-b")}


def test_pressure_pairs_require_exact_generated_variant_match():
    rows = [
        _row("hermes", score=90, seed=101, digest="same"),
        _row("piagent", score=70, seed=101, digest="same"),
        _row("hermes", score=100, seed=102, digest="only-a", repeat=2),
        _row("piagent", score=10, seed=102, digest="only-b", repeat=2),
    ]
    pairs = pressure_paired_comparisons(rows)
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["comparable"] is True
    assert pair["matched_observations"] == 1
    assert pair["mean_score_delta_a_minus_b"] == 20
    assert pair["wins_a"] == 1
    assert pair["wins_b"] == 0


def test_pressure_pairs_fail_closed_on_model_identity_mismatch():
    pairs = pressure_paired_comparisons([
        _row("hermes", fingerprint="model-a"),
        _row("piagent", fingerprint="model-b"),
    ])
    assert len(pairs) == 1
    assert pairs[0]["comparable"] is False
    assert pairs[0]["reason"] == "model_identity_mismatch"


def test_pressure_pairs_do_not_cross_experiment_boundaries():
    pairs = pressure_paired_comparisons([
        _row("hermes", score=90, experiment="exp-a"),
        _row("piagent", score=70, experiment="exp-b"),
    ])
    assert pairs == []


def test_build_summary_includes_selected_v4_landscape(tmp_path: Path):
    run = tmp_path / "piagent" / "ornith" / "runs" / "run-1"
    run.mkdir(parents=True)
    metadata = {
        "harness": "piagent",
        "model": "ornith",
        "run_id": "run-1",
        "suite": "frontier_v4",
        "suite_revision": "revision-v4",
        "task_count": 1,
        "status": "completed",
        "started_at": "2026-08-21T08:00:00Z",
        "finished_at": "2026-08-21T08:01:00Z",
    }
    (run / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run / "results.jsonl").write_text(json.dumps(_row("piagent")) + "\n", encoding="utf-8")

    summary = build_summary(tmp_path)

    assert summary["selected_suite"] == "frontier_v4"
    assert len(summary["pressure_landscapes"]) == 1
    assert summary["pressure_landscapes"][0]["variant_family"] == "expense_report"
    assert summary["pressure_paired_comparisons"] == []


def test_dashboard_renders_pressure_views_without_model_fingerprint(monkeypatch, tmp_path: Path):
    landscape = pressure_landscapes([
        _row("pi<agent>", fingerprint="DO-NOT-RENDER-MODEL-FP")
    ])[0]
    summary = {
        "runs": [],
        "leaderboard": [],
        "selected_suite": "frontier_v4",
        "selected_suite_revision": "revision-v4",
        "pressure_landscapes": [landscape],
        "pressure_paired_comparisons": [],
    }
    monkeypatch.setattr("aios_bench.dashboard.build_summary", lambda root: summary)
    monkeypatch.setattr("aios_bench.dashboard.load_results", lambda root: [])

    output = build_dashboard(tmp_path)
    html = output.read_text(encoding="utf-8")

    assert "Frontier v4 pressure response — marginal axes" in html
    assert "Frontier v4 joint pressure cells" in html
    assert "Matched harness deltas by pressure cell" in html
    assert "rows=48" in html
    assert "pi&lt;agent&gt;" in html
    assert "DO-NOT-RENDER-MODEL-FP" not in html
