# Local benchmark artifact retention

AIOS-bench keeps `results.jsonl` as the canonical local post-run analysis
record. Local run data is written beneath `results/.local/` and is ignored by
Git.

After a normal benchmark run, retention cleanup automatically:

- removes the redundant `events.jsonl` stream;
- removes successful-task stdout logs because their parsed telemetry is embedded in `results.jsonl`;
- retains stdout for failed, timed-out, or errored tasks for diagnosis;
- removes empty stderr logs;
- removes reproducible dependency/cache directories such as `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, and `.ruff_cache` from generated workspaces;
- removes benchmark-created nested `.git` directories after evaluation, preventing workspaces from becoming broken gitlinks if results are moved;
- removes benchmark-owned `.aios-bench-eval` scratch outputs after their oracle has run;
- preserves generated source files, reports, and other task artifacts in the workspace.

A small `retention.json` manifest records the retention policy used for the run.

Use `--keep-raw` when a full unpruned run is needed for debugging the harness itself.

## Repository publication boundary

Raw trajectories can be large and may contain model output, absolute paths, or
other environment-derived data. Do not force-add `.local/` to Git. The
publishable repository artifacts are:

- `results/summary.json`, regenerated from local manifests/results;
- `results/dashboard.html`, regenerated from the same snapshot;
- small, deliberately curated fixtures outside `.local/`, if a test requires
  one and its contents have been reviewed.

`run.json`, `results.jsonl`, logs, workspaces, persistent warm state, event
streams, and `latest` pointers remain local. See [Run lifecycle, manifests, and
result publication](RUNS_AND_RESULTS.md) for the publication and migration
procedure.
