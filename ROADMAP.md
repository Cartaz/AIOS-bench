# AIOS-Bench roadmap

This roadmap is the canonical plan for benchmark evolution. Update it at every completed step. Do not mark a milestone complete until its implementation is integrated, tested, documented where needed, and the touched area has passed a strategic design review.

Status legend: `DONE`, `ACTIVE`, `PLANNED`, `DEFERRED`.

## Design principles

AIOS-Bench measures agentic systems, not only model prompt quality. Capability correctness remains deterministic and separate from reliability, trajectory efficiency, runtime efficiency, resource cost and robustness. No LLM judge is used for scoring. Generic telemetry may describe behavior, but task-specific claims such as "irrelevant action", "destructive edit", "correct recovery" or "causal understanding" require deterministic task evidence.

The benchmark should remain reproducible, cheap to verify relative to solving, resistant to contamination and benchmark aging, and explicit about run comparability. Historical suites remain frozen scientific artifacts; new semantics require new suite/task revisions rather than silently rewriting old results.

## M0 — Reproducibility and run comparability — DONE

### Why

A numerical comparison is meaningless when runs differ in reasoning mode, context, sampling, harness, suite revision, model identity or relevant runtime configuration.

### What

- Persist canonical execution manifests and semantic fingerprints.
- Record suite/task revisions, model/provider identity, inference configuration and environment identity.
- Fail closed or warn when strict comparison requirements are not met.
- Keep historical suite revisions identifiable.

### Completion criteria

- Run metadata is sufficient to determine whether two observations are scientifically comparable.
- Comparison/reporting never silently treats materially different execution profiles as identical.

## M1 — Resource telemetry foundation — DONE

### Why

Local-agent usefulness depends on both capability and hardware cost. Client-side harness cost and inference-server/model cost are different quantities and must not be conflated.

### What

- Sample AIOS-Bench/harness process-tree CPU and RAM.
- On Linux DRM, attribute GPU/VRAM to the process tree when available.
- Keep client host-total GPU/VRAM separate from process-attributed values.
- Add optional read-only inference-server resource agent without SSH or arbitrary command execution.
- Record server process-tree RAM/VRAM/GPU separately from llama.cpp token/throughput metrics.
- Preserve baseline, mean, p95, peak and peak delta where meaningful.
- Make resource telemetry fail-open and score-neutral.

### Completion criteria

- Missing/unsupported telemetry is represented as unavailable, never fake zero.
- Telemetry failure cannot turn an otherwise valid benchmark task into a task failure.
- Client and server cost remain distinguishable even when both run on the same machine/GPU.

## M2 — Resource reporting — DONE

### Why

Raw telemetry is not useful if users must inspect task JSON manually. Reporting must expose cost without collapsing it into capability score.

### What

- Aggregate resource telemetry by harness/model/execution profile.
- Report mean task peak and worst observed peak rather than summing RAM/VRAM across tasks.
- Expose separate dashboard sections for client/harness cost and inference-server/model cost.
- Keep inference throughput and resource consumption as separate dimensions.
- Publish the same canonical `resource_efficiency` aggregation in `summary.json`; the dashboard consumes that derived data rather than maintaining a second resource-reporting path.

### Completion criteria

- `summary.json` and dashboard expose resource-efficiency data.
- Capability score is unchanged.

## M3 — Agentic trajectory telemetry — DONE

### Why

Two agents can both pass a task while one reaches the solution directly and the other loops, retries, makes tool errors or recovers from self-inflicted mistakes. Pass/fail alone hides operational quality.

### Implemented

- Persist assistant turns, tool calls, unique tools, structured tool errors, retries, file reads/writes, subagent starts, refusals and consecutive repeated tool-call patterns.
- Derive generic behavior only from canonical non-inferred events when used for cross-harness comparison.
- Publish `agent_behavior_efficiency` in `summary.json` and dashboard, score-neutral.
- Preserve adapter timestamps and structural identifiers when supplied.
- Persist explicit event `sequence` so replay order never depends on timestamps.
- Keep missing/partial structured telemetry explicit rather than inventing zero activity.

### Validation and strategic review

- CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.
- Reporting ownership is separated: behavioral derivation/aggregation, canonical report generation and rendering remain distinct.
- Test-only `aios_bench` compatibility namespace collisions are handled in tests, not with production workarounds.

## M4 — Deterministic behavioral oracle framework — DONE

### Why

Generic telemetry can count actions but cannot legitimately decide whether an action was correct. Strong task-specific verification turns trajectories into scientific evidence without an LLM judge.

### Implemented

- Added task-owned `behavioral_acceptance`, deliberately separate from capability `acceptance`.
- Added deterministic primitives `required_state`, `forbidden_state`, `preserved_state`, `decoy_untouched` and `required_evidence`.
- Restrict state checks to safe relative workspace paths; reject path traversal and ambiguous predicates at catalog load.
- Capture preservation/decoy baselines after benchmark materialization and before agent execution.
- Compare preserved files by benchmark-owned existence/type/SHA-256 snapshots rather than mutable agent-provided metadata.
- Match required structured evidence by event type, optional source and nested deterministic data subset.
- Persist results as independent `behavioral_evaluation` and keep them score-neutral.
- Include behavioral catalog definitions and evaluator source automatically in suite revision fingerprints.

`coverage_set` remains intentionally deferred to M7; higher-level semantics should not leak into the base oracle module.

### Validation and strategic review

- Unit, catalog and runner integration coverage validates state predicates, preservation, evidence matching, unsafe definitions, serialization and score neutrality.
- Capability PASS can remain 100/100 while an independent behavioral preservation oracle reports FAIL.
- CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## M5 — Adversarial tool selection and branching — ACTIVE

### Why

MCP-Atlas demonstrates that realistic tool use requires selecting among plausible distractors, parameterizing calls correctly and adapting future steps to returned state. A benchmark that exposes only the necessary tool mainly tests execution, not tool selection.

### What

- Add task families with relevant and plausible irrelevant tools.
- Include deterministic branching based on runtime observations.
- Record wrong-tool calls, parameter failures, premature stopping and recovery only where task semantics make them deterministically identifiable.
- Vary tool topology across filesystem, shell, structured data/API, search/docs and development tooling.
- Prefer benchmark-owned audited tool fixtures over harness-specific log parsing so observations remain comparable across harnesses.

### Completion criteria

- At least one family requires correct tool discovery and conditional branching.
- Distractors are realistic but do not create ambiguity in the ground truth.
- Tool-use evidence is deterministically attributable without an LLM judge or harness-specific textual heuristics.

## M6 — Causal state, persistence and belief revision — DONE

### Why

ARC-AGI-3 highlights adaptive intelligence: observe, hypothesize, experiment, update a world model and revise beliefs when evidence contradicts expectations. In software systems the analogue is understanding source-of-truth, generated state, runtime state, caches and persistence.

### Implemented

- Added the parametric `causal_gateway` pilot with source-of-truth `gateway/template.json`, generated `gateway/runtime.json`, current diagnostic evidence, historical decoys and protected unrelated state.
- The grader reconstructs runtime state from the source template itself before health verification; editing only the generated runtime therefore cannot survive verification.
- Protected healthcheck/tooling, registry, historical decoys and unrelated retention state prevent trivial grader tampering or collateral changes.
- Added deterministic negative and golden preflight witnesses for the causal family.
- Added the parametric `runtime_investigation` pilot for active investigation and belief revision.
- Static deployment documentation deterministically names a plausible but stale lane, while the actual live lane exists only behind a benchmark-owned read-only loopback runtime probe.
- The task must save the exact runtime observation, repair only the observed live lane and preserve every inactive lane and historical document.
- A correct-looking route edit without runtime evidence fails; modifying inactive lanes fails even with valid evidence.
- Added a small benchmark-owned `GET /state` probe server with no arbitrary command execution or external network access.
- Dynamic runtime fixtures are owned by `ParametricTaskMaterializer`; startup is bounded, shutdown uses bounded terminate/wait/kill, and `FrontierRunner.run_task()` guarantees materializer cleanup with `finally` even on task failure.
- Ephemeral `runtime/endpoint.json` is excluded from same-seed workspace byte comparisons; seeded semantic state and oracle digests remain deterministic.
- Frontier v4 parametric validation now exercises four families: expense report, config traversal, causal gateway and runtime investigation.

### Completion criteria

- Symptom patching vs causal repair: satisfied by `autonomy_causal_gateway_001`.
- Runtime experimentation: satisfied by `autonomy_runtime_investigation_001`.
- Contradictory evidence cannot be bypassed by a one-step static edit: exact live probe evidence and active-lane-only mutation are verified deterministically.

### Validation and strategic review

- Direct tests cover deterministic generation, persistent source repair, rejection of runtime-only repair, protected-state tampering, stale-vs-live contradiction, required probe evidence, inactive-lane preservation and runtime process cleanup.
- A regression test verifies probe cleanup even when task execution raises after materialization.
- The first version of that regression test exposed the historical `aios_bench`/`core.benchmark` test namespace alias; the test was corrected to patch the module that actually owns `run_task`, with no production workaround.
- Final CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.
- Runtime fixture lifecycle complexity is contained in the materializer rather than spread through task runners or graders.
- The live probe is intentionally an evaluation fixture, not a security boundary. Public-benchmark contamination/derivation risks remain a documented concern for M12 rather than being misrepresented as cryptographic anti-cheat.

## M7 — Coverage/completeness tasks — PLANNED

### Why

WideSearch shows that finding one correct item and finding all correct items are different abilities. Coding agents often fix the first call site while missing the rest.

### What

- Add tasks requiring discovery/modification of a complete finite set.
- Score atomic precision, recall and completion deterministically.
- Include realistic false-positive opportunities so brute-force modification is not rewarded.

Candidate domains:

- migrate all deprecated configuration keys;
- update every affected call site;
- identify all vulnerable instances;
- reconcile all entries matching a rule.

### Completion criteria

- Ground-truth sets are generated/hidden from the agent and cheaply verifiable.
- Partial completion produces informative continuous metrics without weakening correctness semantics.

## M8 — Long-horizon pristine verification — PLANNED

### Why

DeepSWE demonstrates that large multi-file work exposes consistency failures that short tasks cannot, and that verification is stronger when executed outside the mutable agent environment.

### What

- Add a small number of substantial multi-file/multi-module tasks.
- Extract the agent artifact/patch and verify it in a pristine benchmark-controlled environment.
- Include regression/preservation checks, not only target-feature tests.
- Track long-output/reasoning loops, context pressure and recovery through trajectory telemetry.

### Completion criteria

- At least one task requires meaningful coordinated edits across multiple modules.
- The final verifier runs from pristine benchmark-owned state and cannot be modified by the agent.

## M9 — Greenfield repository construction — PLANNED

### Why

NL2Repo tests architectural completeness rather than local patching. An agent may be strong at repairs while weak at designing a coherent application from a specification.

### What

- Add a very small greenfield family starting from an empty/minimal workspace.
- Use large deterministic hidden test suites across API, persistence, validation and integration behavior.
- Report continuous test coverage alongside strict completion criteria.

### Completion criteria

- At least one task requires architecture, implementation and integration rather than editing an existing scaffold.
- Verification remains deterministic and reference-solution independent.

## M10 — Reference trajectory and adaptive efficiency — PLANNED

### Why

ARC-AGI-3's action-efficiency framing suggests comparing successful behavior to a meaningful reference. Raw tool-call counts alone are not quality metrics because additional verification can be beneficial.

### What

- For selected tasks, curate a reference-efficient trajectory or reference milestone path.
- Compare agent effort to the reference descriptively, never as correctness replacement.
- Prefer semantically meaningful milestones/actions over a naive minimum command count.
- Explore metrics for exploration efficiency and steps-to-evidence.

### Completion criteria

- Reference trajectories are clearly labeled as efficiency baselines, not mandatory solution paths.
- An agent is never penalized for legitimate extra verification merely because it uses more commands.

## M11 — Progressive environments and within-run learning — DEFERRED

### Why

ARC-AGI-3 measures whether an agent acquires reusable skills across related levels. This is scientifically valuable but changes benchmark semantics substantially and should not be introduced before trajectory/replay and causal-state foundations are mature.

### What

- Design small environment families whose later levels reuse and perturb earlier rules.
- Measure whether exploration cost decreases as the agent learns.
- Distinguish persistent agent memory from accidental workspace leakage.

### Exit from deferral

Proceed only after M3, M4 and M6 are stable and the ownership of cross-task state is explicit.

## M12 — Task QA, aging and contamination management — PLANNED

### Why

Terminal-Bench 2.1, SWE-bench Verified and Frontier-Bench show that benchmark tasks themselves age, contain oracle defects and become contaminated or over-optimized. A benchmark is not finished when its first test suite passes.

### What

For new task/revision promotion, require an auditable lifecycle:

1. static validation;
2. reference solve;
3. no-op validation;
4. cheat/adversarial validation;
5. preservation/regression validation;
6. multi-agent pilot runs;
7. ambiguity/oracle review;
8. stable promotion.

Track metadata such as task revision, oracle revision, last audit date, known issues and exposure/contamination risk where practical.

Use empirical pass distributions to flag saturated tasks, useful frontier tasks and extreme/broken-candidate tasks. A 0% pass rate is not automatically desirable; it may indicate an impossible or defective task.

### Completion criteria

- Task promotion/revision rules are documented and enforced by tooling where practical.
- Historical results remain tied to the exact task/oracle semantics that produced them.

## M13 — Multi-dimensional comparison UX — PLANNED

### Why

A single composite score hides trade-offs. Users need to compare capability, reliability, trajectory quality, inference speed and hardware cost independently.

### What

Expose head-to-head views for deterministic capability, reliability/repeats and confidence intervals, failure taxonomy, trajectory behavior, prompt/decode efficiency, client resource cost, server/model resource cost and robustness/pressure response. Prefer Pareto-style interpretation to arbitrary weighted composite scores.

### Completion criteria

- Dashboard/head-to-head never implies that a faster or smaller model is more capable solely because of efficiency.
- Comparability warnings remain visible when profiles differ materially.

## Current execution order

1. Build and validate one M5 adversarial tool-selection/branching pilot family.
2. Add M7 coverage scoring.
3. Add M8 pristine long-horizon verification.
4. Add M9 greenfield task.
5. Add M10 reference-trajectory efficiency once real trajectory data exists.
6. Formalize M12 QA/aging before expanding the catalog aggressively.
7. Expand M13 comparison UX as each new dimension becomes stable.

M11 progressive learning remains deferred until the underlying state and replay semantics are mature.

## Milestone update protocol

At every completed step:

- update the relevant status and checklist in this file;
- record any architectural deviation or justified deferral;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a milestone strategic review for ownership, duplication, hidden dependencies, change amplification, error paths and benchmark-semantic drift;
- do not mark work `DONE` based only on implementation without observed validation.
