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

### What

Phase A — canonical per-task behavior metrics — **DONE (2026-08-27)**:

- Persist assistant turns, tool calls, unique tools, structured tool errors, retries, file reads/writes, subagent starts, refusals and consecutive repeated tool-call patterns.
- Derive generic behavior only from canonical non-inferred events when used for cross-harness comparison.
- Keep all behavior metrics observational and score-neutral.
- Direct tests cover canonical/non-inferred filtering, profile separation, persisted behavior reuse and unavailable/non-comparable exclusion.

Phase B — reporting — **DONE (2026-08-27)**:

- Aggregate behavior metrics by harness/model/execution fingerprint.
- Publish `agent_behavior_efficiency` in `summary.json`.
- Render a dedicated dashboard section for turns, tool calls, tool diversity, structured tool errors, retries, consecutive repetition, file activity, subagents and refusals.
- Treat missing structured telemetry as unavailable rather than as zero activity.
- Keep trajectory reporting separate from deterministic capability, reliability, inference efficiency and resource efficiency.

Phase C — replay readiness — **DONE (2026-08-27)**:

- Preserve adapter timestamps and structural identifiers such as tool `call_id` when supplied.
- Persist an explicit observation `sequence` for every trajectory event so replay order never has to be inferred from timestamps that may collide or be absent.
- Never mutate adapter/caller-owned event dictionaries while normalizing persisted trajectory events.
- Keep event payloads structural and bounded; a replay viewer itself is intentionally not part of this milestone.

### Completion criteria

- Supported harnesses expose reliable structured trajectory telemetry where their native interfaces provide it; unavailable/partial telemetry remains explicit.
- Summary/dashboard make PASS-with-clean-trajectory distinguishable descriptively from PASS-with-high-retry/error/repetition trajectories without changing capability score.
- No generic heuristic labels actions as useful, destructive, irrelevant or recovered without deterministic evidence.
- Event ordering is replay-safe and adapter timestamps/identifiers remain intact.

### Validation and strategic review

- CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest after Phase A and again after Phases B/C.
- A regression test exposed a test-only namespace collision between the historical `aios_bench` compatibility alias and the canonical `core.benchmark` namespace; the new reporting test was corrected to use only the canonical namespace rather than adding production workarounds.
- Reporting ownership is now clearer: `behavior_metrics.py` owns generic behavioral derivation/aggregation, `report.py` publishes canonical derived analysis, and `dashboard.py` renders it.
- During the milestone review, M2's previously missing `summary.json` resource aggregation was corrected instead of duplicating resource aggregation in the dashboard.

## M4 — Deterministic behavioral oracle framework — ACTIVE

### Why

Generic telemetry can count actions but cannot legitimately decide whether an action was correct. Benchmarks such as Terminal-Bench, DeepSWE and Frontier-Bench show that strong task-specific verification is what turns trajectories into scientific evidence.

### What

Introduce task-owned behavioral assertions separate from generic event statistics. Candidate primitives:

- `required_state`: facts that must hold at completion.
- `preserved_state`: unrelated state that must remain unchanged.
- `forbidden_state`: side effects that must never appear.
- `restart_survival`: fix remains correct after restart/reload/reconstruction.
- `decoy_untouched`: explicitly irrelevant bait must remain untouched where scientifically justified.
- `required_evidence`: deterministic evidence/probe must be produced or observable.
- `coverage_set`: required elements with precision/recall-style scoring.

Avoid encoding one exact solution path unless the task genuinely requires it; grade observable semantics rather than imitation of a reference patch.

### Completion criteria

- Behavioral oracle definitions are validated and cannot access mutable agent-owned grader state.
- Positive and preservation/negative assertions are both supported.
- Oracle results are persisted independently from generic telemetry.

## M5 — Adversarial tool selection and branching — PLANNED

### Why

MCP-Atlas demonstrates that realistic tool use requires selecting among plausible distractors, parameterizing calls correctly and adapting future steps to returned state. A benchmark that exposes only the necessary tool mainly tests execution, not tool selection.

### What

- Add task families with relevant and plausible irrelevant tools.
- Include deterministic branching based on runtime observations.
- Record wrong-tool calls, parameter failures, premature stopping and recovery only where task semantics make them deterministically identifiable.
- Vary tool topology across filesystem, shell, structured data/API, search/docs and development tooling.

### Completion criteria

- At least one family requires correct tool discovery and conditional branching.
- Distractors are realistic but do not create ambiguity in the ground truth.

## M6 — Causal state, persistence and belief revision — PLANNED

### Why

ARC-AGI-3 highlights adaptive intelligence: observe, hypothesize, experiment, update a world model and revise beliefs when evidence contradicts expectations. In software systems the analogue is understanding source-of-truth, generated state, runtime state, caches and persistence.

### What

- Build tasks with explicit causal structure: source-of-truth -> generated artifact -> runtime behavior.
- Make superficial fixes pass temporarily but fail after deterministic restart/reconstruction.
- Add active-investigation tasks where static file inspection is insufficient and runtime probing is needed.
- Add belief-revision traps: early evidence supports a plausible hypothesis, later evidence falsifies it, and the correct solution requires updating the model of the system.
- Measure milestones such as steps to first relevant evidence, root-cause evidence, correct fix and verification only when evidence nodes are deterministically defined.

### Completion criteria

- At least one task distinguishes symptom patching from causal repair.
- At least one task requires runtime experimentation.
- Contradictory evidence cannot be bypassed by a hard-coded one-step solution.

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

Use empirical pass distributions to flag:

- saturated tasks;
- useful frontier tasks;
- extreme/broken-candidate tasks.

A 0% pass rate is not automatically desirable; it may indicate an impossible or defective task.

### Completion criteria

- Task promotion/revision rules are documented and enforced by tooling where practical.
- Historical results remain tied to the exact task/oracle semantics that produced them.

## M13 — Multi-dimensional comparison UX — PLANNED

### Why

A single composite score hides trade-offs. Users need to compare capability, reliability, trajectory quality, inference speed and hardware cost independently.

### What

Expose head-to-head views for:

- deterministic capability;
- reliability/repeats and confidence intervals;
- failure taxonomy;
- trajectory behavior;
- prompt/decode efficiency;
- client resource cost;
- server/model resource cost;
- robustness/pressure response.

Prefer Pareto-style interpretation to arbitrary weighted composite scores.

### Completion criteria

- Dashboard/head-to-head never implies that a faster or smaller model is more capable solely because of efficiency.
- Comparability warnings remain visible when profiles differ materially.

## Current execution order

1. Implement M4 deterministic behavioral oracle framework.
2. Build one M6 causal/persistence pilot task using M4.
3. Build one M5 adversarial tool-selection pilot family.
4. Add M7 coverage scoring.
5. Add M8 pristine long-horizon verification.
6. Add M9 greenfield task.
7. Add M10 reference-trajectory efficiency once real trajectory data exists.
8. Formalize M12 QA/aging before expanding the catalog aggressively.
9. Expand M13 comparison UX as each new dimension becomes stable.

M11 progressive learning remains deferred until the underlying state and replay semantics are mature.

## Milestone update protocol

At every completed step:

- update the relevant status and checklist in this file;
- record any architectural deviation or justified deferral;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a milestone strategic review for ownership, duplication, hidden dependencies, change amplification, error paths and benchmark-semantic drift;
- do not mark work `DONE` based only on implementation without observed validation.
