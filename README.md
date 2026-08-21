# AIOS-bench

Reproducible benchmark suite for local AI operating-system agents.

## Install and run

The runtime package has no test-framework dependency. Install the development
extra when working on the benchmark itself:

```bash
python -m pip install -e .
python -m pip install -e '.[dev]'  # contributors and CI
```

```bash
aiosbench --piagent --model Qwen --no-resume
```

Or run every active harness with task-level matched interleaving:

```bash
aiosbench --all --model Qwen --repeats 3 --seed 42
```

The active harness matrix is Hermes, Pi Agent, OpenCode, Goose, Letta and Agent
Zero. `--seed` is an **orchestration seed** used to make task-block ordering
reproducible; it does not set the model's sampling RNG. With `--all`, each
`(task, repeat)` is one matched block. Every harness receives the same static
Frontier v3 task identity and derived `task_seed`, while harness order is
shuffled independently and deterministically inside each block. This spreads
server/thermal drift across harnesses without changing the benchmark task.

Sampling/server settings that affect generation should be supplied as JSON in
`AIOS_BENCH_INFERENCE_CONFIG`. For strict same-model comparisons, set
`AIOS_BENCH_MODEL_DIGEST` to an immutable model/GGUF digest. Optionally set
`AIOS_BENCH_MODEL_FILE` to compute and record the SHA-256 directly; if both are
provided, a mismatch is recorded and strict comparability is disabled.

Each repeat remains an independent raw run. The generated summary adds
repeat-level diagnostics including pass rate, empirical pass@k/pass^k, median
score, score range and an attempt-level Wilson 95% interval. Matched
multi-harness experiments additionally produce strict pairwise comparisons.
Pairs are accepted only when both harnesses report the same strict model
identity fingerprint. The report includes matched score deltas, wins/losses,
discordant pass outcomes, a task-cluster bootstrap 95% interval and a
deterministic paired sign-flip permutation p-value. Unsupported, blocked and
otherwise unmatched observations are never imputed.

The runner executes the active frontier v3 catalog in deterministic task order,
creates an isolated workspace for each task, preserves explicit warm-state
chains for memory and learning tasks, records observable execution data, applies
deterministic reference checks, stores resumable results, and regenerates the
comparison dashboard. Under matched interleaving, `--total-timeout` is an active
execution budget per harness, so time spent waiting while another harness runs
does not consume that harness's budget.

### llama.cpp server telemetry

For cross-harness efficiency measurements, start `llama-server` with its
Prometheus metrics endpoint enabled (`--metrics`) and give AIOS-bench the server
origin or `/metrics` URL:

```bash
aiosbench --all --model Ornith --repeats 5 \
  --server-metrics-url http://127.0.0.1:8080 \
  --max-output-tokens 65536
```

`AIOS_BENCH_SERVER_METRICS_URL` is the environment-variable equivalent. In
llama.cpp router mode, `--server-metrics-model MODEL_ID` adds the model filter to
the metrics query. If `AIOS_BENCH_ENDPOINT` is already set, AIOS-bench can derive
the same-origin `/metrics` URL automatically.

AIOS-bench snapshots cumulative llama.cpp counters immediately before and after
each task and stores server-derived prompt/output tokens, prompt/generation
seconds and derived throughput. Cross-harness efficiency uses only rows marked
`usage_source=server_verified`; harness-reported token counts remain diagnostic.
If metrics are unavailable or counters reset during a task, measurement fails
closed to non-comparable efficiency without changing the task's capability
result.

The llama.cpp metrics endpoint is aggregate server state. For publication-grade
efficiency runs, dedicate the measured model/server to AIOS-bench while the run
is active. Concurrent external requests would otherwise contaminate counter
deltas. `--max-output-tokens` uses the same server counter as a runaway guard;
set it to `0` to disable the guard. A triggered guard records `RUNAWAY` rather
than conflating it with `TIMEOUT` or `CRASH`.

Raw task rows carry one mutually exclusive failure kind: `PASS`, `WRONG`,
`CRASH`, `TIMEOUT`, `RUNAWAY`, `REFUSED`, `INFRA_ERROR`, `UNSUPPORTED` or
`BLOCKED`. `REFUSED` requires structured harness telemetry or an explicit
refusal/safety stop reason; AIOS-bench does not infer refusals from prose.

## Deterministic evaluation

AIOS-bench uses **deterministic evaluators as the authoritative benchmark signal**. There is no LLM judge. A task passes only when the agent execution and its required artifacts satisfy reproducible acceptance checks.

Frontier v3 replaces weak "file exists + keyword" acceptance with benchmark-owned reference oracles for the tasks where content matters. These checks can validate exact evidence provenance, alternate datasets, hidden regression tests, negative constraints, dependency chains, persistent memory state, and delegation telemetry without asking another model to grade the result.

Run checkpoints are resumable only when the full benchmark semantics match: the
catalog, deterministic fixture inputs, and reference-oracle implementation are
fingerprinted together. A fixture or oracle update therefore starts affected
work again rather than silently mixing incomparable scores.

Comparable task score is `80% deterministic acceptance + 20% successful
execution`. A failed task is capped at 49/100, so partial artifacts cannot look
like a passing result. Telemetry-derived efficiency and recovery metrics remain
diagnostic fields rather than cross-harness score inputs. Tasks recorded as
`unsupported` or dependency-`blocked` have no score.

### Integrity preflight

```bash
aiosbench validate
```

The current preflight checks that every untouched fixture fails its deterministic
acceptance grader. On Linux with bubblewrap, benchmark-owned task catalogs,
tests, `.git`, reference-check bytecode/source, prior runs and sibling
workspaces are masked from the child process in addition to write confinement.
A positive reference-solution preflight is planned as the next integrity step.

## Results layout

Raw benchmark runs are local data. They live under `results/.local/` using one
canonical layout:

```text
results/
  README.md
  summary.json
  dashboard.html
  .local/
    <harness>/
      <model>/
        latest.txt and, where supported, latest -> runs/<run-id>
        runs/
          <run-id>/
            run.json
            results.jsonl
            logs/
            workspaces/
```

`.local/` is ignored by Git. The repository publishes only the regenerated
aggregate `summary.json` and `dashboard.html`; a `run.json` remains beside its
local run for audit and reproducibility. See [run lifecycle and
comparability](docs/RUNS_AND_RESULTS.md) and the [artifact retention
policy](docs/ARTIFACT_RETENTION.md).

```bash
aiosbench dashboard  # local diagnostic view under results/.local/
aiosbench publish    # reviewed aggregate snapshot under results/
```

## Frontier v3

The active catalog is `benchmarks/tasks/frontier_v3/*.json` and contains **28 tasks** split by capability. The category files are loaded in lexical order, giving a stable execution order.

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** synthesis, recovery, validation, transfer, or grounded research.
- **Tier 5 — Frontier:** combines difficult capabilities with negative constraints, hidden checks, state persistence, or independent verification.

The v3 fixtures deliberately include alternate datasets, malformed inputs, distractors, conflicting procedures, schema shifts, persistent-state chains, and hidden regression tests. The benchmark-owned reference checks live in `aios_bench/reference_checks_*.py` and never invoke an LLM.

The long-horizon workspace is materialized per run with a deterministic corpus
larger than 50 KiB, a late authoritative release gate, and a stateful validator
that fails reproducibly on its third execution. Its oracle checks the grounded
release-gate citation, recorded recovery, untouched validator, and checkpoints.

Subagent tasks count only normalized `subagent_start` events from the harness;
mentions of delegation in a report or stdout do not count as evidence of a
delegated run. Harnesses without compatible structured delegation telemetry
are recorded as `unsupported`, with no score, and excluded from comparable
aggregates rather than treated as failures.
