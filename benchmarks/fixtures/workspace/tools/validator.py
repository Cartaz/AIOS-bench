"""Stateful validator used by the long-horizon recovery task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(state_path: Path | None = None) -> bool:
    state_path = state_path or Path(".state/validator_runs.json")
    state = {"runs": 0, "history": []}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    run_number = int(state.get("runs", 0)) + 1
    state["runs"] = run_number
    record = {"run": run_number, "status": "passed"}
    if run_number == 3:
        record = {"run": run_number, "status": "failed", "error": "validator state corruption"}
    state.setdefault("history", []).append(record)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return record["status"] == "passed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".state/validator_runs.json")
    args = parser.parse_args()
    if validate(Path(args.state)):
        print("validator: passed")
        return 0
    print("validator: validator state corruption", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
