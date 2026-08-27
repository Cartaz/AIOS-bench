from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CausalGatewayPressure:
    """Workload coordinates for the causal gateway persistence pilot."""

    distractor_logs: int = 2
    extra_services: int = 2

    def __post_init__(self) -> None:
        if not 1 <= self.distractor_logs <= 8:
            raise ValueError("distractor_logs must be between 1 and 8")
        if not 0 <= self.extra_services <= 8:
            raise ValueError("extra_services must be between 0 and 8")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CausalGatewayPressure":
        allowed = {"distractor_logs", "extra_services"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown causal gateway pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_causal_gateway_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: CausalGatewayPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "causal_gateway"))

    backend_port = rng.randint(12000, 24000)
    wrong_port = backend_port
    while wrong_port == backend_port:
        wrong_port = rng.randint(24001, 36000)
    gateway_port = rng.randint(4000, 9000)

    registry: dict[str, Any] = {
        "gateway": {"port": gateway_port, "state": "running"},
        "backend": {"port": backend_port, "state": "running"},
    }
    for index in range(pressure.extra_services):
        registry[f"worker_{index + 1}"] = {
            "port": rng.randint(36001, 52000),
            "state": "running",
        }

    template_path = workspace / "gateway" / "template.json"
    runtime_path = workspace / "gateway" / "runtime.json"
    registry_path = workspace / "services" / "registry.json"
    _write_json(template_path, {"listen_port": gateway_port, "backend_port": wrong_port})
    shutil.copyfile(template_path, runtime_path)
    _write_json(registry_path, registry)

    healthcheck_path = workspace / "ops" / "healthcheck.py"
    healthcheck_path.parent.mkdir(parents=True, exist_ok=True)
    healthcheck_path.write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "from pathlib import Path\n\n"
        "ROOT = Path(__file__).parents[1]\n\n"
        "def load(path):\n"
        "    return json.loads(path.read_text(encoding='utf-8'))\n\n"
        "runtime = load(ROOT / 'gateway' / 'runtime.json')\n"
        "registry = load(ROOT / 'services' / 'registry.json')\n"
        "expected = int(registry['backend']['port'])\n"
        "configured = int(runtime['backend_port'])\n"
        "if configured == expected:\n"
        "    print(f'200 OK backend={configured}')\n"
        "    raise SystemExit(0)\n"
        "print(f'502 Bad Gateway connection refused backend={configured}')\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )

    restart_path = workspace / "ops" / "restart_gateway.py"
    restart_path.write_text(
        "from pathlib import Path\n"
        "import shutil\n\n"
        "ROOT = Path(__file__).parents[1]\n"
        "shutil.copyfile(ROOT / 'gateway' / 'template.json', ROOT / 'gateway' / 'runtime.json')\n"
        "print('gateway runtime regenerated from gateway/template.json')\n",
        encoding="utf-8",
    )

    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    gateway_log = logs_dir / "gateway.log"
    gateway_log.write_text(
        f"ERROR upstream connect failed: 127.0.0.1:{wrong_port} connection refused\n"
        f"INFO gateway listener healthy on 127.0.0.1:{gateway_port}\n",
        encoding="utf-8",
    )
    decoys: list[str] = []
    decoy_messages = [
        "ERROR historical worker OOM; resolved after restart\n",
        "WARN cache reached 92 percent; eviction completed\n",
        "ERROR old TLS handshake failure; certificate already rotated\n",
        "WARN archived database latency spike; recovered\n",
    ]
    for index in range(pressure.distractor_logs):
        path = logs_dir / f"historical_{index + 1:02d}.log"
        path.write_text(decoy_messages[index % len(decoy_messages)], encoding="utf-8")
        decoys.append(path.relative_to(workspace).as_posix())

    unrelated_path = workspace / "unrelated" / "retention.json"
    _write_json(unrelated_path, {"days": 30, "rotate": True})
    readme_path = workspace / "README.md"
    readme_path.write_text(
        "# Gateway incident sandbox\n\n"
        "The production-style health probe is `python ops/healthcheck.py`.\n"
        "Gateway restarts regenerate runtime configuration. Use `python ops/restart_gateway.py` "
        "to reproduce that lifecycle locally. Diagnose the current 502 before editing.\n",
        encoding="utf-8",
    )

    protected_paths = [
        "README.md",
        "ops/healthcheck.py",
        "ops/restart_gateway.py",
        "services/registry.json",
        "logs/gateway.log",
        "unrelated/retention.json",
        *decoys,
    ]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "causal_gateway",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "template_path": template_path.relative_to(workspace).as_posix(),
        "runtime_path": runtime_path.relative_to(workspace).as_posix(),
        "backend_port": backend_port,
        "initial_wrong_port": wrong_port,
        "protected_sha256": {
            relative: _sha256(workspace / relative) for relative in sorted(protected_paths)
        },
        "decoy_paths": decoys,
        "unrelated_path": unrelated_path.relative_to(workspace).as_posix(),
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def check_causal_gateway_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    """Verify a persistent root-cause repair after deterministic reconstruction."""
    try:
        if oracle.get("family") != "causal_gateway":
            return False, "causal gateway oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return False, f"protected or unrelated state modified: {relative}"

        template_path = workspace / str(oracle["template_path"])
        runtime_path = workspace / str(oracle["runtime_path"])
        if not template_path.is_file():
            return False, "gateway source template missing"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        expected_port = int(oracle["backend_port"])
        if int(template.get("backend_port", -1)) != expected_port:
            return False, "source template still targets the wrong backend"

        # Reconstruct runtime state ourselves instead of trusting an agent-edited
        # generated file or restart helper. A symptom-only runtime edit therefore
        # disappears exactly as it would on the next service restart.
        shutil.copyfile(template_path, runtime_path)
        healthcheck = workspace / "ops" / "healthcheck.py"
        completed = subprocess.run(
            [sys.executable, str(healthcheck)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0 or "200 OK" not in output:
            return False, "gateway remains unhealthy after deterministic restart reconstruction"

        regenerated = json.loads(runtime_path.read_text(encoding="utf-8"))
        if int(regenerated.get("backend_port", -1)) != expected_port:
            return False, "regenerated runtime does not preserve the repaired backend target"
        return True, "persistent gateway root-cause repair verified after restart reconstruction"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        return False, f"causal gateway parametric oracle error: {type(exc).__name__}: {exc}"
