# Run lifecycle, manifests, and result publication

This document defines when an AIOS-bench result is complete, comparable, and
safe to publish. It is part of the benchmark contract: consumers should not
infer these properties from directory names or the presence of a partial
`results.jsonl` file.

## Lifecycle

`run.json` has exactly one of these lifecycle states:

- `running`: the run directory and manifest exist, but supported tasks may
  still be executing;
- `completed`: the runner ended normally and accounted for every catalog task,
  including tasks recorded as unsupported;
- `aborted`: the runner stopped before normal completion, for example after an
  interruption, an unhandled harness error, or a whole-suite timeout.

`started_at` is written when the run is allocated. `finished_at` is added only
when it reaches a terminal state. A completed run can contain failed tasks and
unsupported tasks: lifecycle completion does not mean a perfect benchmark
score.

The manifest also records `task_count`, `supported_task_count`,
`unsupported_task_count`, and `completed_task_count`. Consumers must use these
fields and `status`; a timestamp-shaped `run_id` is an identifier, not an
ordering or completeness signal. The per-model `latest` pointer is updated only
for completed runs.

## Execution manifest

The nested `manifest` object captures the environment needed to assess whether
runs are equivalent:

- harness executable and discovered version;
- requested model and best-effort resolved model;
- provider and endpoint, with credentials and other secrets removed;
- adapter-declared capabilities;
- Python version and platform.

Top-level Git provenance records both `git_commit` and `git_dirty`; a dirty
run must not be presented as if the commit alone reproduced it. The semantic
suite fingerprint still covers uncommitted benchmark code and fixture changes.

Model resolution is best effort because some harnesses configure their actual
model outside the command line. A requested label is not proof that the
provider served that model. If the resolved model or harness version is absent,
state that limitation when publishing a comparison. Never add API keys,
authorization headers, query credentials, or unredacted secret-bearing URLs to
the manifest.

`execution_fingerprint` is the SHA-256 of the sanitized manifest. Comparisons
should match both `suite_revision` and this execution profile, or explicitly
disclose differences in harness version, resolved model, provider, platform,
or sandbox strategy.

`suite_revision` fingerprints the catalog, deterministic fixtures, and
reference-oracle implementation. Results from different revisions are
historical data, not entries in one leaderboard.

## Unsupported is not failed

Before execution, the runner compares a task's required capabilities with the
adapter's declared capabilities. A task that cannot be measured faithfully is
written to `results.jsonl` with:

```json
{
  "status": "unsupported",
  "score": null,
  "comparable": false
}
```

No agent process is launched for that task. Unsupported tasks count toward
`task_count` and `unsupported_task_count`, but never toward pass rate, mean
score, or failure count. In particular, delegation tasks require compatible
structured `subagent_start` telemetry; a textual claim of delegation cannot
turn an unsupported harness into a comparable result.

Warm memory and learning tasks declare explicit `depends_on` chains. If an
upstream task has not succeeded, the dependent task is recorded as `blocked`
with no score and no agent launch. `blocked` is reported separately from
`unsupported`; on resume it is retried after its prerequisite succeeds.

## Dashboard and summary rules

The default leaderboard selects the newest observed non-legacy, non-dry-run
suite revision from lifecycle timestamps and includes only runs that are all of
the following:

- `status: "completed"`;
- on the selected current `suite_revision`;
- non-legacy;
- not marked as a dry run.

Historical views can expose running, aborted, legacy, dry-run, and older-suite
runs for diagnosis. They must preserve their labels and must not merge their
scores with the current leaderboard. Within a run, the latest task record for a
given task ID supersedes earlier resume attempts.

## Local storage and publication

The complete local record uses this layout:

```text
results/.local/<harness>/<model>/
  latest.txt
  latest -> runs/<run-id>  # best-effort convenience symlink
  runs/<run-id>/
    run.json
    results.jsonl
    retention.json
    logs/
    workspaces/
```

`.local/` is ignored by Git. `run.json` remains the local audit manifest;
`results.jsonl`, logs, event streams, workspaces, persistent state, and pointers
are also local-only. Git publishes the regenerated `results/summary.json` and
`results/dashboard.html` snapshots plus `results/README.md`. A small fixture may
be committed outside `.local/` only when a test needs it and it has been
manually reviewed.

Before publishing a snapshot:

1. Review local-only output with `aiosbench dashboard`, then regenerate both
   publishable artifacts with `aiosbench publish`.
2. Confirm the snapshot selects the intended suite revision and only completed
   non-legacy, non-dry-run leaderboard entries.
3. Review the diff for model output, absolute paths, endpoint credentials, and
   other environment-derived secrets.
4. Commit the summary and dashboard together so they describe the same input
   set.

## Migrating legacy tracked results

Ignore rules do not remove files already present in the Git index. Preserve raw
files locally under `results/.local/`, then remove the old paths from the index
in the same migration commit. Review the staged diff before committing; do not
delete the local `.local/` archive.

One legacy workspace is recorded as a Git entry of mode `160000` even though the
repository has no `.gitmodules` entry and does not contain its target commit:

```text
results/piagent/aios-llamacpp_Qwen/runs/2026-08-20_000249_frontier-v3/workspaces/memory_004
```

Verify the anomaly without changing anything:

```bash
git ls-files -s -- results/piagent/aios-llamacpp_Qwen/runs/2026-08-20_000249_frontier-v3/workspaces/memory_004
git ls-files -s | awk '$1 == 160000 { print }'
```

After the containing legacy run has been copied or moved into the ignored
`results/.local/` archive, remove only the broken index entry:

```bash
git rm --cached -- results/piagent/aios-llamacpp_Qwen/runs/2026-08-20_000249_frontier-v3/workspaces/memory_004
```

Do not add a fabricated `.gitmodules` file and do not recreate the missing
commit. The workspace is benchmark output, not a source dependency. Confirm
that no gitlinks remain with the second verification command above, then review
`git status --short` before committing the migration.
