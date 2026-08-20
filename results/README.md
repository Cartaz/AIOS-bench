# Benchmark result snapshots

This directory is the publication boundary, not the raw run store. Git keeps:

```text
results/
  README.md
  summary.json
  dashboard.html
```

The runner stores manifests, task-level results, logs, and retained workspaces
under the Git-ignored path:

```text
results/.local/<harness>/<model>/runs/<run-id>/
```

`summary.json` and `dashboard.html` are generated snapshots. A leaderboard row
is comparable only when the run completed, belongs to the selected current
suite revision, and is neither legacy nor a dry run. Historical views may show
other runs, but must label them rather than mix their scores.

Do not use a `run_id` filename to infer recency. Lifecycle timestamps and suite
revision in `run.json` are authoritative. Full policy: [run lifecycle and
result publication](../docs/RUNS_AND_RESULTS.md).
