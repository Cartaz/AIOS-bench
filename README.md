# AIOS-bench

Reproducible benchmark suite for local AI operating-system agents.

## Running

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

## Results layout

Benchmark results live under `results/` using one canonical layout:

```text
results/
  <harness>/
    <model>/
      latest.txt or latest -> runs/<run-id>
      runs/
        <run-id>/
          run.json
          results.jsonl
          logs/
          workspaces/
```

Historical runs use the same structure. Older benchmark data has been normalized into this layout rather than being kept in separately named `first_*` and `second_*` directories.

## Frontier v3

The active catalog is `benchmarks/tasks/frontier_v3/*.json` and contains **28 tasks** split by capability. The category files are loaded in lexical order, giving a stable execution order.

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** synthesis, recovery, validation, transfer, or grounded research.
- **Tier 5 — Frontier:** combines difficult capabilities with negative constraints, hidden checks, state persistence, or independent verification.

The v3 fixtures deliberately include alternate datasets, malformed inputs, distractors, conflicting procedures, schema shifts, persistent-state chains, and hidden regression tests. The benchmark-owned reference checks live in `aios_bench/reference_checks_*.py` and never invoke an LLM.
