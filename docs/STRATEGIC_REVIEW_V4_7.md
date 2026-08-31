# Frontier V4.7 strategic review — Generated Long-Horizon Pressure

Status: implementation and strategic review complete; formal milestone closure requires the canonical CI matrix on the final review commit to pass.

This review supplements `docs/STRATEGIC_REVIEW.md`. V4.7 adds benchmark-owned generated workload paths over existing Frontier v4 families without introducing a new task family, grader, runner, harness special case or scalar notion of difficulty.

## Purpose

The milestone is intended to answer a different question from an ordinary single-point benchmark result: how does capability respond as concrete workload dimensions increase while the underlying task semantics and generated randomness remain controlled?

The implementation therefore preserves the existing deterministic family generators and graders and varies only explicit pressure coordinates. The initial profile covers five families:

- `stateful_world`;
- `dependency_world`;
- `workspace_lineage`;
- `tool_recovery`;
- `wide_retrieval`.

The default `generated_long_horizon_v1` profile contains three exact pressure cells per family. Cell order is a benchmark-owned workload path, not a claim that difficulty is one-dimensional or monotonic.

## Design comparison

### Alternative A — add one very large synthetic “long-horizon” task

Rejected. A mega-task would conflate state mutation, dependency discovery, tool recovery, retrieval and context pressure into one opaque result. It would also make failures hard to localize and would weaken the existing “hard to solve, cheap to verify” property.

### Alternative B — clone existing catalog tasks at several fixed sizes

Rejected. Duplicating catalog entries would create task-ID and acceptance-rule duplication, increase suite-revision churn and make every future family fix propagate across several copies. It would encode experimental pressure choices as canonical task semantics.

### Alternative C — benchmark-owned pressure profile over existing families

Chosen. One profile owns exact cells and a stable profile digest. `horizon_execution.py` orchestrates ordinary Frontier runners with cell-specific normalized pressure vectors. Existing materializers, runtimes, deterministic graders, telemetry, harness capability checks and result persistence remain authoritative.

A full Cartesian grid was also deliberately avoided. The first version uses a small reproducible path per family so experimental cost grows linearly and every observed point remains exact rather than interpolated.

## Ownership and abstraction boundaries

### `core/benchmark/horizon.py`

Owns the experiment definition: profile schema, profile IDs, exact cells, pressure validation, axis roles and profile digest. It does not execute agents or grade results.

`parameters_for()` starts from the canonical normalized Frontier v4 pressure manifest and replaces exactly one family vector. This avoids a second source of defaults and guarantees that each run still records the complete pressure identity.

### `core/benchmark/horizon_execution.py`

Owns execution of a profile, not task semantics. It selects the already-loaded canonical task, creates ordinary runners through a factory and chooses either single-runner execution or the existing matched interleaved scheduler.

Within one repeat, all cells of the same canonical task receive the same orchestration seed and therefore the same derived task seed. The pressure vector is the controlled variable. Repeats advance the orchestration seed normally.

### Experiment metadata

`experiments.py` now accepts a namespaced `experiment_context` object. Profile metadata cannot overwrite canonical experiment, model or task identity fields.

The experiment context is persisted in `run.json` before agent execution begins and is re-applied to result rows after execution. Matched interleaving now records experiment identity before the first task block as well. This matters for fail-closed provenance: an interrupted pressure run must not become an unlabelled ordinary run merely because post-run annotation never happened.

### Reporting

`horizon_analysis.py` owns family response aggregation. Every point preserves the exact pressure vector and descriptive metrics such as pass rate, Wilson interval, score, runtime, token counts, variant count and failure distribution.

The analysis explicitly refuses to infer a global difficulty coordinate. `path_index` is presentation/order metadata only.

### Application surfaces

CLI and desktop controls resolve profiles from the same Python registry. A pressure profile owns its required task selection, preventing a GUI or CLI caller from silently running only a subset of the declared profile.

The desktop remains presentation-only; no profile semantics or pressure vectors are duplicated in JavaScript.

## Scientific identity and comparability

The profile is experimental orchestration, not a new Frontier v4 task semantic revision. `horizon.py`, `horizon_execution.py` and `horizon_analysis.py` are therefore outside `semantic_source_paths()`. The experiment carries its own `profile_digest`, and tests enforce this boundary.

This separation prevents two bad outcomes:

1. changing a pressure path would otherwise invalidate every ordinary Frontier v4 result even though no canonical task or grader changed;
2. leaving profile changes unidentified would make different experiments appear equivalent.

The profile digest supplies the missing identity without abusing `suite_revision`.

## Canonical-metric isolation

Pressure sweeps are interventions. They must not inflate or depress the ordinary capability leaderboard simply because they add many observations at deliberately non-default pressure coordinates.

The report layer now has one canonical row policy. `canonical_capability_rows()` excludes both curated-skill interventions and long-horizon pressure rows. That same policy is reused by:

- the ordinary leaderboard selection;
- repeat/reliability aggregates;
- paired harness comparisons;
- failure distributions;
- server-efficiency aggregates;
- ordinary Frontier v4 pressure landscapes and family-specific canonical metrics.

Long-horizon baseline rows remain available only to the dedicated `long_horizon_response_curves` analysis. Curated-skill pressure runs remain experimental and do not enter canonical capability metrics.

## Findings discovered during milestone review

### Pressure runs could become the selected ordinary suite revision

The first implementation summarized horizon runs like any completed baseline run. A newer pressure run could therefore become leaderboard-eligible and change the selected revision.

**Resolved:** run summaries detect the namespaced horizon context, label the run with `eligibility_reason: pressure_profile` and exclude it from ordinary suite selection and leaderboard eligibility.

### Derived statistics initially bypassed the canonical-row policy

`summary.json` correctly filtered canonical family metrics, but `augment_summary_file()` independently reloaded all latest rows for reliability, paired comparisons, failure distributions and server efficiency. This was change amplification and a second policy owner.

**Resolved:** those aggregates now consume `canonical_capability_rows(load_results(...))`. A regression test mixes ordinary and horizon matched runs and verifies that horizon observations cannot enter any of the four generic derived-statistics sections.

### Experiment identity was initially applied only after execution

If the process terminated before post-run annotation, a partial pressure run could exist without its intervention context.

**Resolved:** single-harness horizon execution and matched interleaving persist experiment metadata before agent work begins, then re-annotate final rows after execution. A boundary test checks that the horizon context is already visible to a runner before its task executes.

### Publication sealing did not cover every specialized analysis module

The existing analysis-implementation fingerprint covered the main report/statistics path but omitted several specialized derived-analysis modules. Adding V4.7 made that incompleteness more consequential.

**Resolved:** the publication seal now fingerprints ablation, cross-artifact, epistemic, horizon, landscape, retrieval, raw/report/statistics, dashboard and publication implementations. This is broader than the minimum V4.7 change but removes an existing reproducibility hole in the touched reporting boundary.

### An intermediate publication refactor regressed verification output

An intermediate edit accidentally removed `actual_outputs` / `regenerated_outputs` from the verification result contract. CI caught the regression.

**Resolved:** the original verification API was restored before continuing, and publication regeneration tests remain green on subsequently validated commits.

## Complexity review

### Change amplification

The profile pressure vectors have one owner. CLI and desktop request profile IDs rather than copying the 15 cells. Family defaults still come from the parametric registry. Canonical metric filtering has one owner in the report layer.

### Cognitive load

The new behavior is split by abstraction:

- profile definition;
- experiment execution;
- generic experiment annotation;
- dedicated response analysis;
- thin application controls.

No family generator or deterministic grader needs to know that it is running inside a horizon experiment.

### Hidden dependencies

The experiment depends only on existing Frontier v4 task IDs and pressure dataclasses. Task/family mismatches are validated when the profile is built. Unknown profile IDs and mismatched task selections fail before execution.

### Special cases

The executor does not contain harness-specific logic. Single versus multiple configured runners is the only orchestration branch, reusing the existing matched scheduler for the latter.

### Suite semantics

Experiment-profile modules are explicitly non-semantic for `suite_revision`, while the profile digest identifies experiment design. Regression tests protect both sides of this boundary.

## Validation coverage

Deterministic tests cover, among other cases:

- profile construction, coordinate validation and stable profile identity;
- canonical task/family mapping;
- constant task seed across pressure cells in one repeat;
- exact pressure vectors differing across cells;
- CLI pressure-profile selection and rejection of incompatible options;
- desktop catalog/profile exposure and profile-owned task selection;
- single- and multi-runner orchestration reuse;
- response-curve ordering, missing-cell detection, parameter mismatch detection and seed-drift detection;
- unsupported cells remaining visible without being counted as successful observations;
- baseline-only horizon analysis when curated skills also exist;
- horizon isolation from the ordinary leaderboard and generic statistics;
- experiment-context persistence before task execution;
- separation of horizon orchestration from Frontier suite semantic fingerprints;
- publication sealing of all specialized derived-analysis implementations.

## Deliberate deferrals

### No adaptive search for a “maximum solvable pressure”

Deferred intentionally. Binary search or adaptive pressure selection would make the set of later observations depend on earlier model outcomes, complicating cross-harness and longitudinal comparability. A fixed seeded profile is preferable until there is empirical evidence that adaptive testing is worth the additional protocol complexity.

### No single cross-family difficulty index

Not planned for this milestone. The measured coordinates have different semantics across families. Collapsing them into one number would create a strong latent assumption unsupported by the benchmark.

### No dedicated graphical horizon chart yet

`summary.json` contains the exact response curves and the desktop can launch the profile, while the existing generated dashboard continues to show canonical pressure tables. A separate chart is a presentation enhancement rather than a correctness dependency. It is deferred until real multi-repeat data establishes which visualization is useful; implementing a chart now would risk hard-coding an unvalidated interpretation of path order.

### No hidden profile-wide timeout

The existing `total_timeout` remains a per-runner active-execution budget and resets for each cell because each cell is an ordinary isolated run. This is documented rather than silently changing timeout semantics. A profile-wide budget can be added later as an explicit separate control if operational runs demonstrate a need.

## Review conclusion

V4.7 adds a new experimental dimension without duplicating task semantics or creating another runner. The review found and removed four important boundary problems: pressure-run leaderboard contamination, derived-statistics contamination, post-hoc-only experiment provenance and incomplete analysis-code publication sealing.

The resulting design keeps canonical Frontier v4 capability results separate from benchmark-owned pressure experiments, while preserving exact experiment identity and deterministic family grading. No known material ownership leak, harness-specific workaround, duplicated pressure source of truth or hidden LLM-judge dependency remains in the touched area.

Formal closure requires the final review commit to pass the canonical Python 3.12, 3.13 and 3.14 CI matrix with installation, compileall, Ruff and pytest observed green. Only then should V4.8 begin.
