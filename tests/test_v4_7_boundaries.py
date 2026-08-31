from __future__ import annotations

import json
from pathlib import Path

from aios_bench.frontier_runner import semantic_source_paths
from aios_bench.horizon import HORIZON_CONTEXT_KIND, HorizonProfile, get_horizon_profile
from aios_bench.horizon_execution import execute_horizon_profile
from aios_bench.models import Task
from aios_bench.publication import analysis_implementation_index


ROOT = Path(__file__).resolve().parents[1]


def test_horizon_orchestration_does_not_change_frontier_suite_semantics() -> None:
    names = {path.name for path in semantic_source_paths(ROOT)}
    assert "horizon.py" not in names
    assert "horizon_analysis.py" not in names
    assert "horizon_execution.py" not in names


def test_publication_seal_covers_all_specialized_derived_analyses() -> None:
    sealed = {item["path"] for item in analysis_implementation_index()["files"]}
    assert {
        "ablations.py",
        "cross_artifact_analysis.py",
        "epistemic_analysis.py",
        "horizon.py",
        "horizon_analysis.py",
        "landscapes.py",
        "raw.py",
        "report.py",
        "retrieval_analysis.py",
        "statistics.py",
        "dashboard.py",
        "publication.py",
    } <= sealed


class _ProvenanceRunner:
    def __init__(self, run_dir: Path, family: str, parameters: dict[str, int]) -> None:
        self.run_dir = run_dir
        self.family = family
        self.parameters = parameters
        self.saw_context_before_run = False
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": run_dir.name,
                    "manifest": {
                        "model": {
                            "identity_fingerprint": "model-fp",
                            "strictly_comparable": True,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def run(self, tasks: list[Task]) -> int:
        metadata = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        context = metadata.get("experiment_context")
        self.saw_context_before_run = (
            isinstance(context, dict) and context.get("kind") == HORIZON_CONTEXT_KIND
        )
        task = tasks[0]
        (self.run_dir / "results.jsonl").write_text(
            json.dumps(
                {
                    "task_id": task.id,
                    "variant_family": self.family,
                    "variant_parameters": self.parameters,
                    "variant_digest": "variant-digest",
                    "success": True,
                    "score": 100,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return 0

    def abort(self, tasks: list[Task]) -> None:
        return


def test_single_horizon_run_persists_experiment_context_before_agent_execution(
    tmp_path: Path,
) -> None:
    cell = get_horizon_profile().family_cells("stateful_world")[0]
    profile = HorizonProfile("preannotation-test", (cell,))
    task = Task(id=cell.task_id, category="autonomy", prompt="test")
    created: list[_ProvenanceRunner] = []

    def factory(
        harness: str,
        run_id: str,
        orchestration_seed: int,
        skill_mode: str,
        parameters: dict[str, dict[str, int]],
    ) -> _ProvenanceRunner:
        runner = _ProvenanceRunner(
            tmp_path / run_id,
            cell.family,
            parameters[cell.family],
        )
        created.append(runner)
        return runner

    result = execute_horizon_profile(
        profile,
        tasks={task.id: task},
        harnesses=("piagent",),
        skill_modes=("no_skill",),
        repeats=1,
        base_seed=42,
        experiment_id="exp-horizon",
        runner_factory=factory,
    )

    assert result.exit_code == 0
    assert len(created) == 1
    assert created[0].saw_context_before_run is True
