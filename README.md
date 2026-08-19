# AIOS-bench

Personal benchmark for local AI operating-system agents.

## Goal

AIOS-bench evaluates an agent as a long-lived work system, not only as a coding assistant. The suite measures tool use, knowledge work, memory, learning, coding, autonomy, browser/research work, subagent orchestration, and long-horizon execution.

The benchmark compares harnesses under the same model, local inference endpoint, workspace, and task set.

## One-command benchmark runs

Install the package:

```bash
pip install -e .
```

Run one harness at a time:

```bash
aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL
aiosbench --piagent --model Qwen3.6-35B-Q4_K_XL
aiosbench --opencode --model Qwen3.6-35B-Q4_K_XL
```

Or run every configured harness sequentially with `--all`.

The runner executes the calibrated frontier catalog in deterministic order, creates an isolated workspace for each task, records observable execution data, applies weighted deterministic acceptance checks, stores resumable results, and regenerates the comparison dashboard.

## Frontier task calibration

The active catalog is `benchmarks/tasks/frontier_v2.json` and contains **28 tasks**. Every task is intentionally Tier 3, 4, or 5:

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** requires synthesis, recovery, validation, or transfer across steps.
- **Tier 5 — Frontier:** combines multiple difficult capabilities, negative constraints, ambiguity, or independent verification.

There are no Tier 1/2 tasks in the active suite. The goal is discrimination among capable agent/model combinations, not measuring whether an agent can perform trivial tool calls.

The target calibration is qualitative rather than a hard quota: the current local model should encounter meaningful failures in T4/T5 while still solving a useful portion of T3. A future stronger model should have room to improve without the benchmark saturating near 100.

### Context-window policy

Long-horizon tasks are designed around the practical **98k-token context ceiling**. They do not require an arbitrarily large prompt. Instead, they test whether an agent can maintain state through long execution using compaction, durable notes, files, or other harness-native mechanisms when available.

A task that exceeds the available context because the harness cannot manage its own state is a meaningful failure; simply making prompts enormous is not the objective.

## Scoring

A task is not considered successful merely because the harness exits with code 0. The benchmark evaluates the resulting workspace with weighted deterministic checks such as required artifacts, required content, JSON validity, regex constraints, test commands, protected-input integrity, and minimum evidence/detail requirements.

Acceptance contributes 60% of the task score. Execution success, recovery, human independence, and proportionality provide the remaining signal. This makes partial completion visible and prevents a plausible but incorrect report from receiving a near-perfect score.

Task definitions carry an explicit revision number. Changing a task invalidates stale resumable results for that task.

## Dashboard

Every run updates `results/dashboard.html`. Results are grouped by **harness + model** and include capability and Tier 3/4/5 breakdowns, allowing longitudinal comparison as models improve.

## Observability

AIOS-bench does **not** require or expose private chain-of-thought. Adapters capture observable execution data instead: tool calls, commands, file reads/writes, memory activity, skill creation, subagent activity, errors/retries, human interventions, timing, and token counts when available.

## Repository layout

```text
aios_bench/             Core models, adapters, runner, scoring and dashboard
benchmarks/tasks/       Active frontier catalog plus legacy task definitions
benchmarks/fixtures/    Deterministic isolated workspaces
benchmarks/schemas/     Machine-readable trajectory schemas
results/                Local benchmark runs and generated dashboard
```

## Benchmark philosophy

The primary question is not simply "which agent is smartest?" It is:

> Which agent can perform useful work reliably, proportionally, and with decreasing human supervision as it learns the user's workflow?

Model identity is a first-class dimension so harness improvements and model improvements can be separated over time.
