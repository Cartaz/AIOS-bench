from pathlib import Path

from aios_bench.parametric import ConfigTraversalPressure, check_variant, materialize_variant


def _write_valid_report(workspace: Path, oracle: dict) -> None:
    lines = ["# Effective configuration", ""]
    for key, value in oracle["settings"].items():
        lines.append(f"{key}: {value}")
    lines.extend([
        "",
        "reference chain: " + " -> ".join(oracle["reference_chain"]),
        f"consumer: {oracle['consumer_path']}",
    ])
    (workspace / "reports/effective_config.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def test_config_traversal_variant_is_deterministic(tmp_path: Path) -> None:
    pressure = ConfigTraversalPressure(chain_depth=5, distractor_files=4, extra_settings=3)
    a = tmp_path / "a"
    b = tmp_path / "b"
    oracle_a = materialize_variant(
        "config_traversal", a, seed=1234, parameters=pressure.to_dict()
    )
    oracle_b = materialize_variant(
        "config_traversal", b, seed=1234, parameters=pressure.to_dict()
    )

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["protected_sha256"] == oracle_b["protected_sha256"]
    assert oracle_a["reference_chain"] == oracle_b["reference_chain"]


def test_config_traversal_changes_with_seed_or_pressure(tmp_path: Path) -> None:
    baseline = materialize_variant("config_traversal", tmp_path / "a", seed=7)
    other_seed = materialize_variant("config_traversal", tmp_path / "b", seed=8)
    other_pressure = materialize_variant(
        "config_traversal",
        tmp_path / "c",
        seed=7,
        parameters={"chain_depth": 5, "distractor_files": 2, "extra_settings": 1},
    )

    assert baseline["variant_digest"] != other_seed["variant_digest"]
    assert baseline["variant_digest"] != other_pressure["variant_digest"]


def test_config_traversal_accepts_grounded_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant(
        "config_traversal",
        workspace,
        seed=42,
        parameters={"chain_depth": 4, "distractor_files": 3, "extra_settings": 2},
    )
    _write_valid_report(workspace, oracle)

    passed, detail = check_variant("config_traversal", workspace, oracle)

    assert passed is True, detail


def test_config_traversal_rejects_decoy_port(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant(
        "config_traversal",
        workspace,
        seed=99,
        parameters={"chain_depth": 3, "distractor_files": 2, "extra_settings": 0},
    )
    _write_valid_report(workspace, oracle)
    report = workspace / "reports/effective_config.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        f"port: {oracle['settings']['port']}",
        f"port: {oracle['decoy_ports'][0]}",
    )
    report.write_text(text, encoding="utf-8")

    passed, _ = check_variant("config_traversal", workspace, oracle)

    assert passed is False


def test_config_traversal_rejects_source_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("config_traversal", workspace, seed=31337)
    _write_valid_report(workspace, oracle)
    source = workspace / oracle["config_path"]
    source.write_text(source.read_text(encoding="utf-8") + "tampered: true\n", encoding="utf-8")

    passed, detail = check_variant("config_traversal", workspace, oracle)

    assert passed is False
    assert "protected source modified" in detail


def test_config_traversal_rejects_incomplete_reference_chain(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant(
        "config_traversal", workspace, seed=8080, parameters={"chain_depth": 5}
    )
    _write_valid_report(workspace, oracle)
    report = workspace / "reports/effective_config.md"
    missing = oracle["reference_chain"][2]
    report.write_text(
        report.read_text(encoding="utf-8").replace(f" -> {missing}", ""),
        encoding="utf-8",
    )

    passed, _ = check_variant("config_traversal", workspace, oracle)

    assert passed is False
