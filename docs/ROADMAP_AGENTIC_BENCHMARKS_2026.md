# AIOS-Bench agentic benchmark roadmap — 2026

Status: active roadmap

This document turns the 2026 benchmark review into an implementation plan for Frontier v4. It does not create a new execution engine. Frontier v4 remains the parametric, seeded suite and continues to share `FrontierRunner`, telemetry, scoring, persistence, scheduling and comparability machinery with the existing benchmark architecture.

The roadmap is deliberately capability-first rather than benchmark-copying. External benchmarks are design inputs; AIOS-Bench keeps its own invariants: local/reproducible execution, deterministic grading, hidden benchmark-owned oracles, explicit execution identity, strict comparability and no canonical LLM judge.

## Design principles

1. **Evaluate world state, not declarations.** Success means the workspace/database/artifacts are correct, not that the agent says they are correct.
2. **Hard to solve, cheap to verify.** Prefer tasks whose solution requires discovery, planning and multi-step execution but whose final state can be checked deterministically.
3. **Generated variants over fixture memorization.** New Frontier v4 families must be seeded and parameterized, with hidden oracles stored outside the agent workspace.
4. **Negative constraints are first-class.** Verifiers must detect unauthorized edits, collateral state changes, wrong-source selection and extra actions, not only missing positive outputs.
5. **Pressure coordinates describe workload.** They are observed dimensions, not assumed monotonic difficulty levels. Exact joint pressure vectors remain the unit for matched comparisons.
6. **One deep materialization interface.** New task families plug into the existing `ParametricTaskMaterializer`; do not fork runner, telemetry, scoring or persistence logic per family.
7. **Separate capability from harness advantage.** Wherever meaningful, add paired ablations for skills, tools, code execution and harness choice while keeping model identity, task seed and workload constant.
8. **Benchmark health is part of the benchmark.** Canonical tasks require deterministic self-validation, leakage checks, oracle integrity checks and version/fingerprint invalidation when semantics change.

## Research inputs

The roadmap is informed primarily by the following public benchmark ideas:

- E-Bench / E-Bench-Code: state-changing environments, information/tool gaps, deterministic state verification and reliability across repeated runs.
- AutomationBench: final-world-state evaluation and negative side-effect detection across application workflows.
- Workspace-Bench: large heterogeneous workspaces and explicit dependency graphs.
- SkillsBench: matched with-skill / without-skill evaluation and measured skill lift.
- MCP-Atlas / Toolathlon: tool discovery, schema correctness, distractor tools, recovery and long action chains.
- WideSearch / DRACO: exhaustive retrieval, completeness and provenance rather than single-answer search.
- SWE Atlas: codebase understanding, test writing and refactoring as separate software-engineering capabilities.
- SWE-Marathon: controlled long-horizon degradation rather than only short bug-fix tasks.
- BrokenArXiv: paired valid/invalid premises to distinguish useful skepticism from blanket refusal.
- Harbor-Index: a compact, high-signal subset for fast iteration.
- CritPt / SUPERChem: checkpointed, fine-grained capability diagnostics inside difficult tasks.

## Milestone V4.1 — Stateful worlds

**Goal:** introduce deterministic state-changing tasks where correctness is the final state of a synthetic operational world.

### V4.1a — Stateful world kernel

Implement a new parametric family, initially backed by SQLite because it is deterministic, inspectable, portable and available in the Python standard library.

Required design:

- generated world database under the task workspace;
- current authoritative policy/instructions separated from historical distractors;
- deterministic seed and pressure coordinates;
- hidden baseline and expected-state oracle outside the workspace;
- full final-state verification, including schema and row-set preservation;
- explicit allowed mutations for target entities;
- exact preservation of non-target entities;
- deterministic report/provenance verification;
- variant digest including all generated semantics.

Initial pressure coordinates:

- `entity_count` — number of world entities;
- `required_mutations` — number of entities that legitimately require action;
- `distractor_policies` — number of obsolete/conflicting policy files;
- `negative_constraints` — number of generated near-miss entities that must not be changed.

The first scenario is an escalation workflow over a support-ticket world. The agent must discover the current policy, update exactly the tickets that satisfy it, leave all other records and the schema untouched, and write an audit summary.

### V4.1b — World mutation API

After the state verifier is stable, add a benchmark-owned command/API surface for selected stateful scenarios. The agent should operate through narrow domain actions instead of gaining arbitrary privileged access to hidden state.

The API layer must support:

- typed action schemas;
- deterministic errors;
- idempotency semantics where relevant;
- explicit read versus write operations;
- action logging outside agent-controlled files;
- verifier-visible side effects.

Do not make API mediation a prerequisite for V4.1a: the first milestone establishes the world-state/oracle abstraction before tool enforcement.

### V4.1c — Information and tool gaps

Add generated scenarios where:

- no single file contains all required information;
- no single action completes the workflow;
- correct execution requires a dependency chain across world state, policies and tool outputs.

Add pressure coordinates only when they correspond to a concrete generated workload feature; avoid abstract “difficulty” knobs.

**Exit criteria:** at least one stateful family has deterministic same-seed reproducibility, different-seed variation, hidden-oracle isolation, positive generic-solution tests, untouched-state failures, wrong-target failures, extra-side-effect failures, schema-tamper failures and source-policy tamper failures.

## Milestone V4.2 — Workspace lineage

**Goal:** evolve `config_traversal` from a linear reference chain into generated dependency graphs.

Add a `workspace_lineage` family with a generated DAG of authoritative sources, derived artifacts, archived revisions, duplicated data and distractors.

Pressure coordinates:

- `file_count`;
- `dependency_depth`;
- `branching_factor`;
- `distractor_ratio`;
- `revision_count`;
- `file_type_count` where supported deterministically.

The hidden oracle records the canonical lineage and authoritative leaves. Scoring must distinguish wrong authority, incomplete traversal, stale revision use and correct lineage reconstruction.

**Exit criteria:** exact-DAG cells are reproducible and matched harness comparisons can be made without changing runner semantics.

## Milestone V4.3 — Harness ablations and tool recovery

### Skill ablation

Run identical task/seed/pressure cells in matched conditions:

- `no_skill`;
- `curated_skill`.

Derived reporting adds `skill_lift` without mixing different execution identities.

### Tool recovery

Add scenarios with:

- similarly named tools;
- strict typed arguments;
- irrelevant/distractor tools;
- deterministic transient failures;
- incomplete responses;
- idempotent and non-idempotent operations;
- recovery requirements.

Failure taxonomy should distinguish tool selection, schema/argument, retry-loop and recovery failures.

**Exit criteria:** paired ablations are experiment-scoped and matched on model, task, seed, variant digest and complete pressure vector.

## Milestone V4.4 — Exhaustive retrieval and provenance

Add a frozen local information corpus rather than relying on a changing live web.

The `wide_retrieval` family asks for all matching records, not one plausible answer. Canonical metrics:

- strict complete pass;
- record precision/recall/F1;
- field-level correctness;
- provenance/citation recall;
- wrong-authority and stale-source failures.

Pressure coordinates may include corpus size, duplicate rate, conflict rate, source depth and target-set size.

**Exit criteria:** canonical scoring remains deterministic and offline.

## Milestone V4.5 — Cross-artifact consistency

Generate tasks that require multiple deliverables from one source of truth, for example a machine-readable result plus a human-readable report.

Verifier requirements:

- each artifact individually correct;
- values reconcile across artifacts;
- authoritative source remains unchanged;
- no unsupported rows/claims appear;
- exact transformations are reproducible.

Do not introduce document-format dependencies until they can be validated reliably in the supported Linux environment.

## Milestone V4.6 — Epistemic twins

Generate paired scenarios with near-identical instructions:

- valid premise: the requested action is appropriate;
- corrupted premise: a plausible but false premise points toward the wrong action.

The pair must measure both sides:

- false-premise compliance;
- over-cautious refusal on the valid twin.

This prevents a trivial “always comply” or “always refuse” strategy from scoring well.

## Milestone V4.7 — Generated long-horizon pressure

Replace qualitative long-horizon labels with deliberate, generated scaling experiments where possible.

Candidate axes:

- dependency count;
- required action count;
- state-transition count;
- number of authoritative sources;
- recovery events;
- distractor volume.

Report capability response curves and exact joint cells. Do not assume monotonic difficulty from any marginal axis.

## Milestone V4.8 — Black-box reconstruction

Add a later software-engineering family where the agent receives behavior/documentation but not a reference implementation and must create a compatible implementation.

Verifier strategy:

- hidden property tests;
- generated input suites;
- transfer/generalization tests;
- no fixture-specific constants;
- optional fuzz/property expansion if deterministic and bounded.

This milestone is intentionally later because it has higher environment and runtime cost than stateful-world work.

## Milestone V4.9 — AIOS-Index and benchmark health

Create an `AIOS-Index` profile: a compact subset of high-signal task/pressure cells for routine development. It is a profile over existing canonical tasks, not a separate scoring engine.

Selection criteria:

- stable oracle;
- good model/harness discrimination;
- reasonable runtime;
- low redundancy;
- coverage across important capabilities;
- no known leakage or brittle fixture artifacts.

Add benchmark-health validation that runs independently of agent performance:

- generator determinism;
- same-seed byte-level or semantic reproducibility;
- different-seed diversity;
- oracle/workspace separation;
- golden/generic solution pass;
- untouched workspace fail where action is required;
- deliberate near-miss fail;
- source/schema integrity checks;
- timeout sanity;
- task instruction versus verifier consistency;
- semantic fingerprint invalidation tests.

## Reporting evolution

Add metrics incrementally only when the underlying event/state source is reliable.

Priority metrics:

- strict pass;
- deterministic partial score;
- pass@N;
- reliability / pass^N;
- wall time;
- token usage;
- tool-call count;
- client CPU/RAM/GPU/VRAM;
- inference-server RAM/VRAM;
- time to first action;
- repeated/no-op actions;
- useful progress before failure;
- skill lift;
- tool lift;
- code-execution lift;
- matched harness delta.

Avoid a single opaque composite score until enough empirical data exists to justify weights. Preserve the raw capability dimensions in `summary.json` and the dashboard.

## Failure taxonomy evolution

Candidate deterministic failure kinds:

- `premature_success`;
- `wrong_authority`;
- `lineage_error`;
- `incomplete_retrieval`;
- `unsafe_side_effect`;
- `tool_selection_error`;
- `tool_schema_error`;
- `recovery_failure`;
- `retry_loop`;
- `cross_artifact_mismatch`;
- `false_premise_compliance`;
- `over_cautious_refusal`;
- `verification_failure`;
- `reward_hack_attempt`.

Only promote a failure kind into canonical reporting when it can be assigned mutually exclusively or with clearly documented precedence.

## Implementation order

1. V4.1a Stateful world kernel.
2. V4.1b benchmark-owned mutation API.
3. V4.1c information/tool gaps.
4. V4.2 workspace lineage.
5. V4.3 skill ablation and tool recovery.
6. V4.4 exhaustive retrieval/provenance.
7. V4.5 cross-artifact consistency.
8. V4.6 epistemic twins.
9. V4.7 generated long-horizon pressure.
10. V4.8 black-box reconstruction.
11. V4.9 AIOS-Index and benchmark-health consolidation.

At the end of every milestone, stop feature work for a strategic review: inspect ownership, interfaces, duplicated state, special cases, dependency direction, failure paths, benchmark leakage, comparability metadata and whether the next family can be added without changing the runner. Resolve important architectural drift before continuing.
