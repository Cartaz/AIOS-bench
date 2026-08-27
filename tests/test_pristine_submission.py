from __future__ import annotations

from pathlib import Path

import pytest

from core.benchmark.pristine import (
    PristineArtifactError,
    collect_submitted_tree,
    pristine_submitted_tree,
)


def test_pristine_submission_copies_only_declared_tree_and_ignores_caches(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    submission = workspace / "submission"
    package = submission / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = package / "__pycache__"
    cache.mkdir()
    (cache / "junk.pyc").write_bytes(b"cache")
    (workspace / "outside.txt").write_text("not submitted\n", encoding="utf-8")

    with pristine_submitted_tree(workspace, "submission") as (pristine, manifest):
        assert [item["path"] for item in manifest] == ["pkg/__init__.py"]
        assert (pristine / "pkg" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 1\n"
        assert not (pristine / "outside.txt").exists()
        assert not (pristine / "pkg" / "__pycache__").exists()


def test_pristine_submission_rejects_symlink_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    submission = workspace / "submission"
    submission.mkdir(parents=True)
    target = workspace / "secret.txt"
    target.write_text("secret\n", encoding="utf-8")
    (submission / "linked.txt").symlink_to(target)

    with pytest.raises(PristineArtifactError, match="symlink file"):
        collect_submitted_tree(workspace, "submission")


def test_pristine_submission_enforces_file_and_byte_limits(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    submission = workspace / "submission"
    submission.mkdir(parents=True)
    (submission / "a.txt").write_text("1234", encoding="utf-8")
    (submission / "b.txt").write_text("5678", encoding="utf-8")

    with pytest.raises(PristineArtifactError, match="exceeds 1 files"):
        collect_submitted_tree(workspace, "submission", max_files=1)
    with pytest.raises(PristineArtifactError, match="exceeds 4 bytes"):
        collect_submitted_tree(workspace, "submission", max_total_bytes=4)
