# AIOS-bench

A reproducible benchmark suite for evaluating personal AI-agent systems with local LLMs.

## Goals

AIOS-bench measures more than coding ability. It evaluates tool use, knowledge work, memory, learning, autonomy, error recovery, context efficiency, subagents, and long-horizon execution.

The benchmark is designed around a local OpenAI-compatible model endpoint (for example llama.cpp) so every agent can be tested against the same model and hardware.

## Benchmark philosophy

- **Same model, same fixtures, same tasks.** Agent harnesses are the variable.
- **Trajectory over prose.** We record tool calls, files, memory events, errors, retries, timing and token usage. Private chain-of-thought is not collected.
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

The CLI is intentionally adapter-agnostic:

```bash
python -m aios_bench.cli list
python -m aios_bench.cli validate
python -m aios_bench.cli run --adapter ./adapters/my-agent.py --suite pilot --run-id hermes-cold
python -m aios_bench.cli score results/hermes-cold.jsonl
```

An adapter receives one task JSON object per invocation and must emit one trajectory JSON object. See `docs/adapter-protocol.md`.

## Benchmark modes

- `cold`: empty agent memory/skills.
- `warm`: a pre-seeded memory/skills directory.
- `longitudinal`: repeated tasks over multiple sessions; learning gain is scored from run 1 against later runs.

## Repository layout

```text
benchmark/tasks/          task definitions
benchmark/fixtures/       deterministic input data
benchmark/schemas/        JSON schemas
benchmark/                runner and scoring library
docs/                     methodology and adapter protocol
```

## Status

This is an initial research benchmark. Scores should not be treated as universal rankings. The goal is to identify which agent architecture becomes most useful for a personal local AI OS.
