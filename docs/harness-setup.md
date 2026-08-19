# Harness setup for AIOS-bench

The benchmark intentionally does not hide harness-specific setup behind magic flags. Configure each harness once, then run the common benchmark command.

## Hermes

Install Hermes and configure the local OpenAI-compatible endpoint/model. AIOS-bench invokes `hermes chat --quiet -q` and can override the model per run.

```bash
aiosbench --hermes --model <provider/model>
```

Hermes supports custom OpenAI-compatible endpoints including llama.cpp servers, so a local model can be benchmarked without changing the benchmark adapter.

## Pi Agent

Install the Pi coding agent. AIOS-bench uses JSON event mode for machine-readable execution telemetry.

```bash
aiosbench --piagent --model <provider/model>
```

For richer integration later, the adapter can switch from JSONL subprocess mode to Pi RPC without changing the benchmark task/evaluator layer.

## OpenCode

Install OpenCode. AIOS-bench uses `opencode run --dir <workspace> --format json --auto` so the fixture directory and event stream are explicit.

```bash
aiosbench --opencode --model <provider/model>
```

OpenCode's `serve` API is reserved for a future persistent-server adapter.

## Goose

Install Goose and configure its provider. AIOS-bench uses non-session `goose run` by default so each cold benchmark task starts cleanly.

```bash
set AIOS_BENCH_GOOSE_PROVIDER=openai
aiosbench --goose --model <model>
```

For local providers, configure Goose's normal provider settings first. Recipes/extensions should be pinned in a later benchmark profile rather than implicitly inherited from a developer's personal configuration.

## Letta Code

Install Letta Code and configure an agent. Letta's headless `-p` path is used by the adapter. For longitudinal benchmarks, set a stable agent ID:

```bash
set AIOS_BENCH_LETTA_AGENT=<agent-id>
aiosbench --letta --model <model>
```

Model selection is deliberately not converted into an invented CLI flag; Letta configures model/provider at the agent level. The benchmark records the requested model as metadata, but the actual agent configuration must be verified before comparing runs.

## Agent Zero

Agent Zero is integrated through its documented external HTTP API, not by scraping its Web UI. Start a local Agent Zero instance and create a dedicated benchmark project/workspace that maps to the benchmark fixture.

```bash
set AIOS_BENCH_AGENTZERO_URL=http://127.0.0.1:80
set AIOS_BENCH_AGENTZERO_API_KEY=<api-key>
set AIOS_BENCH_AGENTZERO_PROJECT=aios-bench
aiosbench --agentzero --model <model>
```

The project must be configured so Agent Zero can operate on the isolated fixture. Do not point it at the real personal workspace during benchmark runs.

## Capability policy

Missing telemetry is recorded as `unavailable`, not as zero. This matters because Hermes, Pi, OpenCode, Goose, Letta and Agent Zero expose different native observability surfaces. Correctness remains based on the common deterministic evaluator whenever possible.

For the `subagents` category specifically, a successful result requires the
harness integration to emit normalized `subagent_start` events. Plain-text
claims in the final answer or logs are intentionally not accepted as delegation
evidence. Treat a harness that cannot expose these events as unsupported for
that category when making cross-harness comparisons.
