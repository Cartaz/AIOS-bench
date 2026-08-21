from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .experiments import derive_seed
from .frontier_v3_runner import FrontierV3Runner, SEMANTIC_DIRS as V3_SEMANTIC_DIRS
from .frontier_v3_runner import SEMANTIC_FILES as V3_SEMANTIC_FILES
from .parametric import materialize_variant


SEMANTIC_FILES = tuple(dict.fromkeys((*V3_SEMANTIC_FILES, "frontier_v4_runner.py")))
SEMANTIC_DIRS = tuple(dict.fromkeys((*V3_SEMANTIC_DIRS, "parametric")))


class FrontierV4Runner(FrontierV3Runner):
    """Runner for generated Frontier v4 task families.

    Frontier v3 remains a frozen static baseline. V4 materializes a fresh task
    workspace from an orchestration-derived task seed for every repeat and keeps
    the generated oracle outside the workspace under a sandbox-masked run path.
    """

    def __init__(
        self,
        repo_root,
        agent,
        results_dir,
        task_timeout,
        total_timeout,
        resume=True,
        model="unknown",
        keep_raw=False,
        run_id=None,
        server_metrics_url=None,
        server_metrics_model=None,
        max_output_tokens=65536,
        metrics_poll_interval=1.0,
        variant_base_seed=42,
        parametric_parameters: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        self.variant_base_seed = int(variant_base_seed)
        self.parametric_parameters = {
            str(family): dict(parameters)
            for family, parameters in (parametric_parameters or {}).items()
        }
        self._variants: dict[str, dict[str, Any]] = {}
        if run_id is None:
            run_id = datetime.now().astimezone().strftime(
                "%Y-%m-%d_%H%M%S_%f"
            ) + "_frontier-v4"
        super().__init__(
            repo_root,
            agent,
            results_dir,
            task_timeout,
            total_timeout,
            resume=resume,
            model=model,
            keep_raw=keep_raw,
            run_id=run_id,
            server_metrics_url=server_metrics_url,
            server_metrics_model=server_metrics_model,
            max_output_tokens=max_output_tokens,
            metrics_poll_interval=metrics_poll_interval,
        )

    def _suite_name(self):
        return "frontier_v4"

    def _execution_manifest(self):
        manifest = super()._execution_manifest()
        manifest["parametric"] = {
            "schema": "aios-bench/parametric/v1",
            "suite": "frontier_v4",
            "pressure_coordinates": self.parametric_parameters,
            # The observation seed is intentionally not part of the execution
            # fingerprint. It is recorded on each result row instead.
            "seeded_variants": True,
        }
        return manifest

    def _revision(self):
        digest = hashlib.sha256()
        catalog = self.repo_root / "benchmarks" / "tasks" / "frontier_v4"
        for path in sorted(
            item for item in catalog.rglob("*")
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
        ):
            digest.update(path.relative_to(self.repo_root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        for name in SEMANTIC_FILES:
            path = self.repo_root / "aios_bench" / name
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        for directory in SEMANTIC_DIRS:
            root = self.repo_root / "aios_bench" / directory
            for path in sorted(
                item for item in root.rglob("*.py") if "__pycache__" not in item.parts
            ):
                digest.update(path.relative_to(self.repo_root).as_posix().encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _catalog_task_count(self):
        task_ids: list[str] = []
        for path in sorted((self.repo_root / "benchmarks" / "tasks" / "frontier_v4").glob("*.json")):
            task_ids.extend(
                str(item["id"])
                for item in json.loads(path.read_text(encoding="utf-8"))
            )
        return task_ids

    @staticmethod
    def _family(task) -> str:
        checks = [
            check for check in task.acceptance
            if check.get("type") == "parametric_reference"
        ]
        if len(checks) != 1:
            raise ValueError(f"Frontier v4 task {task.id} needs one parametric_reference")
        return str(checks[0]["family"])

    def _task_seed(self, task) -> int:
        return derive_seed(self.variant_base_seed, "task", task.id)

    def _workspace(self, task):
        path = self.run_dir / "workspaces" / task.id
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        family = self._family(task)
        oracle = materialize_variant(
            family,
            path,
            seed=self._task_seed(task),
            parameters=self.parametric_parameters.get(family, {}),
        )
        oracle_dir = self.run_dir / "oracles"
        oracle_dir.mkdir(parents=True, exist_ok=True)
        oracle_path = oracle_dir / f"{task.id}.json"
        temporary = oracle_path.with_name(f".{oracle_path.name}.tmp")
        temporary.write_text(
            json.dumps(oracle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(oracle_path)
        self._variants[task.id] = oracle
        return path

    def _result_identity(self, task):
        identity = super()._result_identity(task)
        family = self._family(task)
        variant = self._variants.get(task.id) or {}
        identity.update({
            "variant_schema": "aios-bench/parametric/v1",
            "variant_family": family,
            "variant_seed": self._task_seed(task),
            "variant_parameters": dict(self.parametric_parameters.get(family, {})),
            "variant_digest": variant.get("variant_digest"),
        })
        return identity
