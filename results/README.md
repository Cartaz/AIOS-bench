# Benchmark result snapshots

This directory is the publication boundary, not the raw run store. Git keeps:

```text
results/
  README.md
  summary.json
  dashboard.html
  publication.json
```

The runner stores manifests, the append-only task-attempt journal, logs, generated Frontier v4 oracles and retained workspaces under the Git-ignored path:

```text
results/.local/<harness>/<model>/runs/<run-id>/
```

`results.jsonl` is the authoritative task-observation stream. Analysis loaders preserve every valid row as a raw attempt and derive the familiar latest-result view separately. `summary.json` and `dashboard.html` are therefore derived snapshots, not source data.

Tracked derived files without a matching, successfully verified `publication.json` must be treated as historical snapshots only. They are useful for provenance, but they are not evidence that the displayed scores correspond to the current suite revision or current execution implementation.

`publication.json` seals the publication against three independent inputs:

- SHA-256 index of every local `run.json` and `results.jsonl` used by analysis;
- fingerprint of the raw/report/statistics/dashboard/publication implementation;
- SHA-256 and byte size of the published `summary.json` and `dashboard.html`.

Create and verify a publication with:

```bash
aiosbench publish
aiosbench verify
```

`verify` checks the sealed source snapshot and analysis implementation, verifies published output hashes, then regenerates summary and dashboard in a temporary directory and requires the regenerated hashes to match. A changed raw run, modified derived artifact, or different analysis implementation fails closed.

A leaderboard row is comparable only when the run completed, belongs to the selected current suite revision, and is neither legacy nor a dry run. Historical views may show other runs, but must label them rather than mix their scores.

Do not use a `run_id` filename to infer recency. Lifecycle timestamps and suite revision in `run.json` are authoritative. Full policy: [run lifecycle and result publication](../docs/RUNS_AND_RESULTS.md).
