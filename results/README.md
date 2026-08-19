# Benchmark results

All benchmark runs use the canonical layout:

```text
results/<harness>/<model>/runs/<run-id>/
```

Each run contains its metadata, deterministic task results, logs, and retained workspaces. `dashboard.html` and `summary.json` are generated at the `results/` root when a benchmark or dashboard command runs.

Historical runs are kept under the same structure so they can be compared with future runs without special-case directory names.
