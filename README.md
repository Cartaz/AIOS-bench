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

Run an entire harness suite sequentially:

```bash
aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL
aiosbench --piagent --model Qwen3.6-35B-Q4_K_XL
aiosbench --opencode --model Qwen3.6-35B-Q4_K_XL
```

Equivalent explicit form:

```bash
aiosbench run --hermes --model Qwen3.6-35B-Q4_K_XL
```

The runner executes every task in deterministic order, creates an isolated workspace for each task, records execution output, applies available acceptance checks, stores resumable results, and regenerates the comparison dashboard.

Use `--no-resume` to intentionally repeat every task:

```bash
aiosbench --hermes --model Qwen3.6-35B-Q4_K_XL --no-resume
```

## Harness adapters

The adapter layer keeps harness-specific invocation separate from the benchmark itself. Current native adapters are:

- **Hermes Agent** — `hermes chat -q`, with optional `--model`.
- **Pi Agent** — `pi -p`, with optional `--model`.
- **OpenCode** — `opencode run`, using the isolated workspace via `--dir`, JSON output, and optional `--model`.

These invocation forms follow the harness CLIs rather than assuming that every agent accepts the same arguments. Hermes documents non-interactive `hermes chat -q`, Pi documents `pi -p`, and OpenCode documents `opencode run` with `--dir`, `--model`, and `--format json`. citeturn0search0turn0search9turn0search2

Goose, Letta, and Agent Zero currently have generic adapter slots. They will receive dedicated adapters once their headless invocation and event formats are pinned down.

## Dashboard

Every run updates:

```text
results/dashboard.html
```

Results are grouped by **harness + model**, so historical runs remain comparable:

```text
Hermes + Model A  →  Hermes + Model B  →  Hermes + Model C
Pi + Model A      →  Pi + Model B      →  Pi + Model C
```

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

AIOS-bench does **not** require or expose private chain-of-thought. Adapters should capture observable execution data instead:

- tool calls
- commands
- file reads/writes
- memory reads/writes
- skill creation or updates
- subagent activity
- errors and retries
- human interventions
- timing and token counts when available

## Repository layout

```text
aios_bench/             Core models, adapters, runner, scoring and dashboard
benchmarks/tasks/       Versioned benchmark task definitions and acceptance specs
benchmarks/fixtures/    Deterministic isolated workspaces
benchmarks/schemas/     Machine-readable trajectory schemas
results/                Local benchmark runs and generated dashboard
```

## Benchmark philosophy

The primary question is not simply "which agent is smartest?" It is:

> Which agent can perform useful work reliably, proportionally, and with decreasing human supervision as it learns the user's workflow?

Model identity is a first-class dimension so harness improvements and model improvements can be separated over time.
