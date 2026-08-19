# AIOS-bench

AIOS-bench is a reproducible local benchmark suite for AI operating-system agents. It evaluates agent behavior through isolated workspaces, deterministic artifact checks, execution telemetry, and an optional blinded qualitative judge.

## Running

Select a configured harness and model, for example:

```bash
aiosbench --piagent --model Qwen --no-resume
```

Or run every configured harness sequentially with `--all`.

The runner executes the calibrated frontier catalog in deterministic order, creates an isolated workspace for each task, records observable execution data, applies weighted deterministic acceptance checks, stores resumable results, and regenerates the comparison dashboard.

## Optional blinded LLM judge

The benchmark can also ask the **same model** to independently inspect the finished workspace using a separate, strict system prompt:

```bash
aiosbench --piagent --model Qwen --no-resume --llm-judge
```

The judge receives only the original task request and an isolated snapshot of the final workspace. It does **not** receive the deterministic score, the expected answer, the agent's execution transcript, or the model/harness identity. It has read-only tools and cannot modify the evaluated workspace.

The judge returns a separate 0–100 qualitative score with seven criteria: correctness, completeness, problem solving, efficiency, robustness, independence, and creativity. Its score and evidence are stored under `llm_judge` in each task result and summarized in `results/summary.json` and the dashboard.

The judge is deliberately **diagnostic, not authoritative**: it never changes pass/fail and never changes the deterministic benchmark score. This prevents the benchmark from becoming circular while still exposing cases where an artifact passes mechanical checks but is substantively poor, or where an objective checker is too strict.

Use `--judge-timeout` to change the per-task judge timeout (default 300 seconds). Because the same local model performs a second inference pass, enabling the judge substantially increases total benchmark time.

### Offline calibration of an existing run

An existing run can be judged without rerunning any agent task. This is useful when calibrating the benchmark itself because it lets us compare deterministic and qualitative scores on exactly the same completed workspaces:

```bash
aiosbench judge second_benchmark_results_for_evaluation_of_tests/piagent/Qwen/runs/2026-08-19_123411_frontier-v2 --judge-timeout 300
```

This command does **not** modify the original `results.jsonl`. It writes `judge_calibration.jsonl` and `judge_calibration_summary.json` beside it. The summary reports judge coverage, mean scores, Pearson and Spearman correlation, mean absolute disagreement, and the ten largest objective-vs-judge gaps. No second model or cloud service is involved; the configured local model is invoked for the judge pass.

## Frontier task calibration

The active catalog is `benchmarks/tasks/frontier_v2.json` and contains **28 tasks**. Every task is intentionally Tier 3, 4, or 5:

- **Tier 3 — Advanced:** multi-step work with several independent failure points.
- **Tier 4 — Expert:** requires synthesis, recovery, validation, or transfer across steps.
- **Tier 5 — Frontier:** combines multiple difficult capabilities, negative constraints, ambiguity, or independent verification.

There are no Tier 1/2 tasks in the active suite. The goal is discrimination among capable agent/model combinations, not measuring whether an agent can perform trivial tool calls.
