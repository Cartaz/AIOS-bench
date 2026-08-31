from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from aios_bench.failures import VERIFICATION_FAILURE
from aios_bench.parametric import (
    BlackBoxReconstructionPressure,
    evaluate_variant,
    materialize_variant,
    start_variant_runtime,
)
from aios_bench.parametric_goldens import materialize_parametric_golden


TASK_ID = "software_black_box_001"


def _request(endpoint: str, token: str, method: str, path: str, value: object | None = None):
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if value is not None:
        data = json.dumps(value).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(endpoint + path, data=data, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _valid_input() -> dict[str, object]:
    return {
        "region": "eu",
        "plan": "plus",
        "units": 37,
        "priority": 3,
        "active": True,
        "tags": ["alpha", "gamma"],
        "noise_01": "ignored",
    }


def test_black_box_pressure_validation_and_unknown_fields() -> None:
    with pytest.raises(ValueError, match="rule_count"):
        BlackBoxReconstructionPressure(rule_count=4)
    with pytest.raises(ValueError, match="unknown black-box reconstruction pressure fields"):
        BlackBoxReconstructionPressure.from_mapping({"mystery": 1})


def test_black_box_variant_is_deterministic_and_pressure_sensitive(tmp_path: Path) -> None:
    pressure = BlackBoxReconstructionPressure(
        rule_count=8,
        public_examples=10,
        probe_budget=24,
        distractor_fields=4,
        max_units=640,
    )
    first = materialize_variant(
        "black_box_reconstruction",
        tmp_path / "first",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    second = materialize_variant(
        "black_box_reconstruction",
        tmp_path / "second",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    different_seed = materialize_variant(
        "black_box_reconstruction",
        tmp_path / "seed",
        seed=2027,
        parameters=pressure.to_dict(),
    )
    different_pressure = materialize_variant(
        "black_box_reconstruction",
        tmp_path / "pressure",
        seed=2026,
        parameters={**pressure.to_dict(), "max_units": 700},
    )

    assert first["variant_digest"] == second["variant_digest"]
    assert (tmp_path / "first" / "examples" / "public_examples.jsonl").read_bytes() == (
        tmp_path / "second" / "examples" / "public_examples.jsonl"
    ).read_bytes()
    assert first["variant_digest"] != different_seed["variant_digest"]
    assert first["variant_digest"] != different_pressure["variant_digest"]


def test_black_box_workspace_exposes_behavior_not_reference_spec(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("black_box_reconstruction", workspace, seed=41)

    exposed = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(workspace.rglob("*"))
        if path.is_file()
    )
    assert "reference_spec" not in exposed
    assert "plan_multipliers" not in exposed
    assert "region_offsets" not in exposed
    assert oracle["reference_spec"]["schema"] == "aios-bench/black-box-reference-spec/v1"
    assert not (workspace / "solution" / "reconstruct.py").exists()


def test_black_box_runtime_enforces_probe_budget_and_cleans_binding(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant(
        "black_box_reconstruction",
        workspace,
        seed=51,
        parameters={"probe_budget": 8},
    )
    runtime = start_variant_runtime(
        "black_box_reconstruction",
        workspace,
        run_dir=run_dir,
        task_id=TASK_ID,
        oracle=oracle,
    )
    endpoint = runtime.environment["AIOS_BENCH_BLACK_BOX_URL"]
    token = runtime.environment["AIOS_BENCH_BLACK_BOX_TOKEN"]
    try:
        contract = _request(endpoint, token, "GET", "/v1/contract")
        assert contract["probe_budget"] == 8
        assert contract["probes_remaining"] == 8
        assert set(contract["output"]["exact_fields"]) == {
            "bucket",
            "score",
            "normalized_units",
            "flags",
        }
        for expected_remaining in range(7, -1, -1):
            result = _request(
                endpoint,
                token,
                "POST",
                "/v1/probe",
                {"input": _valid_input()},
            )
            assert result["probes_remaining"] == expected_remaining
        with pytest.raises(HTTPError) as exhausted:
            _request(
                endpoint,
                token,
                "POST",
                "/v1/probe",
                {"input": _valid_input()},
            )
        assert exhausted.value.code == 429
        with pytest.raises(HTTPError) as unauthorized:
            _request(endpoint, "wrong", "GET", "/v1/contract")
        assert unauthorized.value.code == 401
        assert (workspace / "reference" / "api.json").is_file()
    finally:
        runtime.close()

    assert not (workspace / "reference" / "api.json").exists()
    log = run_dir / "black_box" / f"{TASK_ID}.probes.jsonl"
    assert len(log.read_text(encoding="utf-8").splitlines()) == 8


def test_black_box_golden_passes_hidden_property_and_transfer_suites(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is required for grader-hidden verification")
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("black_box_reconstruction", workspace, seed=61)
    materialize_parametric_golden(
        "black_box_reconstruction",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )

    grade = evaluate_variant(
        "black_box_reconstruction",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )

    assert grade.passed is True, grade.detail
    assert grade.partial_credit == 1.0
    assert grade.metrics["property_accuracy"] == 1.0
    assert grade.metrics["transfer_accuracy"] == 1.0
    assert grade.metrics["verifier_sandboxed"] is True
    assert grade.metrics["probe_count"] == 0


def test_black_box_fixture_specific_stub_fails_hidden_generalization(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is required for grader-hidden verification")
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("black_box_reconstruction", workspace, seed=71)
    solution = workspace / "solution" / "reconstruct.py"
    solution.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    if line.strip():\n"
        "        print(json.dumps({'bucket':'low','score':0,'normalized_units':0,'flags':[]}))\n",
        encoding="utf-8",
    )

    grade = evaluate_variant(
        "black_box_reconstruction",
        workspace,
        oracle,
        run_dir=tmp_path / "run",
        task_id=TASK_ID,
    )

    assert grade.passed is False
    assert grade.failure_kind == VERIFICATION_FAILURE
    assert grade.metrics["transfer_accuracy"] < 1.0
    assert grade.metrics["property_accuracy"] < 1.0


def test_black_box_protocol_noise_and_source_tampering_fail(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is required for grader-hidden verification")
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("black_box_reconstruction", workspace, seed=81)
    solution = workspace / "solution" / "reconstruct.py"
    solution.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    if line.strip():\n"
        "        print('debug')\n"
        "        print(json.dumps({'bucket':'low','score':0,'normalized_units':0,'flags':[]}))\n",
        encoding="utf-8",
    )
    noisy = evaluate_variant(
        "black_box_reconstruction",
        workspace,
        oracle,
        run_dir=tmp_path / "run",
        task_id=TASK_ID,
    )
    assert noisy.passed is False
    assert noisy.metrics["protocol_error_count"] > 0

    contract = workspace / "docs" / "contract.md"
    contract.write_text(contract.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    tampered = evaluate_variant(
        "black_box_reconstruction",
        workspace,
        oracle,
        run_dir=tmp_path / "run2",
        task_id=TASK_ID,
    )
    assert tampered.passed is False
    assert "protected source modified" in tampered.detail
