from __future__ import annotations

import hashlib
import hmac
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolBranchingPressure:
    distractor_tools: int = 3

    def __post_init__(self) -> None:
        if not 2 <= self.distractor_tools <= 5:
            raise ValueError("distractor_tools must be between 2 and 5")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ToolBranchingPressure":
        allowed = {"distractor_tools"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown tool branching pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def receipt(secret: str, observation_id: str, tool: str, value: str) -> str:
    payload = f"{observation_id}:{tool}:{value}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _tool_script(tool: str) -> str:
    return (
        "from __future__ import annotations\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "from urllib.error import HTTPError\n"
        "from urllib.request import Request, urlopen\n\n"
        "ROOT = Path(__file__).parents[1]\n"
        "endpoint = json.loads((ROOT / 'runtime' / 'tool_endpoint.json').read_text(encoding='utf-8'))['base_url']\n"
        f"tool = {tool!r}\n"
        "argument = sys.argv[1] if len(sys.argv) > 1 else ''\n"
        "request = Request(endpoint + '/tool/' + tool, data=json.dumps({'argument': argument}).encode(), headers={'Content-Type': 'application/json'}, method='POST')\n"
        "try:\n"
        "    with urlopen(request, timeout=3) as response:\n"
        "        print(response.read().decode())\n"
        "except HTTPError as exc:\n"
        "    print(exc.read().decode(), file=sys.stderr)\n"
        "    raise SystemExit(2)\n"
    )


def generate_tool_branching_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: ToolBranchingPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "tool_branching"))
    branch = rng.choice(["billing", "access"])
    target_id = f"case-{rng.randint(1000, 9999)}"
    expected_value = str(rng.randint(20, 900)) if branch == "billing" else rng.choice(["editor", "viewer", "admin"])
    observation_id = hashlib.sha256(f"tool-observation:{seed}".encode()).hexdigest()[:24]
    secret = hashlib.sha256(f"tool-secret:{seed}:aios".encode()).hexdigest()

    tools = ["inspect_case", "billing_lookup", "access_lookup"]
    distractor_pool = ["legacy_lookup", "cache_lookup", "system_metrics", "archive_search", "old_directory"]
    distractors = distractor_pool[: pressure.distractor_tools]
    tool_dir = workspace / "tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    for tool in [*tools, *distractors]:
        path = tool_dir / f"{tool}.py"
        path.write_text(_tool_script(tool), encoding="utf-8")

    (workspace / "README.md").write_text(
        "# Case resolver\n\n"
        "Resolve the live case using the smallest relevant tool path. Start by inspecting the case. "
        "Then use the branch-specific lookup with the case id returned by inspection. Several plausible legacy/cache/metrics tools are intentionally present but are not authoritative. "
        "The live tool session rejects broad distractor probing. Save `reports/case_resolution.json` with `case_type`, `case_id`, `value`, `inspection_receipt`, and `lookup_receipt`.\n",
        encoding="utf-8",
    )
    (workspace / "runtime").mkdir(parents=True, exist_ok=True)
    protected = ["README.md", *[f"tools/{name}.py" for name in [*tools, *distractors]]]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "tool_branching",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "branch": branch,
        "target_id": target_id,
        "expected_value": expected_value,
        "observation_id": observation_id,
        "secret": secret,
        "distractor_tools": distractors,
        "protected_sha256": {
            relative: hashlib.sha256((workspace / relative).read_bytes()).hexdigest()
            for relative in sorted(protected)
        },
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def server_payload(oracle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "branch": str(oracle["branch"]),
        "target_id": str(oracle["target_id"]),
        "expected_value": str(oracle["expected_value"]),
        "observation_id": str(oracle["observation_id"]),
        "secret": str(oracle["secret"]),
        "distractor_tools": list(oracle.get("distractor_tools") or []),
    }


def expected_resolution(oracle: Mapping[str, Any]) -> dict[str, str]:
    branch = str(oracle["branch"])
    target = str(oracle["target_id"])
    value = str(oracle["expected_value"])
    observation = str(oracle["observation_id"])
    secret = str(oracle["secret"])
    lookup = f"{branch}_lookup"
    return {
        "case_type": branch,
        "case_id": target,
        "value": value,
        "inspection_receipt": receipt(secret, observation, "inspect_case", target),
        "lookup_receipt": receipt(secret, observation, lookup, value),
    }


def check_tool_branching_variant(workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    try:
        if oracle.get("family") != "tool_branching":
            return False, "tool branching oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected tool digests"
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != str(expected):
                return False, f"benchmark-owned tool modified: {relative}"
        report = workspace / "reports" / "case_resolution.json"
        if not report.is_file():
            return False, "case resolution report missing"
        actual = json.loads(report.read_text(encoding="utf-8"))
        if actual != expected_resolution(oracle):
            return False, "case resolution does not contain the verified branch-specific receipts"
        return True, "branch-specific tool selection and receipts verified"
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return False, f"tool branching parametric oracle error: {type(exc).__name__}: {exc}"
