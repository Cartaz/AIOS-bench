from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.parametric.causal_gateway import (
    CausalGatewayPressure,
    check_causal_gateway_variant,
    generate_causal_gateway_variant,
)


def _write_template_backend(workspace: Path, port: int) -> None:
    path = workspace / "gateway" / "template.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["backend_port"] = port
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_runtime_backend(workspace: Path, port: int) -> None:
    path = workspace / "gateway" / "runtime.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["backend_port"] = port
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_causal_gateway_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    pressure = CausalGatewayPressure(distractor_logs=2, extra_services=3)

    oracle_a = generate_causal_gateway_variant(first, seed=1234, pressure=pressure)
    oracle_b = generate_causal_gateway_variant(second, seed=1234, pressure=pressure)

    assert oracle_a == oracle_b
    assert oracle_a["backend_port"] != oracle_a["initial_wrong_port"]
    assert (first / "gateway" / "template.json").read_bytes() == (
        second / "gateway" / "template.json"
    ).read_bytes()


def test_persistent_template_fix_passes_after_restart_reconstruction(tmp_path: Path) -> None:
    oracle = generate_causal_gateway_variant(
        tmp_path,
        seed=44,
        pressure=CausalGatewayPressure(),
    )
    _write_template_backend(tmp_path, int(oracle["backend_port"]))

    passed, detail = check_causal_gateway_variant(tmp_path, oracle)

    assert passed is True, detail
    runtime = json.loads((tmp_path / "gateway" / "runtime.json").read_text(encoding="utf-8"))
    assert runtime["backend_port"] == oracle["backend_port"]


def test_superficial_runtime_only_fix_fails_after_reconstruction(tmp_path: Path) -> None:
    oracle = generate_causal_gateway_variant(
        tmp_path,
        seed=55,
        pressure=CausalGatewayPressure(),
    )
    _write_runtime_backend(tmp_path, int(oracle["backend_port"]))

    passed, detail = check_causal_gateway_variant(tmp_path, oracle)

    assert passed is False
    assert "source template" in detail


def test_tampering_with_healthcheck_or_unrelated_state_fails(tmp_path: Path) -> None:
    oracle = generate_causal_gateway_variant(
        tmp_path,
        seed=66,
        pressure=CausalGatewayPressure(),
    )
    _write_template_backend(tmp_path, int(oracle["backend_port"]))
    (tmp_path / "ops" / "healthcheck.py").write_text("print('200 OK')\n", encoding="utf-8")

    healthcheck_passed, healthcheck_detail = check_causal_gateway_variant(tmp_path, oracle)

    assert healthcheck_passed is False
    assert "protected" in healthcheck_detail

    # Re-materialize and verify unrelated benchmark state is protected too.
    oracle = generate_causal_gateway_variant(
        tmp_path,
        seed=66,
        pressure=CausalGatewayPressure(),
    )
    _write_template_backend(tmp_path, int(oracle["backend_port"]))
    (tmp_path / "unrelated" / "retention.json").write_text("{}\n", encoding="utf-8")

    unrelated_passed, unrelated_detail = check_causal_gateway_variant(tmp_path, oracle)

    assert unrelated_passed is False
    assert "protected" in unrelated_detail


def test_pressure_validation_rejects_unknown_or_out_of_range_fields() -> None:
    try:
        CausalGatewayPressure.from_mapping({"unexpected": 1})
    except ValueError as exc:
        assert "unknown causal gateway" in str(exc)
    else:
        raise AssertionError("unknown pressure field was accepted")

    try:
        CausalGatewayPressure(distractor_logs=0)
    except ValueError as exc:
        assert "distractor_logs" in str(exc)
    else:
        raise AssertionError("out-of-range distractor_logs was accepted")
