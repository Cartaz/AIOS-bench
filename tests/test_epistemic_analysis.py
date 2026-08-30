from __future__ import annotations

from core.benchmark.epistemic_analysis import epistemic_twin_metrics


def _row(*, harness: str, metrics: dict, skill_mode: str = "no_skill") -> dict:
    return {
        "harness": harness,
        "model": "model-a",
        "suite": "frontier_v4",
        "suite_revision": "rev-a",
        "variant_family": "epistemic_twins",
        "status": "completed",
        "comparable": True,
        "skill_mode": skill_mode,
        "evaluation": {"metrics": {"epistemic_twins": metrics}},
    }


def test_epistemic_metrics_keep_both_failure_directions_visible() -> None:
    rows = [
        _row(
            harness="piagent",
            metrics={
                "strict_complete_pass": True,
                "full_decision_accuracy": 1.0,
                "valid_twin_acceptance_rate": 1.0,
                "corrupted_twin_rejection_rate": 1.0,
                "false_premise_compliance_rate": 0.0,
                "overcautious_refusal_rate": 0.0,
                "premise_accuracy": 1.0,
                "evidence_accuracy": 1.0,
                "pair_action_accuracy": 1.0,
                "pair_count": 6,
                "case_count": 12,
                "missing_case_count": 0,
                "extra_case_count": 0,
                "duplicate_case_count": 0,
            },
        ),
        _row(
            harness="piagent",
            metrics={
                "strict_complete_pass": False,
                "full_decision_accuracy": 0.5,
                "valid_twin_acceptance_rate": 1.0,
                "corrupted_twin_rejection_rate": 0.0,
                "false_premise_compliance_rate": 1.0,
                "overcautious_refusal_rate": 0.0,
                "premise_accuracy": 0.5,
                "evidence_accuracy": 1.0,
                "pair_action_accuracy": 0.0,
                "pair_count": 6,
                "case_count": 12,
                "missing_case_count": 0,
                "extra_case_count": 0,
                "duplicate_case_count": 0,
            },
        ),
    ]

    groups = epistemic_twin_metrics(
        rows,
        suite="frontier_v4",
        suite_revision="rev-a",
    )

    assert len(groups) == 1
    item = groups[0]
    assert item["observations"] == 2
    assert item["strict_pass_rate"] == 0.5
    assert item["mean_full_decision_accuracy"] == 0.75
    assert item["mean_valid_twin_acceptance_rate"] == 1.0
    assert item["mean_corrupted_twin_rejection_rate"] == 0.5
    assert item["mean_false_premise_compliance_rate"] == 0.5
    assert item["mean_overcautious_refusal_rate"] == 0.0
    assert item["mean_pair_action_accuracy"] == 0.5
    assert item["total_pair_count"] == 12
    assert item["total_case_count"] == 24


def test_epistemic_metrics_filter_other_families_and_noncomparable_rows() -> None:
    valid = _row(
        harness="piagent",
        metrics={
            "strict_complete_pass": False,
            "full_decision_accuracy": 0.5,
            "valid_twin_acceptance_rate": 0.5,
            "corrupted_twin_rejection_rate": 0.5,
            "false_premise_compliance_rate": 0.5,
            "overcautious_refusal_rate": 0.5,
            "premise_accuracy": 0.5,
            "evidence_accuracy": 0.5,
            "pair_action_accuracy": 0.25,
            "pair_count": 4,
            "case_count": 8,
            "missing_case_count": 0,
            "extra_case_count": 0,
            "duplicate_case_count": 0,
        },
    )
    noncomparable = dict(valid)
    noncomparable["comparable"] = False
    other = dict(valid)
    other["variant_family"] = "cross_artifact"

    groups = epistemic_twin_metrics([valid, noncomparable, other])

    assert len(groups) == 1
    assert groups[0]["observations"] == 1
