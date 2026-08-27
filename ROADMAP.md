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

## M7 — Coverage/completeness tasks — DONE

### Why

WideSearch highlights that finding one correct item and finding the complete set are distinct capabilities. Agents can produce locally correct fixes while silently missing affected call sites, configurations or records.

### Implemented

- Added a dedicated finite-set evaluator in `coverage.py`; it owns only TP/FP/FN, precision, recall and Jaccard completion mathematics.
- Extended parametric evaluation with an optional rich-result path while preserving the historical `check_variant()` PASS/detail contract for existing callers.
- `parametric_reference` persists optional task-owned metrics inside the canonical deterministic `evaluation.results` entry; capability acceptance scoring remains unchanged.
- Added parametric `coverage_migration` and Frontier v4 `tool_use_coverage_001`.
- The generated workspace contains an authoritative runtime index, affected loaded fragments, already-current loaded fragments and retired historical files carrying plausible deprecated keys.
- Ground-truth target/expected sets and protected hashes live only in the benchmark oracle outside the agent workspace.
- Exact migration of every affected loaded fragment is required for PASS. Missing targets remain strict failure even though recall/completion show partial progress.
- Already-current and historical files are hash-protected; unnecessary rewrites count as false positives, so broad replacement is not rewarded.
- `completion` is Jaccard set similarity (`TP / (TP + FP + FN)`), so both omissions and out-of-scope edits reduce it while precision/recall explain the failure mode.
- Added `coverage_completeness` reporting in `summary.json`, derived only from persisted evaluator metrics rather than recomputing task truth.

### Validation and strategic review

- Tests cover exact completion, partial completion, false positives, continuous metrics, evaluator persistence, preflight/golden witnesses and profile-level reporting aggregation.
- A partial migration can report useful coverage while acceptance score remains 0 and the task remains FAIL.
- Full recall with an out-of-scope edit still fails and has precision/completion below 1.
- Ownership is layered: generic set mathematics in `coverage.py`; domain truth in `coverage_migration.py`; persistence in `evaluators.py`; derived aggregation in `coverage_reporting.py`/`report.py`.
- No second scoring system or coverage-specific behavior heuristic was introduced.
- Final CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## M8 — Long-horizon pristine verification — DONE

### Why

Large coordinated changes expose consistency failures that short single-artifact tasks miss, and workspace-local tests are not a trustworthy final verifier when the agent can edit that workspace.

### Implemented

- Added `pristine.py` as the generic reconstruction boundary for existing source artifacts.
- Safe relative paths are required; symlinks, path traversal and artifact paths absent from the benchmark baseline are rejected.
- A fresh temporary repository is reconstructed from benchmark-owned baseline text and only task-declared source artifacts are overlaid from the agent workspace; deletions are reproduced explicitly.
- Added parametric `pristine_refactor` and Frontier v4 `long_horizon_pristine_001`.
- The pilot repository has separate validation, pricing, routing, serialization and integration modules plus public regression tests.
- The agent must coordinate the priority-tier rollout across four policy modules while `service.py`, README and public tests remain protected.
- Seeded variants change existing express behavior and priority surcharge/queue/wire-code specification without changing the task contract.
- The final verifier runs in a separate Python subprocess from the freshly reconstructed repository with a bounded timeout and minimal environment.
- Hidden checks validate each policy primitive, the integrated priority path, existing standard/express regressions and invalid-tier behavior.
- Workspace-local test tampering and high-level `service.py` shortcuts fail before hidden verification; newly added non-submitted helpers are absent from the pristine verifier tree.
- Pristine verification emits descriptive artifact/return-code metadata through the existing rich deterministic evaluation path.
- README documents the mechanism and explicitly distinguishes pristine verification from OS-level sandboxing.

### Validation and strategic review

- Tests cover baseline rejection, benchmark-owned golden acceptance, deleted-artifact reconstruction, unsafe/non-baseline path rejection, protected test/integration tampering and seeded semantic variation.
- A dedicated partial-solution regression proves that updating three of the four required policy modules still fails hidden integration verification.
- The first CI exposed an over-narrow test that compared only priority coordinates while adjacent variants changed the existing express coordinate; the test was corrected to compare the full observable specification rather than weakening the generator.
- Reconstruction ownership is isolated in `pristine.py`; domain truth and hidden integration checks remain in the parametric family; harness adapters remain unaware of pristine semantics.
- Git diff/apply was deliberately rejected for this pilot because it would add Git-specific failure modes without improving the required trust property; direct mutable-workspace verification was rejected because it would not be pristine.
- The verifier still follows the project-wide workspace threat model rather than claiming hostile-code sandboxing; stronger isolation belongs to M12.
- Final CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## M9 — Greenfield repository construction — ACTIVE

Build a small family starting from an empty/minimal repository, with deterministic hidden tests across architecture, API, persistence, validation and integration. Continuous hidden-test coverage may be reported, but completion remains deterministic and reference-solution independent.

First pilot design goals:

- provide only a specification and minimal project boundary, not a solution scaffold;
- allow the agent to create a bounded submitted source tree rather than limiting verification to pre-existing artifact paths;
- reconstruct that submitted tree outside the mutable workspace before verification;
- verify public API, persistence behavior, malformed-input handling and cross-module integration through hidden deterministic tests;
- avoid requiring one reference architecture: verification should depend on externally observable contracts rather than exact file contents or a golden source implementation;
- keep submitted-tree extraction generic so future greenfield tasks can reuse it without teaching harness adapters about repository structure.

## M10 — Reference trajectory and adaptive efficiency — PLANNED

For selected tasks, curate semantic reference milestones/efficient trajectories. Compare successful agent effort descriptively without turning raw command count into correctness or penalizing legitimate extra verification.

## M11 — Progressive environments and within-run learning — DEFERRED

Later evaluate reusable skill acquisition across related levels while explicitly separating persistent agent memory from workspace leakage. Resume only after trajectory, causal-state and cross-task ownership are mature.

## M12 — Task QA, aging, contamination and anti-cheat — PLANNED

Formalize task promotion/revision lifecycle: static validation, reference solve, no-op, cheat/adversarial checks, preservation/regression, multi-agent pilots, ambiguity/oracle review and stable promotion. Track revisions, audits, known issues, exposure/contamination risk and empirical saturation. This milestone also owns stronger isolation/anti-cheat work beyond the current workspace trust model.

## M13 — Multi-dimensional comparison UX — PLANNED

Expose deterministic capability, reliability/confidence intervals, failure taxonomy, trajectory behavior, inference speed, client resource cost, server/model resource cost and robustness/pressure response side-by-side. Prefer Pareto-style interpretation over arbitrary composite weighting and keep comparability warnings visible.

## Current execution order

1. Build and validate one M9 greenfield-construction pilot.
2. Add M10 reference-trajectory efficiency once real trajectory data exists.
3. Formalize M12 QA/aging/contamination before aggressive catalog expansion.
4. Expand M13 UX as each dimension stabilizes.

M11 remains deferred.

## Milestone update protocol

At every completed step:

- update status and implementation notes here;
- record architectural deviations and justified deferrals;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a strategic review for ownership, duplication, hidden dependencies, change amplification, races, shutdown/error paths and semantic drift;
- never mark work `DONE` based only on implementation without observed validation.
