from pathlib import Path

import pytest

from core.benchmark.pristine import PristineArtifactError, artifact_changes, pristine_overlay


def test_pristine_overlay_rebuilds_baseline_then_applies_only_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "a.py").write_text("value = 2\n", encoding="utf-8")
    (workspace / "README.md").write_text("tampered locally\n", encoding="utf-8")
    baseline = {
        "src/a.py": "value = 1\n",
        "README.md": "authoritative baseline\n",
    }

    with pristine_overlay(workspace, baseline, ["src/a.py"]) as (pristine, changes):
        assert (pristine / "src" / "a.py").read_text(encoding="utf-8") == "value = 2\n"
        assert (pristine / "README.md").read_text(encoding="utf-8") == "authoritative baseline\n"
        assert [item["path"] for item in changes] == ["src/a.py"]


def test_deleted_artifact_is_reproduced_as_deleted_in_pristine_copy(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    baseline = {"module.py": "value = 1\n"}

    with pristine_overlay(workspace, baseline, ["module.py"]) as (pristine, changes):
        assert not (pristine / "module.py").exists()
        assert changes[0]["exists"] is False


def test_artifact_changes_rejects_paths_not_owned_by_baseline(tmp_path: Path) -> None:
    with pytest.raises(PristineArtifactError, match="missing from baseline"):
        artifact_changes(tmp_path, {"safe.py": ""}, ["other.py"])
