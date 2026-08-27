from __future__ import annotations

import hashlib
import os
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


def collect_submitted_tree(
    workspace: Path,
    relative_root: str,
    *,
    max_files: int = 64,
    max_total_bytes: int = 512 * 1024,
) -> list[dict[str, str | int]]:
    """Collect a bounded agent-created tree without following links or caches."""
    if max_files < 1 or max_total_bytes < 1:
        raise ValueError("submitted-tree limits must be positive")
    relative = _relative_path(relative_root)
    source_root = _workspace_file(workspace, relative)
    if not source_root.is_dir():
        raise PristineArtifactError(f"submitted tree missing: {relative.as_posix()}")

    ignored_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
    files: list[dict[str, str | int]] = []
    total_bytes = 0
    for current, dirs, names in os.walk(source_root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_dirs: list[str] = []
        for name in dirs:
            candidate = current_path / name
            if name in ignored_dirs:
                continue
            if candidate.is_symlink():
                raise PristineArtifactError(
                    f"submitted tree contains symlink directory: {candidate.relative_to(source_root).as_posix()}"
                )
            safe_dirs.append(name)
        dirs[:] = safe_dirs

        for name in sorted(names):
            candidate = current_path / name
            if candidate.is_symlink():
                raise PristineArtifactError(
                    f"submitted tree contains symlink file: {candidate.relative_to(source_root).as_posix()}"
                )
            if not candidate.is_file():
                raise PristineArtifactError(
                    f"submitted tree contains non-file entry: {candidate.relative_to(source_root).as_posix()}"
                )
            relative_file = candidate.relative_to(source_root).as_posix()
            data = candidate.read_bytes()
            total_bytes += len(data)
            files.append({
                "path": relative_file,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
            if len(files) > max_files:
                raise PristineArtifactError(f"submitted tree exceeds {max_files} files")
            if total_bytes > max_total_bytes:
                raise PristineArtifactError(
                    f"submitted tree exceeds {max_total_bytes} bytes"
                )
    return sorted(files, key=lambda item: str(item["path"]))


@contextmanager
def pristine_submitted_tree(
    workspace: Path,
    relative_root: str,
    *,
    max_files: int = 64,
    max_total_bytes: int = 512 * 1024,
) -> Iterator[tuple[Path, list[dict[str, str | int]]]]:
    """Copy only a bounded new submission tree into a fresh verifier directory."""
    relative = _relative_path(relative_root)
    source_root = _workspace_file(workspace, relative)
    manifest = collect_submitted_tree(
        workspace,
        relative.as_posix(),
        max_files=max_files,
        max_total_bytes=max_total_bytes,
    )
    with tempfile.TemporaryDirectory(prefix="aios-bench-submission-") as temporary:
        destination_root = Path(temporary)
        for item in manifest:
            relative_file = _relative_path(str(item["path"]))
            source = source_root.joinpath(*relative_file.parts)
            destination = destination_root.joinpath(*relative_file.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        yield destination_root, manifest


__all__ = [
    "PristineArtifactError",
    "artifact_changes",
    "collect_submitted_tree",
    "pristine_overlay",
    "pristine_submitted_tree",
]
