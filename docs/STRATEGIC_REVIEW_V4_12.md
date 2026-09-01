# Strategic Review — Frontier V4.12 Delegation & Reconciliation

**Status:** CLOSED, contingent on the required branch-head CI run succeeding after this review is committed.

## Scope reviewed

V4.12 adds one canonical Tier-5 task, `subagents_reconcile_001`, one parametric family, `delegation_reconciliation`, and one generic evaluator check, `structured_delegation`. The review covers task count/runtime tradeoffs, harness capability ownership, event normalization, deterministic reconciliation, benchmark-health integration, privacy/observability boundaries, catalog exposure and interaction with existing profiles.

## Complexity review

### Task granularity

The V3 suite contains three subagent tasks with overlapping capability claims. Reproducing all three in V4 would increase run time and apparent coverage without adding three independent constructs. V4.12 therefore uses one stronger task combining two orthogonal requirements: observable native delegation and deterministic evidence reconciliation.

This is a deliberate complexity/runtime reduction. Frontier v4 grows from 16 to 17 canonical tasks rather than 19, while gaining one new family and one new verified orchestration capability.

### Ownership and layer boundaries

Ownership remains explicit:

- `delegation_reconciliation` owns generated evidence, pressure coordinates, oracle construction and deterministic artifact grading;
- harness adapters/parsers own normalization of native tool/subagent telemetry into canonical events;
- the generic evaluator owns the reusable requirement that structured delegation lifecycles actually occurred;
- runner/scheduler continue to own execution and lifecycle without V4.12 special cases.

A rejected alternative was to add `events` to every parametric grader signature. That would leak one task's orchestration concern through all 13 families and increase change amplification. Keeping event verification in `evaluate_artifacts` preserves the existing deep family interface.

### Harness capability semantics

The existing `structured_subagent_events` capability is retained as the hard requirement. This is intentionally stricter than a broad native-delegation feature flag.

OpenCode, Goose, Letta, Agent Zero and Claude Code currently expose normalized non-inferred subagent lifecycle evidence. Hermes has a native delegation tool but its benchmark one-shot path does not expose structured child lifecycle events; Pi Agent likewise lacks the required observable contract. Those combinations remain `UNSUPPORTED` instead of being scored as failures or accepted on prose claims.

No V4.12 task ID is hard-coded into the harness registry or runner.

### Lifecycle verifier depth

The old V3 subagent verifier primarily counted non-inferred `subagent_start` events. V4.12 requires distinct structured IDs and matched successful start/end lifecycles. Duplicate starts cannot satisfy the requirement, inferred text evidence is ignored, and error/failed/cancelled terminal events do not count as completed delegation.

The evaluator also handles the already-normalized Agent Zero representation where bounded structured fields live below `data.payload`. This is a canonical-event shape normalization issue, not an Agent Zero-specific grading rule.

### Benchmark Health

V4.12 exposed a useful general gap: Benchmark Health materialized parametric golden events but previously discarded them because no active v4 acceptance check depended on events. The health path now forwards the events returned by every parametric golden into the ordinary evaluator for positive, near-miss and comparison-seed checks.

Existing families return an empty event list, so their semantics are unchanged. Event-dependent future tasks can now use the same health contract without another V4.12-style special case.

Synthetic golden events are benchmark self-test witnesses only. They never enter real harness trajectories.

### Generated evidence and provenance

The family centralizes status/authority/revision ranking and provenance derivation. The generator fails closed if equally top-ranked claims disagree, rather than forcing the grader to invent an arbitrary answer. Source files, scope and policy are hash-protected.

The final report is exact structured JSON rather than prose pattern matching. This keeps reconciliation deterministic and avoids an LLM judge.

### Privacy versus attribution

Canonical telemetry deliberately excludes delegated prompts, arguments and bulk subagent outputs. As a consequence V4.12 can prove that two distinct native delegations completed and that the final reconciliation is correct, but cannot prove that each child agent substantively reviewed exactly one intended stream.

Retaining child-agent payloads would increase privacy risk and bind the benchmark to harness-specific content schemas. Instrumenting benchmark-controlled per-subagent sandboxes could provide stronger attribution but would introduce substantial harness-specific orchestration complexity. Neither is justified before empirical evidence shows that lifecycle-plus-result verification is insufficient.

The limitation is therefore documented rather than hidden.

### Profiles, pressure and UI

`aios_index_v1` remains unchanged. Adding V4.12 before empirical calibration would redefine an established compact comparison series without evidence that the new task improves signal/time or reduces redundancy.

No dedicated V4.12 CLI or GUI pressure editor is added. Defaults are still normalized into execution identity through the family registry. Pressure controls remain a deliberate empirical-calibration follow-up, not a prerequisite for canonical execution.

No frontend, bridge, controller, scheduler or task-runtime changes were required.

## Validation observed before closure commit

The functional branch-head CI run following catalog-invariant alignment is required to succeed on Python 3.12, 3.13 and 3.14 before this milestone is reported as closed. The matrix must pass installation, functional Bubblewrap verification, compile, Ruff and the complete pytest suite.

The catalog-wide Benchmark Health gate must exercise all 17 Frontier v4 tasks, including V4.12's generated determinism/diversity, oracle isolation/schema, protected-source integrity, instruction/verifier consistency, untouched failure, two-seed golden success, missing-artifact near miss, grader runtime bound and the structured-delegation golden lifecycle.

## Remaining deliberate deferrals

- No AIOS-Index inclusion or reweighting until real model/harness runs quantify discrimination, redundancy, stability, runtime and full-suite correlation.
- No dedicated V4.12 pressure controls until pressure sweeps show operational value.
- No stronger per-subagent contribution attribution until a privacy-preserving, harness-neutral mechanism is justified by evidence.
- No claim of native CachyOS/KDE interactive execution from GitHub CI; the existing offscreen/native-library automated boundary remains what is observed.

## Milestone conclusion

The touched architecture remains coherent: one new family owns content semantics, one generic evaluator owns observable delegation, existing harness parsers own native event normalization, and execution infrastructure remains unchanged. The design improves the reusable health path rather than adding a task-specific workaround, reduces V3-style task duplication, and records the remaining attribution limitation explicitly.

V4.12 may be reported as closed only after the CI run triggered by the final closure commit finishes successfully.
