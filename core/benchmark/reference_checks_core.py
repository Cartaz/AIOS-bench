from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias


CheckResult: TypeAlias = tuple[bool, str] | None


def read(workspace: Path, relative_path: str | Path) -> str:
    return (workspace / relative_path).read_text(encoding="utf-8", errors="replace")


def load(workspace: Path, relative_path: str | Path) -> Any:
    return json.loads(read(workspace, relative_path))


def eval_path(workspace: Path, name: str) -> Path:
    """Return a workspace-local oracle path, isolated across harness runs."""
    root = workspace / ".aios-bench-eval"
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def run(
    workspace: Path,
    args: Sequence[str],
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    argv = list(args)
    if argv and argv[0] in {"python", "python3"}:
        argv[0] = sys.executable
    return subprocess.run(
        argv,
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def same(workspace: Path, relative_path: str | Path, fixture_root: Path) -> bool:
    actual = workspace / relative_path
    expected = fixture_root / relative_path
    return (
        actual.is_file()
        and expected.is_file()
        and hashlib.sha256(actual.read_bytes()).digest()
        == hashlib.sha256(expected.read_bytes()).digest()
    )


def ok(value: object, message: str) -> tuple[bool, str]:
    return bool(value), message
