# AIOS-bench

Reproducible benchmark suite for local AI operating-system agents.

## Running

Select a configured harness and model:

```bash
aiosbench --piagent --model Qwen --no-resume
```

Or run every configured harness sequentially:

```bash
aiosbench --all --model Qwen
```

The runner executes the calibrated frontier catalog in deterministic order, creates an isolated workspace for each task, records observable execution data, applies deterministic artifact checks, stores resumable results, and regenerates the comparison dashboard.

## Deterministic evaluation

AIOS-bench deliberately uses **deterministic evaluators as the authoritative benchmark signal**. A task passes only when the agent execution and its required artifacts satisfy the configured acceptance checks. The final score is computed from reproducible telemetry and acceptance results; no LLM is asked to grade another LLM.

This keeps benchmark runs reproducible, debuggable, and comparable across models and harnesses.

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

`results/dashboard.html` and `results/summary.json` are generated from the run data.

## Frontier task calibration

The active catalog is `benchmarks/tasks/frontier_v2.json` and contains **28 tasks**. Every task is intentionally Tier 3, 4, or 5:

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** requires synthesis, recovery, validation, or transfer across steps.
- **Tier 5 — Frontier:** combines multiple difficult capabilities, negative constraints, ambiguity, or independent verification.
