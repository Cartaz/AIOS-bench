import json
import shutil
from pathlib import Path

from aios_bench.reference_checks_system import check


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "fixtures" / "workspace"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE, workspace)
    (workspace / "reports").mkdir(exist_ok=True)
    return workspace


def test_tool_use_002_rejects_correct_report_if_reference_source_was_edited(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "reports/effective_config.md").write_text(
        "environment: production\n"
        "port: 8081\n"
        "reference chain: README.md -> docs/README.md -> config/app.yaml\n"
        "consumer: tools/run_server.py\n",
        encoding="utf-8",
    )
    (workspace / "config/app.yaml").write_text(
        "port: 8081\nenv: production\n# agent touched this source\n",
        encoding="utf-8",
    )

    passed, detail = check("tool_use_002", workspace, FIXTURE)

    assert passed is False
    assert "source modified" in detail


def test_memory_003_rejects_empty_typescript_placeholder(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / ".agent_memory").mkdir()
    (workspace / ".agent_memory/preferences.json").write_text(
        json.dumps(
            {
                "preference_token": "7K9X2A",
                "primary_language": "TypeScript",
                "previous_primary_language": "Python",
                "tooling_style": "simple",
                "vcs_policy": "no-commit",
            }
        ),
        encoding="utf-8",
    )
    (workspace / "tools/updated_tool.ts").write_text("// placeholder only\n", encoding="utf-8")

    passed, _ = check("memory_003", workspace, FIXTURE)

    assert passed is False


def test_system_oracle_no_longer_contains_stale_category_implementations(tmp_path: Path):
    workspace = _workspace(tmp_path)

    assert check("long_horizon_001", workspace, FIXTURE) is None
    assert check("subagents_001", workspace, FIXTURE) is None
