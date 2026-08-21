from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


PROJECT_META_DIR = ".a0proj"
_PROJECT_HEADER = "project.json"
_MCP_FILE = "mcp_servers.json"
_FORBIDDEN_CUSTOMIZATION_DIRS = frozenset({"instructions", "knowledge", "skills", "agents"})
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_-]+")


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise RuntimeError("Agent Zero workspace bridge does not accept symlink roots")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("Agent Zero workspace bridge does not accept symlinks")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RuntimeError("Agent Zero project template may not contain symlinks")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0D\0" if path.is_dir() else b"\0F\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def validate_template_project(projects_root: Path, template_name: str) -> tuple[Path, str]:
    """Validate a metadata-only Agent Zero project template.

    The template supplies only Agent Zero's project configuration. Benchmark task
    files are copied into a newly-created sibling project for each attempt.
    """
    root = projects_root.expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT must be an existing directory")
    if not template_name or Path(template_name).name != template_name or template_name in {".", ".."}:
        raise RuntimeError("AIOS_BENCH_AGENTZERO_PROJECT must be a simple project name")

    template = (root / template_name).resolve()
    try:
        template.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Agent Zero template project escapes projects root") from exc
    if not template.is_dir():
        raise RuntimeError("Agent Zero template project was not found under projects root")

    _reject_symlinks(template)
    non_meta = [child.name for child in template.iterdir() if child.name != PROJECT_META_DIR]
    if non_meta:
        raise RuntimeError("Agent Zero template project must contain metadata only")

    meta = template / PROJECT_META_DIR
    if not meta.is_dir():
        raise RuntimeError("Agent Zero template project is missing .a0proj metadata")

    header_path = meta / _PROJECT_HEADER
    if not header_path.is_file():
        raise RuntimeError("Agent Zero template project is missing project.json")
    try:
        header = json.loads(header_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Agent Zero template project.json is invalid") from exc
    if not isinstance(header, dict):
        raise RuntimeError("Agent Zero template project.json must be an object")
    if str(header.get("instructions") or "").strip():
        raise RuntimeError("Agent Zero benchmark template must have empty project instructions")
    if header.get("include_agents_md", True) is not False:
        raise RuntimeError("Agent Zero benchmark template must set include_agents_md=false")
    if str(header.get("git_url") or "").strip():
        raise RuntimeError("Agent Zero benchmark template must not bind a git repository")

    mcp_path = meta / _MCP_FILE
    if mcp_path.is_file():
        try:
            mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Agent Zero benchmark mcp_servers.json is invalid") from exc
        servers = mcp.get("mcpServers") if isinstance(mcp, dict) else None
        if servers not in ({}, None):
            raise RuntimeError("Agent Zero benchmark template must not configure MCP servers")

    for dirname in _FORBIDDEN_CUSTOMIZATION_DIRS:
        candidate = meta / dirname
        if candidate.is_dir() and any(path.is_file() for path in candidate.rglob("*")):
            raise RuntimeError(
                f"Agent Zero benchmark template must not contain custom {dirname} files"
            )

    return template, _tree_digest(meta)


def template_project_digest(projects_root: str | None, template_name: str | None) -> str | None:
    if not projects_root or not template_name:
        return None
    try:
        _, digest = validate_template_project(Path(projects_root), template_name)
    except RuntimeError:
        return None
    return digest


def _copy_contents(source: Path, destination: Path, *, exclude_meta: bool = False) -> None:
    _reject_symlinks(source)
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if exclude_meta and child.name == PROJECT_META_DIR:
            continue
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, symlinks=False)
        elif child.is_file():
            shutil.copy2(child, target)
        else:
            raise RuntimeError("Unsupported filesystem object in Agent Zero workspace bridge")


def _clear_contents(root: Path, *, preserve_meta: bool = False) -> None:
    if not root.is_dir():
        return
    for child in root.iterdir():
        if preserve_meta and child.name == PROJECT_META_DIR:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            raise RuntimeError("Unsupported filesystem object in Agent Zero project")


def _ephemeral_name(template_name: str) -> str:
    task = _SAFE_COMPONENT.sub("-", os.environ.get("AIOS_BENCH_TASK_ID", "task")).strip("-_")
    task = task[:36] or "task"
    base = _SAFE_COMPONENT.sub("-", template_name).strip("-_")[:32] or "aios-bench"
    return f"{base}-{task}-{uuid.uuid4().hex[:10]}"


@dataclass
class EphemeralAgentZeroProject:
    workspace: Path
    projects_root: Path
    template_name: str
    project_name: str | None = None
    project_path: Path | None = None
    template_digest: str | None = None

    def prepare(self) -> str:
        workspace = self.workspace.resolve()
        if not workspace.is_dir():
            raise RuntimeError("AIOS_BENCH_WORKSPACE must be an existing directory")
        _reject_symlinks(workspace)

        template, digest = validate_template_project(self.projects_root, self.template_name)
        root = self.projects_root.expanduser().resolve()
        name = _ephemeral_name(self.template_name)
        target = root / name
        if target.exists():
            raise RuntimeError("Agent Zero ephemeral project collision")

        target.mkdir()
        shutil.copytree(template / PROJECT_META_DIR, target / PROJECT_META_DIR)
        _copy_contents(workspace, target)
        self.project_name = name
        self.project_path = target
        self.template_digest = digest
        return name

    def sync_back(self) -> None:
        if self.project_path is None or not self.project_path.is_dir():
            raise RuntimeError("Agent Zero ephemeral project is unavailable")
        # Validate the remote result before altering the authoritative local
        # workspace. A symlink could otherwise escape deterministic graders.
        _reject_symlinks(self.project_path)
        workspace = self.workspace.resolve()
        _clear_contents(workspace)
        _copy_contents(self.project_path, workspace, exclude_meta=True)

    def cleanup(self) -> None:
        if self.project_path is None:
            return
        root = self.projects_root.expanduser().resolve()
        target = self.project_path.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return
        if target.name == self.template_name:
            return
        shutil.rmtree(target, ignore_errors=True)
