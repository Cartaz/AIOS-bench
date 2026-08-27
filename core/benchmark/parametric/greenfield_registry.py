from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..pristine import PristineArtifactError, pristine_submitted_tree
from ..pristine_verifier import run_pristine_verifier


@dataclass(frozen=True)
class GreenfieldRegistryPressure:
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GreenfieldRegistryPressure":
        if value:
            raise ValueError(f"greenfield registry has no pressure coordinates: {sorted(value)}")
        return cls()

    def to_dict(self) -> dict[str, int]:
        return {}


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _semantic_coordinates(seed: int) -> tuple[int, str]:
    digest = hashlib.sha256(f"greenfield-registry:{int(seed)}".encode()).digest()
    max_name_length = (32, 48, 64, 80)[digest[0] % 4]
    storage_name = ("registry.json", "entries.json", "records.json", "store.json")[digest[1] % 4]
    return max_name_length, storage_name


def generate_greenfield_registry_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: GreenfieldRegistryPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    max_name_length, storage_name = _semantic_coordinates(seed)
    specification = (
        "# Greenfield persistent registry\n\n"
        "Build the implementation from scratch under `submission/`. No source starter is provided.\n\n"
        "The submission must expose `Registry` from `registry_app` so that "
        "`from registry_app import Registry` works. `Registry(storage_path)` accepts a string or Path. "
        "Names are normalized with surrounding whitespace removed and Unicode-aware lowercase "
        "(`casefold`). Empty names and names longer than "
        f"{max_name_length} characters after normalization must raise `ValueError`. Values must be "
        "non-empty strings after trimming, otherwise raise `ValueError`.\n\n"
        "The public methods are:\n"
        "- `add(name, value) -> dict`: persist a new entry and return exactly "
        "`{\"name\": normalized_name, \"value\": trimmed_value}`; duplicate normalized names raise `ValueError`.\n"
        "- `get(name) -> dict | None`: return the persisted entry or `None`.\n"
        "- `list_entries() -> list[dict]`: return all entries sorted by normalized name.\n"
        "- `remove(name) -> bool`: persist deletion and report whether an entry existed.\n\n"
        "Persistence must survive constructing a new `Registry` instance against the same storage path. "
        "Malformed existing storage must raise `ValueError` rather than being silently discarded. "
        f"Use `{storage_name}` as the example storage filename in any local checks you create. "
        "Do not depend on third-party packages. The benchmark will verify only the submitted tree from "
        "a fresh directory, so workspace-local test tampering or files outside `submission/` cannot satisfy verification.\n"
    )
    (workspace / "README.md").write_text(specification, encoding="utf-8")

    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "greenfield_registry",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "submission_root": "submission",
        "max_name_length": max_name_length,
        "storage_name": storage_name,
        "readme_sha256": hashlib.sha256((workspace / "README.md").read_bytes()).hexdigest(),
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def _hidden_verifier(oracle: Mapping[str, Any]) -> str:
    max_name_length = int(oracle["max_name_length"])
    storage_name = str(oracle["storage_name"])
    return f'''\\
from pathlib import Path\nfrom registry_app import Registry\n\nroot = Path.cwd()\nstorage = root / {storage_name!r}\nregistry = Registry(storage)\nassert registry.list_entries() == []\nassert registry.add("  Alpha  ", "  first  ") == {{"name": "alpha", "value": "first"}}\nassert registry.add("BETA", "second") == {{"name": "beta", "value": "second"}}\nassert registry.get(" ALPHA ") == {{"name": "alpha", "value": "first"}}\nassert registry.list_entries() == [\n    {{"name": "alpha", "value": "first"}},\n    {{"name": "beta", "value": "second"}},\n]\ntry:\n    registry.add("alpha", "duplicate")\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError("duplicate normalized name accepted")\nfor bad_name in ("", "   ", "x" * ({max_name_length} + 1)):\n    try:\n        registry.add(bad_name, "value")\n    except ValueError:\n        pass\n    else:\n        raise AssertionError("invalid name accepted")\nfor bad_value in ("", "   ", 7, None):\n    try:\n        registry.add("value-check", bad_value)\n    except ValueError:\n        pass\n    else:\n        raise AssertionError("invalid value accepted")\nassert registry.remove(" BETA ") is True\nassert registry.remove("beta") is False\nreopened = Registry(storage)\nassert reopened.get("alpha") == {{"name": "alpha", "value": "first"}}\nassert reopened.get("beta") is None\nassert reopened.list_entries() == [{{"name": "alpha", "value": "first"}}]\nstorage.write_text("not-json", encoding="utf-8")\ntry:\n    Registry(storage)\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError("malformed persisted storage was silently accepted")\nprint("greenfield registry verification passed")\n'''


def evaluate_greenfield_registry_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        if oracle.get("family") != "greenfield_registry":
            return {"passed": False, "detail": "greenfield registry oracle family mismatch"}
        readme = workspace / "README.md"
        if not readme.is_file() or hashlib.sha256(readme.read_bytes()).hexdigest() != str(oracle.get("readme_sha256")):
            return {"passed": False, "detail": "benchmark specification modified"}

        with pristine_submitted_tree(
            workspace,
            str(oracle.get("submission_root", "submission")),
            max_files=32,
            max_total_bytes=256 * 1024,
        ) as (pristine, manifest):
            execution = run_pristine_verifier(pristine, _hidden_verifier(oracle), timeout=8)
        passed = execution.returncode == 0
        detail = (execution.stdout + "\n" + execution.stderr).strip()[-2000:]
        return {
            "passed": passed,
            "detail": detail or f"greenfield verifier exited {execution.returncode}",
            "metrics": {
                "schema": "aios-bench/greenfield-verification/v2",
                "submitted_file_count": len(manifest),
                "submitted_bytes": sum(int(item["size"]) for item in manifest),
                "verifier_returncode": execution.returncode,
                "greenfield_verification_passed": passed,
                "verifier_isolation_strategy": execution.isolation_strategy,
                "verifier_filesystem_confined": execution.filesystem_confined,
                "verifier_network_confined": execution.network_confined,
            },
        }
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        PristineArtifactError,
        subprocess.TimeoutExpired,
    ) as exc:
        return {
            "passed": False,
            "detail": f"greenfield registry verifier error: {type(exc).__name__}: {exc}",
        }


def check_greenfield_registry_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    result = evaluate_greenfield_registry_variant(workspace, oracle)
    return bool(result["passed"]), str(result.get("detail", ""))


__all__ = [
    "GreenfieldRegistryPressure",
    "check_greenfield_registry_variant",
    "evaluate_greenfield_registry_variant",
    "generate_greenfield_registry_variant",
]
