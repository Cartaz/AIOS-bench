# AIOS-bench

Personal benchmark for local AI operating-system agents.

## Goal

AIOS-bench evaluates an agent as a long-lived work system, not only as a coding assistant. The suite measures tool use, knowledge work, memory, learning, coding, autonomy, browser/research work, subagent orchestration, and long-horizon execution.

The benchmark is designed to compare different agent harnesses under the same model, local inference endpoint, workspace, and task set.

## One-command benchmark runs

Install the package in the benchmark environment:

```bash
pip install -e .
```

Then run an entire harness suite sequentially:

```bash
aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL
aiosbench --piagent --model Qwen3.6-35B-Q4_K_XL
aiosbench --opencode --model Qwen3.6-35B-Q4_K_XL
```

The equivalent explicit form is:

```bash
aiosbench run --hermes --model Qwen3.6-35B-Q4_K_XL
```

The runner executes every task in deterministic order, creates an isolated workspace for each task, records the execution trajectory, applies available deterministic acceptance checks, stores resumable results, and regenerates the comparison dashboard.

Use `--no-resume` to intentionally repeat every task:

```bash
aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL --no-resume
```

## Dashboard

Every run updates:

```text
results/dashboard.html
```

The dashboard groups results by **harness + model**, so the same harness can be tested repeatedly with progressively stronger models without overwriting historical results. This is the basis for longitudinal comparisons such as:

```text
Hermes + Model A  →  Hermes + Model B  →  Hermes + Model C
Pi + Model A      →  Pi + Model B      →  Pi + Model C
```

## Current harnesses

The CLI has adapters/configuration slots for:

- Hermes Agent
- Pi Agent
- OpenCode
- Goose
- Letta
- Agent Zero

The commands are deliberately centralized in the runner so their invocation can later be replaced by dedicated adapters without changing the benchmark or scoring layer.

## Current task suite

The v0.1 suite contains task definitions across nine categories:

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

## Repository layout

```text
aios_bench/             Core models, task loader, runner, scoring and dashboard
benchmarks/tasks/       Versioned benchmark task definitions and acceptance specs
benchmarks/fixtures/    Deterministic isolated workspaces
benchmarks/schemas/     Machine-readable trajectory schemas
results/                Local benchmark runs and generated dashboard
```

## Benchmark philosophy

The primary question is not simply "which agent is smartest?" It is:

> Which agent can perform useful work reliably, proportionally, and with decreasing human supervision as it learns the user's workflow?

The suite therefore tracks both **raw agent performance** and **learning performance** over repeated sessions. Model identity is a first-class dimension so harness improvements and model improvements can be separated over time.
