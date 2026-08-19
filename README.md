# AIOS-bench

Personal benchmark for local AI operating-system agents.

## Goal

AIOS-bench evaluates an agent as a long-lived work system, not only as a coding assistant. The suite measures tool use, knowledge work, memory, learning, coding, autonomy, browser/research work, subagent orchestration, and long-horizon execution.

The benchmark is designed to compare different agent harnesses under the same model, local inference endpoint, workspace, and task set.

## Initial task suite

The v0.1 suite contains 24 task definitions across eight categories:

- tool use
- knowledge work
- memory
- learning
- coding
- autonomy
- browser/research
- subagents
- long-horizon execution

Tasks support `cold` and `warm` modes. Longitudinal evaluation is performed by running related warm tasks across multiple sessions and measuring improvement.

## Observability

AIOS-bench does **not** require or expose private chain-of-thought. Adapters should emit observable execution trajectories instead:

- tool calls
- commands
- file reads/writes
- memory reads/writes
- skill creation or updates
- subagent activity
- errors and retries
- human interventions
- timing and token counts when available

This makes the benchmark useful without treating hidden reasoning traces as a required metric.

## Quick start

```bash
python -m aios_bench.cli list
```

or, after installation:

```bash
aios-bench list
```

## Repository layout

```text
aios_bench/             Core models, task loader, scoring and CLI
benchmarks/tasks/       Versioned benchmark task definitions
benchmarks/schemas/     Machine-readable trajectory schemas
```

## Benchmark philosophy

The primary question is not simply "which agent is smartest?" It is:

> Which agent can perform useful work reliably, proportionally, and with decreasing human supervision as it learns the user's workflow?

The suite therefore tracks both **raw agent performance** and **learning performance** over repeated sessions.
