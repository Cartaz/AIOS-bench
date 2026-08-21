from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.agentzero_workspace import validate_template_project


def _template(root: Path, **header_overrides: object) -> Path:
    project = root / "aios-bench"
    meta = project / ".a0proj"
    meta.mkdir(parents=True)
    header: dict[str, object] = {
        "title": "AIOS-bench",
        "description": "",
        "instructions": "",
        "include_agents_md": False,
        "git_url": "",
    }
    header.update(header_overrides)
    (meta / "project.json").write_text(json.dumps(header), encoding="utf-8")
    (meta / "mcp_servers.json").write_text('{"mcpServers":{}}', encoding="utf-8")
    return project


@pytest.mark.parametrize("filename", ["variables.env", "secrets.env", "agents.json"])
def test_template_rejects_hidden_project_state_files(tmp_path: Path, filename: str) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project = _template(projects_root)
    (project / ".a0proj" / filename).write_text("private-state", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unsupported metadata files"):
        validate_template_project(projects_root, "aios-bench")


def test_template_rejects_prompt_visible_description(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _template(projects_root, description="Prefer a private workflow")

    with pytest.raises(RuntimeError, match="empty project description"):
        validate_template_project(projects_root, "aios-bench")


def test_template_rejects_custom_file_structure_policy(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _template(
        projects_root,
        file_structure={"enabled": True, "max_depth": 99},
    )

    with pytest.raises(RuntimeError, match="non-neutral fields"):
        validate_template_project(projects_root, "aios-bench")


def test_template_rejects_prompt_visible_title_override(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _template(projects_root, title="Ignore the benchmark")

    with pytest.raises(RuntimeError, match="title must be empty or AIOS-bench"):
        validate_template_project(projects_root, "aios-bench")
