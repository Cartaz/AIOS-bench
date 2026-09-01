# Strategic Review — Frontier V4.11 Learning & Transfer

**Status:** CLOSED, contingent on the required branch-head CI run succeeding after this review is committed.

## Scope reviewed

V4.11 adds one longitudinal parametric family, `learning_transfer`, and three canonical tasks: acquisition, transfer, and repair. The review covers state ownership, materialization boundaries, verifier design, task dependencies, seed semantics, catalog/UI exposure, benchmark-health integration, and interaction with existing experiment profiles.

## Complexity review

### Ownership

Ownership is clear. The family owns generation and deterministic grading. `ParametricTaskMaterializer` continues to own workspace preparation and benchmark-managed cross-task persistence. The scheduler and runner continue to own execution/lifecycle. No learning-specific state was added to the controller, scheduler, harness adapters, frontend, or runner.

Only `skills/` is persistent for `learning_transfer_v1`. Demonstrations, datasets, schema transitions, validation cases, tools, and reports remain task-local. This prevents hidden dependency on prior task workspaces and keeps the reusable learned artifact explicit.

### Reuse of V4.10 persistence

V4.11 is the first independent consumer of the generic family-declared persistence contract introduced in V4.10. It registers `persistent_paths=("skills",)` and uses a shared `state_scope`; no learning task IDs or paths were added to `ParametricTaskMaterializer`.

This is a positive strategic result: the V4.10 abstraction reduced change amplification for the next longitudinal capability rather than merely moving a memory-specific special case behind a new name.

### Seed semantics

A potential hidden dependency was identified during design: ordinary Frontier v4 gives each task a distinct derived seed. Regenerating the procedure from the transfer/repair seed would create a different skill and invalidate the longitudinal claim. The implementation therefore treats persisted state as canonical in warm phases and uses seed-derived fallback only for standalone health/preflight materialization.

A regression test explicitly verifies the chain under distinct task seeds.

### Identifiability

The first acquisition design allowed multiple canonical procedures to reproduce the demonstrations for a material fraction of sampled seeds. That would make exact-rule grading invalid. The design was replaced before commit with an explicit teaching set plus included-record evidence, and generation now enumerates the full canonical hypothesis space and fails closed unless exactly one skill is compatible.

This removes ambiguity at its source rather than adding grader exceptions for alternative answers.

### Grader depth and security

The learned artifact is declarative JSON. The benchmark-owned application tool implements the procedure contract; the verifier does not execute arbitrary code authored by the agent. Strict grading checks the exact reusable skill, protected source integrity, exact report, and successful deterministic reproduction of the report from the persisted skill.

This keeps Learning & Transfer distinct from future software-repair/program-synthesis tasks and avoids unnecessary execution risk in the verifier.

### Duplication and layer boundaries

Filtering and signed contribution logic have one family implementation path used by both demonstration evidence and aggregate results. Family dispatch remains through the existing registry. No new runner, event bus, service abstraction, runtime server, or frontend state was introduced.

The family source is larger than earlier generators because it owns dataset construction, identifiability checking, three phase materializers, and grading. Splitting it now would mostly expose internal data contracts between shallow modules; the current single deep family module is preferable until a second consumer emerges.

### Profiles and UI

`aios_index_v1` is deliberately unchanged. Adding a new high-value-looking task without empirical discrimination/time data would silently redefine the compact comparison series. Generated long-horizon pressure is also unchanged.

No dedicated CLI or GUI pressure editors were added. Effective learning coordinates are still recorded through `normalize_parameters()`. Editor/flag surface is deferred until real sweeps show which coordinates are operationally useful.

## Validation observed before closure commit

GitHub Actions run `33474557843` on V4.11 functional HEAD succeeded on Python 3.12, 3.13 and 3.14. Every matrix job passed installation, Bubblewrap verification, compile, Ruff, and pytest. Python 3.12 reported 458 passing tests.

Benchmark Health remains catalog-wide, so the same run exercised seeded determinism/diversity, oracle hiding/schema, protected-source integrity, instruction/verifier agreement, untouched failure, golden success on two seeds, missing-artifact near miss, and grader runtime bounds for all 16 active Frontier v4 tasks.

## Remaining deliberate deferrals

- No empirical reweighting or inclusion in AIOS-Index until real model/harness runs quantify discrimination, redundancy, stability, runtime and correlation with the full suite.
- No Learning-specific pressure sweep UI/CLI until those coordinates prove useful operationally.
- No partial Learning score is promoted to a canonical capability score; strict task success remains binary and deterministic.
- Native CachyOS/KDE interactive execution is not claimed by CI; the existing offscreen/native-library checks remain the observed automated validation boundary.

## Milestone conclusion

No important architectural drift or tactical special case remains in the touched area. State ownership is explicit, warm-state isolation is reused rather than reimplemented, independent task seeds cannot redefine learned state, acquisition ambiguity fails closed, and the grader verifies reusable procedure correctness rather than output-only success.

V4.11 may be reported as closed only after the CI run triggered by this closure commit finishes successfully.
