from __future__ import annotations

from aios_bench.reconstruction_analysis import black_box_reconstruction_metrics


def _row(property_accuracy: float, transfer_accuracy: float, probes: int) -> dict:
    exact = (property_accuracy * 96 + transfer_accuracy * 64) / 160
    return {
        "harness": "piagent",
        "model": "ornith",
        "suite": "frontier_v4",
        "suite_revision": "rev-v48",
        "variant_family": "black_box_reconstruction",
        "status": "completed",
        "comparable": True,
        "evaluation": {
            "metrics": {
                "black_box_reconstruction": {
                    "property_accuracy": property_accuracy,
                    "transfer_accuracy": transfer_accuracy,
                    "exact_case_accuracy": exact,
                    "output_field_accuracy": exact,
                    "property_cases": 96,
                    "transfer_cases": 64,
                    "protocol_error_count": 0,
                    "implementation_returncode": 0,
                    "verifier_sandboxed": True,
                    "probe_count": probes,
                    "probe_budget": 48,
                }
            }
        },
    }


def test_reconstruction_metrics_keep_transfer_and_probe_efficiency_visible() -> None:
    groups = black_box_reconstruction_metrics([
        _row(1.0, 1.0, 20),
        _row(0.75, 0.5, 40),
    ])

    assert len(groups) == 1
    group = groups[0]
    assert group["observations"] == 2
    assert group["strict_passes"] == 1
    assert group["strict_pass_rate"] == 0.5
    assert group["mean_property_accuracy"] == 0.875
    assert group["mean_transfer_accuracy"] == 0.75
    assert group["total_probes"] == 60
    assert group["total_probe_budget"] == 96
    assert group["probe_utilization"] == 0.625


def test_reconstruction_metrics_ignore_other_families_and_noncomparable_rows() -> None:
    other = _row(1.0, 1.0, 1)
    other["variant_family"] = "wide_retrieval"
    unsupported = _row(1.0, 1.0, 1)
    unsupported["status"] = "unsupported"

    assert black_box_reconstruction_metrics([other, unsupported]) == []
