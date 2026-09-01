# Frontier V4.10 — Persistent Memory

Frontier V4.10 adds a deterministic, parametric durable-memory lifecycle to the canonical Frontier v4 catalog. It is intentionally a longitudinal family rather than three unrelated memory questions: the benchmark must observe whether state written in one task survives into later warm tasks without leaking transient information.

## Canonical tasks

The `persistent_memory` family owns three ordered tasks:

1. `memory_persist_001` (`T3`, cold) — capture every durable preference from the current authoritative source while excluding transient session instructions and historical distractors.
2. `memory_persist_002` (`T4`, warm) — retrieve and apply the persisted preferences when the request deliberately omits their values; the durable store must remain unchanged.
3. `memory_persist_003` (`T5`, warm) — apply durable updates, preserve unrelated preferences, record exact previous/current history, and reject transient update noise.

The latter two tasks depend on their predecessor. A failed memory state therefore blocks downstream observations instead of generating misleading independent failures.

## Deterministic pressure coordinates

`PersistentMemoryPressure` currently owns four coordinates:

- `durable_fact_count` — number of durable preferences generated;
- `transient_fact_count` — current-session values that must not enter durable memory;
- `distractor_fact_count` — stale/historical preference noise;
- `update_count` — number of durable keys changed in the update phase.

The family is seed-derived. Same task seed and coordinates produce the same generated workspace/oracle; a different task seed changes the generated variant.

## Persistent-state ownership

Persistent state is not a memory-task special case in the runner. `ParametricFamilySpec` declares benchmark-owned `persistent_paths`, while `ParametricTaskMaterializer` owns the lifecycle:

- cold tasks begin without restored family state;
- warm tasks restore the declared paths before materialization;
- after execution the materializer snapshots those paths into the run's benchmark-owned persistent-state area;
- `state_scope` is declared in task `variant_context` and is path-sanitized;
- every harness/repeat has its own run directory, so persistent state cannot cross harness or repeat boundaries.

For V4.10 the only declared persistent path is `.agent_memory`. The interface is generic so future longitudinal families such as Learning & Transfer can reuse it without adding task IDs or category branches to the materializer.

## Oracle and grader boundary

Generated oracles remain outside the agent workspace. The family grader verifies:

- all protected generated inputs remain byte-identical;
- `.agent_memory/preferences.json` equals the complete canonical durable state;
- transient values are absent by exact-state comparison;
- unrelated durable preferences survive updates;
- update history is exact;
- the phase-specific report is exact.

Warm phases can also be constructed independently by benchmark-health/preflight validation. In that context the generator derives an oracle-only synthetic prior state; it does not materialize that state into the agent workspace. Real runs still require the preceding task to create and persist the state.

## Benchmark health and preflight

Both `validate_benchmark_health` and `validate_parametric_baseline` consume the same catalog-owned `variant_context` parser from `ParametricTaskMaterializer`. This prevents the two validation paths from silently materializing a contextual family with different semantics.

The full Frontier v4 health gate now includes the memory tasks, while dedicated tests additionally exercise the actual capture → restore → apply → persist → update lifecycle.

## AIOS-Index

V4.10 does **not** add Persistent Memory to `aios_index_v1`. The compact profile remains the seven-task V4.9 selection until empirical runs justify changing it. Because AIOS-Index parameters include only selected pressure families, `persistent_memory` is not added to the profile digest merely by existing in the full catalog.

## Deliberate scope

V4.10 does not add dedicated GUI/CLI pressure editors for Persistent Memory. The normalized family registry records the canonical defaults in ordinary Frontier v4 execution identity, and the family can be parameterized through the internal normalized parameter contract. Dedicated user-facing sweep controls are deferred until empirical use shows that varying these coordinates is valuable enough to justify additional interface surface.
