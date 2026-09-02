from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Mapping

from .paths import REPO_ROOT


PROJECT_VENV = REPO_ROOT / ".venv"
PROJECT_BIN = PROJECT_VENV / "bin"


def _project_candidate(name: str) -> Path | None:
    if not name or "/" in name or "\\" in name:
        return None
    candidate = PROJECT_BIN / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def resolve_executable(name: str) -> str | None:
    """Prefer an AIOS-Bench project-local executable over ambient PATH."""
    candidate = _project_candidate(name)
    if candidate is not None:
        return str(candidate)
    return shutil.which(name)


def with_project_bin(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a child environment with ``.venv/bin`` first on PATH.

    Callers may pass a deliberately restricted environment. In that case we
    preserve exactly those keys and only synthesize PATH from the parent when it
    was omitted, avoiding accidental leakage of unrelated process state.
    """
    result = dict(os.environ if environment is None else environment)
    inherited_path = result.get("PATH", os.environ.get("PATH", ""))
    project = str(PROJECT_BIN)
    parts = [part for part in inherited_path.split(os.pathsep) if part and part != project]
    result["PATH"] = os.pathsep.join([project, *parts])
    return result


def npm_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the project-local npm installation environment."""
    result = with_project_bin(environment)
    result["NPM_CONFIG_PREFIX"] = str(PROJECT_VENV)
    return result
