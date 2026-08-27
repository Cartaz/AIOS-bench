from __future__ import annotations

import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator, Mapping, Sequence


class PristineArtifactError(ValueError):
    pass


def _relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise PristineArtifactError(f"unsafe artifact path: {value!r}")
    return path


def _workspace_file(workspace: Path, relative: PurePosixPath) -> Path:
    root = workspace.resolve()
    path = workspace.joinpath(*relative.parts)
    if path.is_symlink():
        raise PristineArtifactError(f"artifact path is a symlink: {relative.as_posix()}")
    resolved = path.resolve()
    if root not in resolved.parents and resolved != root:
        raise PristineArtifactError(f"artifact path escapes workspace: {relative.as_posix()}")
    return path


def artifact_changes(
    workspace: Path,
    baseline_files: Mapping[str, str],
    artifact_paths: Sequence[str],
) -> list[dict[str, str | bool | None]]:
    """Describe source artifacts relative to a benchmark-owned text baseline."""
    changes: list[dict[str, str | bool | None]] = []
    for raw in artifact_paths:
        relative = _relative_path(raw)
        key = relative.as_posix()
        if key not in baseline_files:
            raise PristineArtifactError(f"artifact path missing from baseline: {key}")
        source = _workspace_file(workspace, relative)
        baseline = str(baseline_files[key]).encode("utf-8")
        if source.is_file():
            current = source.read_bytes()
            exists = True
            digest = hashlib.sha256(current).hexdigest()
        elif source.exists():
            raise PristineArtifactError(f"artifact path is not a regular file: {key}")
        else:
            current = b""
            exists = False
            digest = None
        baseline_digest = hashlib.sha256(baseline).hexdigest()
        if not exists or current != baseline:
            changes.append({
                "path": key,
                "exists": exists,
                "sha256": digest,
                "baseline_sha256": baseline_digest,
            })
    return changes


@contextmanager
def pristine_overlay(
    workspace: Path,
    baseline_files: Mapping[str, str],
    artifact_paths: Sequence[str],
) -> Iterator[tuple[Path, list[dict[str, str | bool | None]]]]:
    """Rebuild baseline in a fresh directory and overlay only submitted artifacts."""
    normalized_baseline: dict[str, str] = {}
    for raw, content in baseline_files.items():
        relative = _relative_path(raw)
        normalized_baseline[relative.as_posix()] = str(content)

    changes = artifact_changes(workspace, normalized_baseline, artifact_paths)
    with tempfile.TemporaryDirectory(prefix="aios-bench-pristine-") as temporary:
        root = Path(temporary)
        for raw, content in normalized_baseline.items():
            relative = _relative_path(raw)
            destination = root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        for raw in artifact_paths:
            relative = _relative_path(raw)
            source = _workspace_file(workspace, relative)
            destination = root.joinpath(*relative.parts)
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            else:
                destination.unlink(missing_ok=True)
        yield root, changes


__all__ = [
    "PristineArtifactError",
    "artifact_changes",
    "pristine_overlay",
]
