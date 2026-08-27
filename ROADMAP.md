# AIOS-Bench roadmap

This is the canonical benchmark-evolution plan. Update it after every validated step. A milestone is `DONE` only after implementation, tests/CI, documentation where needed, and a strategic review of ownership, complexity, error paths and benchmark semantics.

Status legend: `DONE`, `ACTIVE`, `PLANNED`, `DEFERRED`.

## Design principles

AIOS-Bench measures agentic systems, not only prompt quality. Deterministic capability correctness remains separate from reliability, trajectory behavior, inference/runtime efficiency, hardware cost and robustness. No LLM judge participates in scoring. Generic telemetry may describe actions, but semantic claims such as irrelevant action, destructive edit, causal repair or correct recovery require deterministic task evidence.

Historical suites are frozen scientific artifacts. New task/oracle semantics require new revisions. Verification should be substantially cheaper than solving, missing telemetry must remain explicit, and materially different execution profiles must never be silently compared.

## M0 — Reproducibility and run comparability — DONE

Canonical manifests, semantic fingerprints, suite/task revisions, model/runtime identity and comparability checks are persisted so materially different runs are not silently treated as equivalent.

## M1 — Resource telemetry foundation — DONE

Client/harness and inference-server/model costs are measured separately. Client process-tree CPU/RAM and Linux DRM GPU/VRAM attribution are separated from host totals. An optional read-only server resource agent provides server process-tree and host telemetry. Sampling is fail-open and score-neutral.

## M2 — Resource reporting — DONE

`summary.json` and dashboard expose canonical `resource_efficiency`, including mean task peaks and worst observed peaks rather than nonsensical sums across tasks. Capability and resource cost remain separate dimensions.

## M3 — Agentic trajectory telemetry — DONE

Canonical structured trajectory events expose turns, tool calls/diversity/errors, retries, file activity, subagents, refusals and consecutive repetition where harness telemetry supports them. Event `sequence` makes replay ordering explicit. `agent_behavior_efficiency` is published in summary/dashboard and remains score-neutral.

## M4 — Deterministic behavioral oracle framework — DONE

Task-owned `behavioral_acceptance` supports `required_state`, `forbidden_state`, `preserved_state`, `decoy_untouched` and `required_evidence`. Paths are workspace-confined, preservation baselines are benchmark-owned SHA-256 snapshots captured after materialization and before execution, and results are persisted independently as `behavioral_evaluation`. `coverage_set` was intentionally deferred to M7.

## M5 — Adversarial tool selection and branching — DONE

### Why

MCP-Atlas shows that realistic tool use requires choosing among plausible alternatives, passing correct parameters and adapting later actions to runtime observations. Giving an agent only the necessary tool mostly measures execution, not selection.

### Implemented

- Added parametric `tool_branching` and Frontier v4 task `tool_use_branching_001`.
- Materialize benchmark-owned tools for live case inspection, billing/access branch lookups and 2–5 plausible cache/legacy/metrics/archive/directory distractors.
- A stateful loopback service makes the correct branch depend on the live inspection result.
- Branch lookup requires the live case id; incorrect parameters return a deterministic recoverable error.
- Calling the wrong branch or a non-authoritative distractor contaminates the session, so brute-force fan-out cannot obtain a valid receipt chain.
- The task prompt identifies differing authority/freshness but does not prescribe the exact command sequence.
- Successful authoritative calls return deterministic branch-specific receipts; the final artifact must match the exact expected receipt chain.
- Benchmark-owned tool files and README are hash-protected from mutation.
- Runtime-service startup is generalized in `ParametricTaskMaterializer`, bounded to five seconds, and all services share deterministic bounded shutdown.
- Server state transitions are serialized with a lock so concurrent calls cannot race `inspected`/`tainted` state.
- Catalog, GUI, CLI, same-seed materialization and parametric golden/no-op validation include the new family.
- During review, a real compatibility-wrapper regression was found: v3/v4 constructors did not forward resource telemetry options supplied by the CLI. Both wrappers now forward `server_resource_url` and `resource_poll_interval`, with direct regression tests.

### Validation and strategic review

- Tests cover deterministic generation, authoritative happy path, distractor contamination, wrong-branch rejection, wrong-id rejection and recovery from a corrected parameter.
- No harness-specific textual parser or LLM judge determines which tool was correct; task semantics live in benchmark-owned fixtures and verifier logic.
- Semantic ownership remains clear: the parametric family owns task truth, the loopback service owns mutable session state, the materializer owns subprocess lifecycle, and the checker owns final deterministic verification.
- Receipts follow the current Frontier workspace trust model. They are not claimed to be cryptographic anti-cheat against an agent intentionally escaping the workspace and reading benchmark internals; stronger contamination/anti-cheat hardening remains M12.
- Final CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## M6 — Causal state, persistence and belief revision — DONE

### Implemented

- `causal_gateway`: source template -> generated runtime -> health behavior. The verifier reconstructs runtime from the source-of-truth so symptom-only runtime edits fail, while unrelated state/tooling/decoys are protected.
- `runtime_investigation`: static documentation contains a deterministic stale hypothesis while the actual live lane exists only behind a benchmark-owned read-only loopback probe. Exact probe evidence is required and only the observed live lane may be changed.
- Dynamic runtime fixtures have bounded startup/shutdown and are always cleaned in `FrontierRunner.run_task()` via `finally`, including exception paths.

Final CI was observed green on Python 3.12, 3.13 and 3.14.

## M7 — Coverage/completeness tasks — ACTIVE

### Why

WideSearch highlights that finding one correct item and finding the complete set are distinct capabilities. Agents can produce locally correct fixes while silently missing affected call sites, configurations or records.

### What

- Add a dedicated coverage evaluation layer rather than overloading generic behavioral predicates.
- Generate a hidden finite ground-truth target set and realistic false-positive opportunities.
- Persist deterministic true-positive, false-positive, false-negative, precision, recall and completion metrics.
- Keep strict capability correctness: full completion remains required for task PASS; partial coverage is descriptive continuous evidence, not a weakened pass threshold.
- Build one Frontier v4 pilot requiring migration of every affected active artifact while preserving plausible but out-of-scope files.

### Completion criteria

- Ground truth is benchmark-owned and outside the agent workspace.
- A partial solution produces useful precision/recall metrics while still failing strict capability correctness.
- Brute-force modification of plausible false positives is penalized deterministically.
- Coverage metrics are persisted in the canonical task evaluation/result path without introducing a second scoring system.

## M8 — Long-horizon pristine verification — PLANNED

Add a small number of substantial multi-file/multi-module tasks. Extract the agent artifact/patch and verify it from pristine benchmark-controlled state with target and preservation/regression checks. At least one task must require coordinated edits across multiple modules.

## M9 — Greenfield repository construction — PLANNED

Add a very small family starting from an empty/minimal repository, with deterministic hidden tests across architecture, API, persistence, validation and integration. Continuous hidden-test coverage may be reported, but completion remains deterministic and reference-solution independent.

## M10 — Reference trajectory and adaptive efficiency — PLANNED

For selected tasks, curate semantic reference milestones/efficient trajectories. Compare successful agent effort descriptively without turning raw command count into correctness or penalizing legitimate extra verification.

## M11 — Progressive environments and within-run learning — DEFERRED

Later evaluate reusable skill acquisition across related levels while explicitly separating persistent agent memory from workspace leakage. Resume only after trajectory, causal-state and cross-task ownership are mature.

## M12 — Task QA, aging, contamination and anti-cheat — PLANNED

Formalize task promotion/revision lifecycle: static validation, reference solve, no-op, cheat/adversarial checks, preservation/regression, multi-agent pilots, ambiguity/oracle review and stable promotion. Track revisions, audits, known issues, exposure/contamination risk and empirical saturation. This milestone also owns stronger isolation/anti-cheat work beyond the current workspace trust model.

## M13 — Multi-dimensional comparison UX — PLANNED

Expose deterministic capability, reliability/confidence intervals, failure taxonomy, trajectory behavior, inference speed, client resource cost, server/model resource cost and robustness/pressure response side-by-side. Prefer Pareto-style interpretation over arbitrary composite weighting and keep comparability warnings visible.

## Current execution order

1. Complete M7 coverage/completeness scoring and one pilot task.
2. Add M8 pristine long-horizon verification.
3. Add M9 greenfield construction.
4. Add M10 reference-trajectory efficiency once real trajectory data exists.
5. Formalize M12 QA/aging/contamination before aggressive catalog expansion.
6. Expand M13 UX as each dimension stabilizes.

M11 remains deferred.

## Milestone update protocol

At every completed step:

- update status and implementation notes here;
- record architectural deviations and justified deferrals;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a strategic review for ownership, duplication, hidden dependencies, change amplification, races, shutdown/error paths and semantic drift;
- never mark work `DONE` based only on implementation without observed validation.
