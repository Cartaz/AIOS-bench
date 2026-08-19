# AIOS-bench

Reproducible benchmark suite for local AI operating-system agents.

## Optional blinded LLM judge

The benchmark can optionally run the same local model a second time as a blinded qualitative evaluator after each task:

```bash
aiosbench --piagent --model Qwen --no-resume --llm-judge
```

The judge receives only the original task request and an isolated snapshot of the final workspace. It does **not** receive the deterministic score, the expected answer, the agent's execution transcript, or the model/harness identity. It has read-only tools and cannot modify the evaluated workspace.

The judge returns a separate 0–100 qualitative score with seven criteria: correctness, completeness, problem solving, efficiency, robustness, independence, and creativity. Its score and evidence are stored under `llm_judge` in each task result and summarized in `results/summary.json` and the dashboard.

The seven criterion values are authoritative. The harness recomputes the canonical weighted score from those criteria, while retaining the model's reported top-level score and its discrepancy from the canonical value for diagnostics. Small arithmetic or rounding differences therefore do not invalidate an otherwise usable judgment.

If the first judge response is malformed or cannot be parsed, the harness makes one short format-only recovery attempt using the same model, with a maximum 60-second retry timeout. A failed recovery remains a judge error and does not affect the deterministic benchmark score.

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
