# Benchmark artifact retention

AIOS-bench keeps `results.jsonl` as the canonical post-run analysis record.

After a normal benchmark run, retention cleanup automatically:

- removes the redundant `events.jsonl` stream;
- removes successful-task stdout logs because their parsed telemetry is embedded in `results.jsonl`;
- retains stdout for failed, timed-out, or errored tasks for diagnosis;
- removes empty stderr logs;
- removes reproducible dependency/cache directories such as `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, and `.ruff_cache` from generated workspaces;
- preserves generated source files, reports, and other task artifacts in the workspace.

A small `retention.json` manifest records the retention policy used for the run.

Use `--keep-raw` when a full unpruned run is needed for debugging the harness itself.
