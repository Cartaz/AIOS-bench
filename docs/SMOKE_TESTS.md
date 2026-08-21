# Harness smoke tests

Use the smoke profile after installing/configuring a harness and before spending
hours on a full Frontier campaign. Smoke runs execute the real harness, real
workspace isolation and the normal deterministic Frontier v3 graders; they are
not mocked validation.

Smoke output is deliberately stored under `results/.smoke/`, never under
`results/.local/`. It therefore cannot enter the normal summary, dashboard,
paired statistics or sealed publication inputs.

## What runs

The profile is capability-aware:

- every selected harness runs `tool_use_001`, exercising ordinary workspace
  inspection, artifact creation and deterministic grading;
- harnesses that declare `browser` also run `browser_001`;
- harnesses that declare `structured_subagent_events` also run
  `subagents_001`;
- with `--all`, the union of those tasks is executed as matched interleaved
  blocks; a harness lacking an optional hard capability must record that task as
  `unsupported`, which is an expected smoke outcome rather than a failure.

The current expected per-harness plan is therefore:

| Harness | Core | Browser | Subagent |
| --- | --- | --- | --- |
| Hermes | yes | yes | unsupported |
| Pi Agent | yes | unsupported | unsupported |
| OpenCode | yes | unsupported | yes |
| Goose | yes | unsupported | yes |
| Letta | yes | unsupported | yes |
| Agent Zero | yes | yes | yes |

## Run one harness

An explicit model is mandatory because smoke verifies that the run manifest
resolved the same model that was requested:

```bash
aiosbench --piagent --model Ornith smoke
```

Keep raw stdout/event artifacts while diagnosing a new integration:

```bash
aiosbench --opencode --model Ornith --keep-raw smoke
```

## Run the complete matrix

Once every harness has been configured, use the same endpoint/model and run all
six in matched task-level interleaving:

```bash
aiosbench --all --model Ornith --seed 42 smoke
```

For llama.cpp efficiency verification, enable server metrics and dedicate that
server to the smoke run:

```bash
aiosbench --all --model Ornith --seed 42 \
  --server-metrics-url http://127.0.0.1:8080 \
  smoke
```

For a publication-readiness smoke, also set the same immutable model and
inference provenance used by the future campaign, for example:

```bash
export AIOS_BENCH_MODEL_DIGEST=sha256:<gguf-digest>
export AIOS_BENCH_INFERENCE_CONFIG='{"reasoning":"off","ctx":98304}'
aiosbench --all --model Ornith \
  --server-metrics-url http://127.0.0.1:8080 \
  smoke
```

Harness-specific environment variables, especially the Agent Zero isolation,
model and service-revision attestations, are documented in
[`harness-setup.md`](harness-setup.md).

## Smoke report

Each invocation writes a JSON report such as:

```text
results/.smoke/2026-08-21_130000_000000_smoke.json
```

The report exposes three independent readiness signals:

- `integration_ok`: every task the harness is expected to support passed, every
  optional unsupported task was reported as `unsupported`, and the resolved
  model exactly matched the requested model;
- `strict_model_ready`: every participating run carried sufficient immutable
  model/inference provenance for strict same-model comparison;
- `server_metrics_ready`: every participating run had the shared server metrics
  source enabled.

A smoke command exits successfully on `integration_ok`. The other two flags are
reported separately because a developer may legitimately verify an adapter
before supplying publication-grade model digests or llama.cpp telemetry.

Per task the report records status, score, failure kind, telemetry availability
and normalized event-type counts. It never copies prompts, tool arguments,
subagent content or model output into the diagnostic report.

Smoke always disables resume semantics. Reusing an explicit `--run-id` that
already contains results therefore fails instead of silently skipping the real
harness execution.

The smoke profile currently targets Frontier v3 because it is validating harness
integration contracts. Frontier v4 remains the parametric benchmark suite, not
an adapter-installation test.
