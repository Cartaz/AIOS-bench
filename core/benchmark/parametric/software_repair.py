"""Seeded software-maintenance task: two independent bugs, hidden behavior checks.

The generator supplies a genuinely broken executable and public tests; the
hidden grader checks behavior, protected fixtures, and executable regressions.
"""
from __future__ import annotations

import hashlib
import json
import random
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ..failures import VERIFICATION_FAILURE
from ..isolated_verifier import run_isolated_python
from .grading import VariantGrade

_BUG_SELECTION = ("positive_only", "skip_zero", "include_pending")
_BUG_THRESHOLD = ("strict_gt", "absolute_value")
_SOURCE = '''"""Ledger summary CLI: one JSON input object per line, one JSON result per line."""
import json
import sys


def summarize(payload):
    count = 0
    net = 0
    for row in payload["records"]:
        if row["status"] != "posted":
            continue
        count += 1
        net += int(row["amount_cents"])
    cutoff = int(payload["cutoff_cents"])
    return {"posted_count": count, "net_cents": net, "at_or_above_cutoff": net >= cutoff}


if __name__ == "__main__":
    for line in sys.stdin:
        if line.strip():
            print(json.dumps(summarize(json.loads(line)), sort_keys=True, separators=(",", ":")))
'''
_PUBLIC_TEST = '''"""Public executable contract tests; these files are benchmark-owned."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LedgerContract(unittest.TestCase):
    def test_public_cases(self):
        cases = [json.loads(line) for line in (ROOT / "examples/public.jsonl").read_text().splitlines()]
        payload = "".join(json.dumps(case["input"]) + "\\n" for case in cases)
        result = subprocess.run([sys.executable, str(ROOT / "src/ledger.py")],
                                input=payload, text=True, capture_output=True, timeout=5,
                                cwd=ROOT, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), len(cases))
        actual = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(actual, [case["output"] for case in cases])


if __name__ == "__main__":
    unittest.main()
'''
_REGRESSION_TEST = '''"""Regression checks for independent selection and cutoff faults."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def invoke(records, cutoff):
    result = subprocess.run([sys.executable, str(ROOT / "src/ledger.py")],
        input=json.dumps({"records": records, "cutoff_cents": cutoff}) + "\\n",
        text=True, capture_output=True, cwd=ROOT, check=False, timeout=5)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class LedgerRegressions(unittest.TestCase):
    def test_signed_zero_and_pending(self):
        rows = [
            {"status": "posted", "amount_cents": -7},
            {"status": "posted", "amount_cents": 0},
            {"status": "posted", "amount_cents": 9},
            {"status": "pending", "amount_cents": 100},
        ]
        self.assertEqual(invoke(rows, 2), {
            "posted_count": 3, "net_cents": 2, "at_or_above_cutoff": True})

    def test_negative_net_is_not_absolute(self):
        self.assertEqual(invoke([{"status": "posted", "amount_cents": -7}], 2), {
            "posted_count": 1, "net_cents": -7, "at_or_above_cutoff": False})


if __name__ == "__main__":
    unittest.main()
'''


@dataclass(frozen=True)
class SoftwareRepairPressure:
    public_cases: int = 16
    hidden_cases: int = 96
    max_rows: int = 20
    distractor_files: int = 3

    def __post_init__(self) -> None:
        if not 4 <= self.public_cases <= 64:
            raise ValueError("public_cases must be 4..64")
        if not 16 <= self.hidden_cases <= 256:
            raise ValueError("hidden_cases must be 16..256")
        if not 4 <= self.max_rows <= 64:
            raise ValueError("max_rows must be 4..64")
        if not 0 <= self.distractor_files <= 16:
            raise ValueError("distractor_files must be 0..16")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SoftwareRepairPressure":
        unknown = set(value) - {"public_cases", "hidden_cases", "max_rows", "distractor_files"}
        if unknown:
            raise ValueError(f"unknown software repair pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _seed(seed: int, label: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{label}".encode()).digest()[:8], "big")


def _write(workspace: Path, path: str, content: str) -> None:
    target = workspace / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def correct_source() -> str:
    return _SOURCE


def _broken_source(selection: str, threshold: str) -> str:
    source = _SOURCE
    if selection == "positive_only":
        source = source.replace('        count += 1\n',
            '        if int(row["amount_cents"]) <= 0:\n            continue\n        count += 1\n')
    elif selection == "skip_zero":
        source = source.replace('        count += 1\n',
            '        if int(row["amount_cents"]) == 0:\n            continue\n        count += 1\n')
    elif selection == "include_pending":
        source = source.replace('row["status"] != "posted"',
                                'row["status"] not in ("posted", "pending")')
    else:
        raise ValueError("unknown selection defect")
    if threshold == "strict_gt":
        source = source.replace('net >= cutoff}', 'net > cutoff}')
    elif threshold == "absolute_value":
        source = source.replace('net >= cutoff}', 'abs(net) >= cutoff}')
    else:
        raise ValueError("unknown cutoff defect")
    return source


def _expected(payload: Mapping[str, Any]) -> dict[str, Any]:
    posted = [row for row in payload["records"] if row["status"] == "posted"]
    net = sum(int(row["amount_cents"]) for row in posted)
    return {"posted_count": len(posted), "net_cents": net,
            "at_or_above_cutoff": net >= int(payload["cutoff_cents"])}


def _cases(seed: int, count: int, max_rows: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    corner = [
        {"records": [{"status": "posted", "amount_cents": -7},
                     {"status": "posted", "amount_cents": 0},
                     {"status": "posted", "amount_cents": 9},
                     {"status": "pending", "amount_cents": 100}], "cutoff_cents": 2},
        {"records": [{"status": "posted", "amount_cents": -13}], "cutoff_cents": 5},
        {"records": [{"status": "posted", "amount_cents": 0}], "cutoff_cents": 0},
        {"records": [{"status": "pending", "amount_cents": 50}], "cutoff_cents": 1},
    ]
    result = list(corner)
    while len(result) < count:
        records = [
            {"status": rng.choice(["posted", "posted", "pending", "void"]),
             "amount_cents": rng.randint(-5000, 5000)}
            for _ in range(rng.randint(1, max_rows))
        ]
        net = sum(row["amount_cents"] for row in records if row["status"] == "posted")
        cutoff = rng.choice([0, net, max(0, net), rng.randint(0, 7000)])
        result.append({"records": records, "cutoff_cents": cutoff})
    return result[:count]


def generate_software_repair_variant(
    workspace: Path, *, seed: int, pressure: SoftwareRepairPressure,
) -> dict[str, Any]:
    rng = random.Random(_seed(seed, "faults"))
    selection = rng.choice(_BUG_SELECTION)
    threshold = rng.choice(_BUG_THRESHOLD)
    original = _broken_source(selection, threshold)
    _write(workspace, "src/ledger.py", original)
    _write(workspace, "tests/test_public.py", _PUBLIC_TEST)
    _write(workspace, "README.md",
        "# Ledger maintenance\n\nRead `docs/contract.md`, reproduce both defects using the public "
        "unittest suite, then repair **only** `src/ledger.py`. Add genuine regression "
        "tests at `tests/test_regression.py`, run the tests, and document the selection "
        "and threshold root causes in `reports/repair.json` with the schema "
        "diagnoses:[{area:selection,cause:...},{area:threshold,cause:...}] "
        "and verification:string. Preserve benchmark-owned documentation, tests, "
        "examples, and archives. Do not hard-code examples; hidden input combinations "
        "are generated independently.\n")
    _write(workspace, "docs/contract.md",
        "# CLI contract\n\nRun `python src/ledger.py`: read one JSON object per nonblank "
        "stdin line and emit exactly one JSON object per line. Input is "
        "{records:[{status:posted|pending|void,amount_cents:int},...],cutoff_cents:int}. "
        "Count every posted row, including zero/negative amounts. Sum signed "
        "amount_cents for posted rows only. Ignore pending and void rows. "
        "at_or_above_cutoff is true iff the signed net is >= cutoff_cents "
        "(inclusive). Output exactly posted_count, net_cents and "
        "at_or_above_cutoff. No commentary on stdout.\n")
    public = _cases(_seed(seed, "public"), pressure.public_cases, pressure.max_rows)
    _write(workspace, "examples/public.jsonl", "".join(
        json.dumps({"input": case, "output": _expected(case)}, sort_keys=True) + "\n"
        for case in public))
    archive = []
    for index in range(pressure.distractor_files):
        relative = f"archive/historical_{index + 1:02d}.md"
        _write(workspace, relative,
               f"# Retired policy revision {rng.randint(100, 999)}\nDo not use: posted-only semantics may have changed.\n")
        archive.append(relative)
    protected = ["README.md", "docs/contract.md", "tests/test_public.py",
                 "examples/public.jsonl", *archive]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "software_repair",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "selection_fault": selection,
        "threshold_fault": threshold,
        "hidden_seed": _seed(seed, "hidden"),
        "source_path": "src/ledger.py",
        "regression_path": "tests/test_regression.py",
        "report_path": "reports/repair.json",
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "protected_sha256": {name: hashlib.sha256((workspace / name).read_bytes()).hexdigest()
                             for name in protected},
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def _valid_report(workspace: Path, oracle: Mapping[str, Any]) -> bool:
    try:
        data = json.loads((workspace / str(oracle["report_path"])).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(data, dict) or set(data) != {"diagnoses", "verification"}:
        return False
    diagnoses = data["diagnoses"]
    if not isinstance(diagnoses, list) or len(diagnoses) != 2:
        return False
    if not all(isinstance(item, dict) and set(item) == {"area", "cause"}
                   and isinstance(item["area"], str)
                   and isinstance(item["cause"], str)
                   and len(item["cause"].strip()) >= 12 for item in diagnoses):
        return False
    return (
        {item["area"] for item in diagnoses} == {"selection", "threshold"}
        and isinstance(data["verification"], str)
        and len(data["verification"].strip()) >= 8
    )


def grade_software_repair_variant(workspace: Path, oracle: Mapping[str, Any]) -> VariantGrade:
    if oracle.get("family") != "software_repair":
        return VariantGrade.binary(False, "software-repair family mismatch")
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping):
        return VariantGrade.binary(False, "software-repair source manifest missing")
    for relative, digest in protected.items():
        path = workspace / str(relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != str(digest):
            return VariantGrade.binary(False, f"protected source modified: {relative}")
    source = workspace / str(oracle.get("source_path", ""))
    regression = workspace / str(oracle.get("regression_path", ""))
    report = workspace / str(oracle.get("report_path", ""))
    if (not source.is_file() or not regression.is_file() or not report.is_file()
            or source.is_symlink() or regression.is_symlink() or report.is_symlink()
            or not _valid_report(workspace, oracle)):
        return VariantGrade.binary(False, "required repaired source, tests or diagnosis missing")
    initial_artifact_digests = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (source, regression, report)
    }
    if initial_artifact_digests[source] == oracle.get("original_sha256"):
        return VariantGrade.binary(False, "original broken implementation is unchanged")
    params = oracle.get("parameters")
    if not isinstance(params, Mapping):
        return VariantGrade.binary(False, "missing repair pressure")
    cases = _cases(int(oracle["hidden_seed"]), int(params["hidden_cases"]),
                   int(params["max_rows"]))
    stdin = "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases)
    code, stdout, stderr, sandboxed = run_isolated_python(
        workspace, ["src/ledger.py"], stdin=stdin, timeout=12)
    try:
        observed = [json.loads(line) for line in stdout.splitlines()]
    except ValueError:
        observed = []
    exact = sum(actual == _expected(case) for actual, case in zip(observed, cases))
    hidden_ok = sandboxed and code == 0 and len(observed) == len(cases) and exact == len(cases)
    test_code, _, tests_stderr, test_sandboxed = run_isolated_python(
        workspace, ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        timeout=12)
    tests_ok = test_sandboxed and test_code == 0
    # Require regression tests to reject the *original* buggy implementation.
    # A no-op test file would pass the fixed version and the mutation alike.
    mutation_detected = False
    if tests_ok and not regression.is_symlink():
        with tempfile.TemporaryDirectory(prefix="aios-bench-repair-mutation-") as directory:
            mutation_workspace = Path(directory) / "workspace"
            for relative in ("tests/test_regression.py", "examples/public.jsonl", "docs/contract.md"):
                original_file = workspace / relative
                destination = mutation_workspace / relative
                if original_file.is_file() and not original_file.is_symlink():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(original_file.read_bytes())
            _write(mutation_workspace, "src/ledger.py", _broken_source(
                str(oracle["selection_fault"]), str(oracle["threshold_fault"])))
            mutation_code, _, _, mutation_sandboxed = run_isolated_python(
                mutation_workspace,
                ["-m", "unittest", "discover", "-s", "tests", "-p", "test_regression.py"],
                timeout=12,
            )
            mutation_detected = mutation_sandboxed and mutation_code == 1
    protected_still_intact = all(
        (workspace / str(relative)).is_file()
        and hashlib.sha256((workspace / str(relative)).read_bytes()).hexdigest() == str(digest)
        for relative, digest in protected.items()
    )
    outputs_still_intact = all(
        path.is_file() and not path.is_symlink()
        and hashlib.sha256(path.read_bytes()).hexdigest() == digest
        for path, digest in initial_artifact_digests.items()
    )
    passed = (hidden_ok and tests_ok and mutation_detected
              and protected_still_intact and outputs_still_intact)
    return VariantGrade(
        passed=passed,
        detail=("software repair hidden behavior and regression tests verified" if passed else
                f"software repair failed: {exact}/{len(cases)} hidden cases, "
                f"program exit={code}, unittest exit={test_code}, "
                f"mutation_detected={mutation_detected}, "
                f"stderr={(stderr or tests_stderr)[-250:]}"),
        score=exact / len(cases) if sandboxed and code == 0 and cases else 0.0,
        metrics={"hidden_exact": exact, "hidden_cases": len(cases),
                 "hidden_sandboxed": sandboxed, "unittest_passed": tests_ok,
                 "regression_mutation_detected": mutation_detected,
                 "sources_still_intact": protected_still_intact and outputs_still_intact},
        failure_kind=None if passed else VERIFICATION_FAILURE,
    )


def materialize_software_repair_golden(workspace: Path, oracle: Mapping[str, Any]) -> None:
    _write(workspace, str(oracle["source_path"]), correct_source())
    _write(workspace, str(oracle["regression_path"]), _REGRESSION_TEST)
    _write(workspace, str(oracle["report_path"]), json.dumps({
        "diagnoses": [
            {"area": "selection", "cause": "Incorrect selection excluded eligible posted rows or included pending rows."},
            {"area": "threshold", "cause": "Incorrect cutoff comparison mishandled inclusivity or signed net values."},
        ],
        "verification": "Public and independent regression suites run successfully.",
    }, indent=2, sort_keys=True) + "\n")


__all__ = ["SoftwareRepairPressure", "generate_software_repair_variant",
           "grade_software_repair_variant", "materialize_software_repair_golden"]
