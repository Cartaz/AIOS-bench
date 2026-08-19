# AIOS-bench

A reproducible benchmark suite for evaluating personal AI-agent systems with local LLMs.

## Goals

AIOS-bench measures more than coding ability. It evaluates tool use, knowledge work, memory, learning, autonomy, error recovery, context efficiency, subagents, and long-horizon execution.

The benchmark is designed around a local OpenAI-compatible model endpoint (for example llama.cpp) so every agent can be tested against the same model and hardware.

## Benchmark philosophy

- **Same model, same fixtures, same tasks.** Agent harnesses are the variable.
- **Trajectory over prose.** We record observable tool/process events, files, memory events, errors, retries, timing and token usage. Private chain-of-thought is not collected.
- **Cold vs warm vs longitudinal.** A good personal agent should improve after repeated work.
- **Correctness before autonomy.** An agent that acts more is not automatically better.
- **Human intervention is a cost.** The benchmark measures how often the user has to rescue the agent.

## Current suite

The v0.1 pilot contains 24 tasks across eight categories:

| Category | Tasks | What it measures |
|---|---:|---|
| tool_use | 3 | filesystem discipline, scoped edits, recovery |
| knowledge | 3 | retrieval, synthesis, evidence handling |
| memory | 3 | recall, update, contamination control |
| learning | 3 | improvement across repeated sessions |
| coding | 3 | small-tool implementation and debugging |
| autonomy | 3 | planning and proportionality |
| browser | 2 | research and structured capture |
| long_horizon | 4 | multi-step execution and recovery |

## Running

Validate and inspect the suite:

```bash
python -m aios_bench.cli list
python -m aios_bench.cli validate
```

Run an adapter:

```bash
python -m aios_bench.cli run --adapter adapters/pi.py --agent pi --run-id pi-qwen-cold
python -m aios_bench.cli score results/pi-qwen-cold.jsonl
```

The runner creates an isolated workspace for every task. `cold` tasks receive fresh agent state; `warm` and `longitudinal` tasks share isolated state within the relevant task family. An adapter receives one task JSON object per invocation and must emit one trajectory JSON object. See `docs/adapter-protocol.md`.

### Pi

Pi supports JSON event output and RPC mode for programmatic integration. Configure Pi to use the same local OpenAI-compatible endpoint used by the other agents, then run:

```bash
set PI_PROVIDER=<your-local-provider>
set PI_MODEL=<your-local-model>
python -m aios_bench.cli run --adapter adapters/pi.py --agent pi --run-id pi-qwen
```

On PowerShell use `$env:PI_PROVIDER=...` and `$env:PI_MODEL=...`.

### Hermes

Hermes supports non-interactive `hermes chat` execution and toolset selection. Configure its provider/model to the same local endpoint, then run:

```bash
set HERMES_PROVIDER=<your-provider>
set HERMES_MODEL=<your-local-model>
set HERMES_TOOLSETS=terminal,file,skills,memory,delegation
python -m aios_bench.cli run --adapter adapters/hermes.py --agent hermes --run-id hermes-qwen
```

The adapter redirects Hermes' HOME/USERPROFILE to the benchmark state directory so benchmark memory cannot contaminate the user's real Hermes profile.

## Benchmark modes

- `cold`: empty agent memory/skills/session state.
- `warm`: persistent isolated state reused by related tasks.
- `longitudinal`: persistent state across repeated related tasks; intended for measuring learning gain.

## Results

Each line in `results/*.jsonl` contains both the raw trajectory and deterministic evaluation. The trajectory schema is intentionally model-agnostic so additional agents can be added without changing the task suite.

## Repository layout

```text
adapters/                 agent-specific adapters
aios_bench/               CLI and benchmark orchestration
benchmark/tasks/          task definitions
benchmark/fixtures/       deterministic input data
benchmark/schemas/        JSON schemas
benchmark/scoring.py      deterministic scoring
docs/                     methodology and adapter protocol
tests/                    benchmark tests
```

## Status

This is an initial research benchmark. Scores should not be treated as universal rankings. The goal is to identify which agent architecture becomes most useful for a personal local AI OS.
