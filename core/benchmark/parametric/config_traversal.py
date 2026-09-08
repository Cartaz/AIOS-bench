from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ConfigTraversalPressure:
    """Workload coordinates for indirect configuration discovery."""

    chain_depth: int = 3
    distractor_files: int = 3
    extra_settings: int = 2

    def __post_init__(self) -> None:
        if not 2 <= self.chain_depth <= 6:
            raise ValueError("chain_depth must be between 2 and 6")
        if not 0 <= self.distractor_files <= 16:
            raise ValueError("distractor_files must be between 0 and 16")
        if not 0 <= self.extra_settings <= 6:
            raise ValueError("extra_settings must be between 0 and 6")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ConfigTraversalPressure":
        allowed = {"chain_depth", "distractor_files", "extra_settings"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown config traversal pressure fields: {sorted(unknown)}")
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


_ASSIGNMENT_LINE = re.compile(
    r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*(?P<value>.+?)\s*$"
)
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _strip_inline_markup(value: str) -> str:
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for marker in ("**", "__", "`", "*", "_"):
            if (
                len(text) >= 2 * len(marker)
                and text.startswith(marker)
                and text.endswith(marker)
            ):
                text = text[len(marker) : -len(marker)].strip()
                changed = True
    return text


def _markdown_cells(line: str) -> list[str] | None:
    text = line.strip()
    if "|" not in text:
        return None
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells = [_strip_inline_markup(cell) for cell in text.split("|")]
    return cells if len(cells) >= 2 else None


def parse_effective_config_report(text: str) -> dict[str, tuple[str, ...]]:
    """Extract candidate settings without coupling grading to one Markdown style."""
    settings: dict[str, list[str]] = {}
    for raw_line in text.splitlines():
        assignment = _ASSIGNMENT_LINE.fullmatch(raw_line)
        if assignment is not None:
            key = assignment.group("key")
            value = _strip_inline_markup(assignment.group("value"))
            settings.setdefault(key, []).append(value)
            continue

        cells = _markdown_cells(raw_line)
        if not cells:
            continue
        if all(_TABLE_SEPARATOR_CELL.fullmatch(cell or "") for cell in cells):
            continue
        key, value = cells[0], cells[1]
        if (
            key.casefold() in {"setting", "key", "name"}
            and value.casefold() in {"value", "effective value", "effective_value"}
        ):
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
            settings.setdefault(key, []).append(value)
    return {key: tuple(values) for key, values in settings.items()}


def setting_matches(actual: object, expected: object) -> bool:
    if isinstance(actual, str):
        values = (actual,)
    elif isinstance(actual, tuple) and all(isinstance(value, str) for value in actual):
        values = actual
    else:
        return False
    normalized = {value.casefold() for value in values}
    return normalized == {str(expected).casefold()}


def generate_config_traversal_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: ConfigTraversalPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "config"))

    port = rng.randint(4100, 9800)
    environments = ["production", "staging", "canary"]
    environment = rng.choice(environments)
    workers = rng.randint(2, 12)

    settings: dict[str, str | int] = {
        "port": port,
        "environment": environment,
        "workers": workers,
    }
    optional_pool = [
        ("request_timeout_ms", lambda: rng.randrange(1000, 9001, 250)),
        ("max_connections", lambda: rng.randrange(50, 501, 25)),
        ("log_level", lambda: rng.choice(["info", "warning", "error"])),
        ("cache_ttl_s", lambda: rng.randrange(30, 601, 30)),
        ("batch_limit", lambda: rng.randrange(8, 129, 8)),
        ("retry_limit", lambda: rng.randint(1, 7)),
    ]
    rng.shuffle(optional_pool)
    for key, factory in optional_pool[: pressure.extra_settings]:
        settings[key] = factory()

    chain: list[str] = ["README.md"]
    for index in range(pressure.chain_depth - 1):
        chain.append(f"docs/reference_{index + 1}.md")
    config_path = "config/runtime.yaml"
    chain.append(config_path)
    consumer_path = "tools/run_service.py"

    for index, relative in enumerate(chain[:-1]):
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        target = chain[index + 1]
        path.write_text(
            f"# Runtime reference {index + 1}\n\n"
            f"For the effective runtime configuration, follow `{target}`.\n",
            encoding="utf-8",
        )

    config = workspace / config_path
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "\n".join(f"{key}: {value}" for key, value in settings.items()) + "\n",
        encoding="utf-8",
    )

    consumer = workspace / consumer_path
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_text(
        "from pathlib import Path\n"
        "import yaml\n\n"
        "CONFIG = Path(__file__).parents[1] / 'config' / 'runtime.yaml'\n\n"
        "def effective_config():\n"
        "    return yaml.safe_load(CONFIG.read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )

    distractors: list[str] = []
    decoy_ports: list[int] = []
    for index in range(pressure.distractor_files):
        decoy_port = rng.randint(1000, 3999)
        decoy_ports.append(decoy_port)
        path = workspace / "archive" / f"runtime_{index + 1:02d}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"port: {decoy_port}\nenvironment: legacy\nworkers: 1\n",
            encoding="utf-8",
        )
        distractors.append(path.relative_to(workspace).as_posix())

    protected = [*chain, consumer_path, *distractors]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "config_traversal",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "reference_chain": chain,
        "config_path": config_path,
        "consumer_path": consumer_path,
        "settings": settings,
        "decoy_ports": decoy_ports,
        "protected_sha256": {
            relative: _sha256(workspace / relative) for relative in sorted(protected)
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def check_config_traversal_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    try:
        if oracle.get("family") != "config_traversal":
            return False, "config traversal oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return False, f"protected source modified: {relative}"

        report = workspace / "reports" / "effective_config.md"
        if not report.is_file():
            return False, "effective configuration report missing"
        text = report.read_text(encoding="utf-8", errors="replace")

        settings = oracle.get("settings")
        chain = oracle.get("reference_chain")
        consumer = str(oracle.get("consumer_path", ""))
        if not isinstance(settings, Mapping) or not isinstance(chain, list):
            return False, "invalid config traversal oracle"

        reported_settings = parse_effective_config_report(text)
        for key, value in settings.items():
            if not setting_matches(reported_settings.get(str(key)), value):
                return False, f"effective setting missing or incorrect: {key}"

        position = -1
        for relative in chain:
            next_position = text.find(str(relative), position + 1)
            if next_position < 0:
                return False, f"reference chain missing: {relative}"
            position = next_position
        if consumer not in text:
            return False, "consumer path missing from report"

        for decoy_port in oracle.get("decoy_ports") or []:
            port_values = reported_settings.get("port", ())
            if isinstance(port_values, tuple) and str(decoy_port).casefold() in {
                value.casefold() for value in port_values
            }:
                return False, "report selected a distractor configuration"

        return True, "generated config traversal and source integrity verified"
    except (OSError, TypeError, ValueError) as exc:
        return False, f"config traversal parametric oracle error: {type(exc).__name__}: {exc}"
