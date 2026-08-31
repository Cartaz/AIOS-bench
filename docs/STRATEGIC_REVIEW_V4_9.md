# Frontier V4.9 strategic review — AIOS-Index and benchmark health

Status: **CLOSED** — implementation, strategic review and canonical CI validation complete.

This review supplements `docs/STRATEGIC_REVIEW.md` and closes the Frontier v4 roadmap sequence started with V4.1. V4.9 does not add another capability family. It consolidates the existing benchmark into a compact routine-development profile, a benchmark-construction health gate and a simpler parametric-family integration boundary.

## Purpose

V4.9 has three goals:

1. provide a compact high-signal profile for routine model/harness iteration without creating a separate benchmark or scorer;
2. make benchmark construction itself testable independently of agent performance;
3. reduce change amplification accumulated while V4.1–V4.8 added generated families and task-scoped runtimes.

The canonical full Frontier v4 suite remains authoritative. AIOS-Index is an experiment profile over those tasks, and benchmark health validates their construction.

## Design comparison

### Alternative A — create a separate compact benchmark catalog

Rejected. Copying seven prompts/checks into an `aios_index` catalog would duplicate canonical task semantics and require synchronized revisions, graders and scientific identity.

### Alternative B — treat AIOS-Index as an ordinary task filter only

Rejected. A bare filter would not have a stable profile digest, explicit experiment context or protection against accidentally mixing results after the profile definition changes.

### Alternative C — metadata-only profile over canonical tasks

Chosen. `AIOSIndexProfile` owns task selection, selected-family pressure coordinates, roles and a profile digest while all prompts, generators, runtimes and graders remain canonical Frontier v4 assets.

### Alternative D — benchmark health through representative sample tasks

Rejected during milestone review. A health test over only `autonomy_expense_001` proved the mechanism but did not establish health of the benchmark as a whole.

### Alternative E — full-catalog agent-independent health gate

Chosen. CI now executes the health validator over every active Frontier v4 task without invoking an LLM or harness.

## Ownership and abstraction boundaries

### `core/benchmark/aios_index.py`

Owns compact-profile metadata only:

- stable selection name;
- canonical task IDs and capability roles;
- selected parametric families;
- effective selected-family pressure coordinates;
- deterministic profile digest;
- immutable digest-qualified comparison identity;
- validation that selected task families have not drifted.

It does not own prompts, acceptance checks, task generation, grading or scoring.

### `core/benchmark/aios_index_execution.py`

Owns orchestration of one compact profile through the existing runners and `MatchedInterleavedScheduler`. Single-harness and multi-harness runs preserve the existing lifecycle and result formats.

### `core/benchmark/health.py`

Owns deterministic benchmark-construction validation. It materializes generated variants in temporary benchmark-owned workspaces, checks oracle/workspace properties, applies benchmark-owned golden witnesses and deliberate near misses, and invokes the ordinary deterministic artifact evaluators.

It never invokes a model or harness and therefore measures benchmark health rather than agent performance.

### Parametric family registry

V4.9 resolves the V4.8 deferral by consolidating pressure type, generator, grader, optional post-materialization hook, optional runtime and optional failure diagnosis into `ParametricFamilySpec` entries in `FAMILY_SPECS`.

The public dispatch functions (`materialize_variant`, `start_variant_runtime`, `evaluate_variant`, `diagnose_variant_failure`) remain stable. Adding a family no longer requires parallel branching across generation/runtime/evaluation dispatch paths.

### Desktop/service boundary

The desktop remains presentation-only. `BenchmarkService` exposes available run profiles, validates mutual exclusion, owns exact task selection and passes a validated `PreparedRun` to execution. The frontend has one unified run-profile selector; selecting AIOS-Index or a long-horizon profile locks task selection because the profile owns the exact canonical task set.

AIOS-Index fixes the canonical `no_skill` condition. No persistent or operational benchmark state moved into JavaScript.

## Findings discovered during milestone review

### AIOS-Index initially depended on unrelated family defaults

The first implementation used `normalize_parameters()` wholesale for the profile digest. That meant changing the default pressure of a family not selected by AIOS-Index could change the compact-profile identity.

**Resolved:** each `IndexEntry` records its canonical parametric family; `AIOSIndexProfile.parameters()` now returns only selected-family coordinates. `select_tasks()` validates that catalog task family identity still matches the profile metadata.

### Stable profile names could allow old/new definitions to be grouped

Reporting keyed compact runs by `profile_id`, but the first context used the stable name `aios_index_v1`. If the profile definition changed without renaming it, older reporting code could silently aggregate incompatible versions.

**Resolved:** the stable selection name is recorded as `profile_name`, while run `profile_id` is now digest-qualified (`name@digest`). The full digest is also recorded separately. This makes comparison identity immutable and fail-closed even for reporting consumers that only key on `profile_id`.

### V4.9 modules polluted the Frontier semantic fingerprint

The automatic semantic-source discovery correctly includes task execution semantics by default, but newly added `aios_index.py`, `aios_index_execution.py` and `health.py` were initially included as well. Changing profile selection or benchmark self-check logic could therefore invalidate ordinary Frontier results despite unchanged task semantics.

**Resolved:** those three orchestration/health modules are explicitly non-semantic, matching the existing treatment of long-horizon profiles, derived analysis and reporting. Regression tests enforce this boundary.

### Benchmark health initially covered one representative task

The first health test validated the complete mechanism on `autonomy_expense_001`, but this did not guarantee that all active generated families remained satisfiable and discriminative.

**Resolved:** the canonical pytest suite now runs `validate_benchmark_health()` over the entire active Frontier v4 catalog. Every task must satisfy same-seed determinism, different-seed variation, oracle isolation/schema, protected-source integrity, instruction/verifier consistency, untouched-state failure, two-seed golden success, missing-artifact near-miss failure and grader runtime bounds.

### One test emitted a Python escape-sequence warning

`tests/test_epistemic_twins.py` used a non-raw regex string containing `\*`.

**Resolved:** the regex is now a raw string. The post-fix Python 3.12 CI run reports `451 passed` with no project warning summary.

### Documentation lagged the implementation

The README described V4.8 and generated long-horizon profiles but not AIOS-Index or full-catalog benchmark health.

**Resolved:** README now documents the unified profile selector, AIOS-Index identity/leaderboard boundary, full-catalog health gate and semantic-fingerprint boundary. `docs/AIOS_INDEX_AND_HEALTH.md` records the detailed V4.9 contracts.

## Benchmark-health contract

For each active Frontier v4 task, the health gate requires:

- same seed -> identical oracle identity;
- same seed -> identical materialized workspace;
- different seed -> changed oracle identity;
- different seed -> changed workspace;
- valid oracle schema and digest;
- no oracle directory or variant digest leakage into the agent workspace;
- protected benchmark sources intact immediately after materialization;
- exactly one authoritative parametric grader matching task/family identity;
- required output paths named by task instructions;
- untouched generated workspace fails when action/output is required;
- benchmark-owned golden witness passes;
- a golden witness on a comparison seed also passes;
- deleting a required artifact produces a deterministic failure;
- grader execution stays inside the configured health budget.

This is intentionally construction-focused. It does not try to predict whether a model will find the task difficult or whether one pressure axis is monotonic.

## Scientific identity and comparability

Task semantics continue to be identified by the Frontier suite revision and task/variant identity. Generators, runtimes, graders, catalogs and other execution-semantic modules remain inside the semantic fingerprint.

AIOS-Index and long-horizon profiles are orchestration layers with their own digests. Benchmark-health validation is a quality gate. None changes ordinary task semantics, so none belongs in the suite semantic revision.

AIOS-Index results remain separate from the full-suite leaderboard. Curated-skill runs, long-horizon pressure runs and compact-profile runs therefore cannot silently inflate canonical capability/reliability aggregates.

## Complexity review

### Change amplification

The most important V4.9 design investment is `FAMILY_SPECS`. Before consolidation, a new generated family required changes in repeated dispatch branches for pressure validation, generation, runtime startup and grading. Those responsibilities are now registered once behind the same public functions.

AIOS-Index similarly references canonical tasks instead of cloning them, and health uses the existing materializer/evaluator/golden contracts rather than implementing a second grader pipeline.

### Cognitive load

There are now three clearly separate concepts:

- canonical Frontier task semantics;
- experiment profiles that select/orchestrate canonical tasks;
- benchmark-health validation of construction invariants.

The semantic fingerprint boundary mirrors those concepts. This is simpler than treating every module under `core/benchmark/` as scientific task semantics.

### Hidden dependencies

AIOS-Index entries explicitly record their pressure family, and selection fails if the catalog task drifts to another family. This is deliberate duplication of identity metadata at the profile boundary, paired with validation, rather than hidden dependence on a hard-coded family list elsewhere.

Benchmark health depends on benchmark-owned golden materializers. That dependency is appropriate: the health gate asks whether the benchmark has a known satisfying witness and deterministic negative discrimination.

### Special cases

No harness-specific AIOS-Index path was added. Multi-harness execution uses `MatchedInterleavedScheduler`; single-harness execution uses the same runner surface.

No new scorer, result format or leaderboard was introduced. The desktop profile selector is a presentation of Python-owned profile state, not a second source of truth.

## Validation coverage

V4.9-specific deterministic coverage includes:

- compact profile task selection;
- selected-family pressure ownership;
- stable selection name plus digest-qualified comparison identity;
- profile family-drift rejection;
- missing task and dependency rejection;
- single/multi-run compact execution context;
- separate reporting eligibility from full-suite capability rows;
- desktop catalog, validation and profile-owned task selection;
- family registry single-source ownership and runtime registration;
- semantic-fingerprint exclusion of AIOS-Index/orchestration/health modules;
- full active Frontier v4 catalog benchmark-health validation;
- instruction/verifier drift detection;
- health budget validation;
- regression coverage preventing distinct compact profile revisions from sharing one comparison identity.

Implementation commit `5e828b1f1c95bff4a7475d1a1017bd718f7f646e` passed the complete GitHub Actions matrix on Python 3.12, 3.13 and 3.14. The Python 3.12 job observed:

- installation and critical Qt imports successful;
- Bubblewrap functional sandbox probe successful;
- `compileall` successful;
- Ruff: `All checks passed!`;
- pytest: `451 passed in 19.39s`;
- no Python/project warning summary.

The formal strategic-review commit `25ea0984674852ad8f2901f1c05632d6c7babe28` also passed the canonical matrix on Python 3.12, 3.13 and 3.14. Every job completed installation, Bubblewrap verification, compileall, Ruff and pytest successfully; the Python 3.13 run observed `451 passed in 33.33s`.

## Deliberate deferrals

### No empirical re-weighting of AIOS-Index

The current seven tasks are a structurally selected high-signal profile. V4.9 does not claim that their weights form an empirically optimal composite index. Future replacement/removal should use observed discrimination, redundancy and runtime data and will naturally produce a new profile digest.

### No opaque scalar AIOS score

The profile remains a compact run set, not a new weighted leaderboard. Raw task/capability dimensions remain available; introducing an opaque composite would require empirical justification.

### No live-model benchmark health

Health validation deliberately excludes model/harness behavior. Model smoke runs answer a different question and remain separate from generator/oracle/grader self-validation.

### No automatic merge into `main`

Milestone closure establishes the branch as technically complete. Integration into the default branch is a separate repository operation and is not part of this review.

## Review conclusion

V4.9 completes the intended Frontier v4 roadmap without adding a parallel benchmark architecture. AIOS-Index is a metadata-only compact profile over canonical tasks, benchmark health now gates every active v4 task independently of agent performance, and parametric-family dispatch has been consolidated behind one declarative registry.

The milestone review found and resolved three correctness/maintainability issues that ordinary green unit tests did not expose: unrelated pressure coordinates in compact-profile identity, orchestration modules contaminating suite semantic revisions, and health validation covering only one representative task. It also made compact-profile comparison identity fail closed across profile revisions, removed the remaining Python test warning and brought documentation up to date.

No high-impact tactical workaround or duplicated scientific source of truth remains in the V4.9 path. The strategic-review commit passed the complete canonical CI matrix, so **Frontier V4.9 is formally closed** on branch `v4.9-aios-index-benchmark-health`. Integration into `main` remains a separate operation.
