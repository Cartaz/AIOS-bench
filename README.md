# AIOS-bench

Reproducible benchmark suite for local AI operating-system agents.

## Install and run

The runtime package has no test-framework dependency. Install the development
extra when working on the benchmark itself:

```bash
python -m pip install -e .
python -m pip install -e '.[dev]'  # contributors and CI
```

```bash
aiosbench --piagent --model Qwen --no-resume
```

Or run every configured harness sequentially:

```bash
aiosbench --all --model Qwen
```

The runner executes the active frontier v3 catalog in deterministic order, creates an isolated workspace for each task, preserves explicit warm-state chains for memory and learning tasks, records observable execution data, applies deterministic reference checks, stores resumable results, and regenerates the comparison dashboard.

## Deterministic evaluation

AIOS-bench uses **deterministic evaluators as the authoritative benchmark signal**. There is no LLM judge. A task passes only when the agent execution and its required artifacts satisfy reproducible acceptance checks.

Frontier v3 replaces weak "file exists + keyword" acceptance with benchmark-owned reference oracles for the tasks where content matters. These checks can validate exact evidence provenance, alternate datasets, hidden regression tests, negative constraints, dependency chains, persistent memory state, and delegation telemetry without asking another model to grade the result.

Run checkpoints are resumable only when the full benchmark semantics match: the
catalog, deterministic fixture inputs, and reference-oracle implementation are
fingerprinted together. A fixture or oracle update therefore starts affected
work again rather than silently mixing incomparable scores.

Comparable task score is `80% deterministic acceptance + 20% successful
execution`. A failed task is capped at 49/100, so partial artifacts cannot look
like a passing result. Telemetry-derived efficiency and recovery metrics remain
diagnostic fields rather than cross-harness score inputs. Tasks recorded as
`unsupported` or dependency-`blocked` have no score.

## Results layout

Raw benchmark runs are local data. They live under `results/.local/` using one
canonical layout:

```text
results/
  README.md
  summary.json
  dashboard.html
  .local/
    <harness>/
      <model>/
        latest.txt and, where supported, latest -> runs/<run-id>
        runs/
          <run-id>/
            run.json
            results.jsonl
            logs/
            workspaces/
```

`.local/` is ignored by Git. The repository publishes only the regenerated
aggregate `summary.json` and `dashboard.html`; a `run.json` remains beside its
local run for audit and reproducibility. See [run lifecycle and
comparability](docs/RUNS_AND_RESULTS.md) and the [artifact retention
policy](docs/ARTIFACT_RETENTION.md).

```bash
aiosbench dashboard  # local diagnostic view under results/.local/
aiosbench publish    # reviewed aggregate snapshot under results/
```

## Frontier v3

The active catalog is `benchmarks/tasks/frontier_v3/*.json` and contains **28 tasks** split by capability. The category files are loaded in lexical order, giving a stable execution order.

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** synthesis, recovery, validation, transfer, or grounded research.
- **Tier 5 — Frontier:** combines difficult capabilities with negative constraints, hidden checks, state persistence, or independent verification.

The v3 fixtures deliberately include alternate datasets, malformed inputs, distractors, conflicting procedures, schema shifts, persistent-state chains, and hidden regression tests. The benchmark-owned reference checks live in `aios_bench/reference_checks_*.py` and never invoke an LLM.

The long-horizon workspace is materialized per run with a deterministic corpus
larger than 50 KiB, a late authoritative release gate, and a stateful validator
that fails reproducibly on its third execution. Its oracle checks the grounded
release-gate citation, recorded recovery, untouched validator, and checkpoints.

Subagent tasks count only normalized `subagent_start` events from the harness;
mentions of delegation in a report or stdout do not count as evidence of a
delegated run. Harnesses without compatible structured delegation telemetry
are recorded as `unsupported`, with no score, and excluded from comparable
aggregates rather than treated as failures.
