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
- The final verifier runs from the freshly reconstructed repository through a bounded shared verifier boundary.
- Hidden checks validate each policy primitive, the integrated priority path, existing standard/express regressions and invalid-tier behavior.
- Workspace-local test tampering and high-level `service.py` shortcuts fail before hidden verification; newly added non-submitted helpers are absent from the pristine verifier tree.
- Pristine verification emits descriptive artifact/return-code/isolation metadata through the existing rich deterministic evaluation path.

### Validation and strategic review

- Tests cover baseline rejection, benchmark-owned golden acceptance, deleted-artifact reconstruction, unsafe/non-baseline path rejection, protected test/integration tampering and seeded semantic variation.
- A dedicated partial-solution regression proves that updating three of the four required policy modules still fails hidden integration verification.
- Reconstruction ownership is isolated in `pristine.py`; domain truth and hidden integration checks remain in the parametric family; harness adapters remain unaware of pristine semantics.
- Git diff/apply was deliberately rejected for this pilot because it would add Git-specific failure modes without improving the required trust property; direct mutable-workspace verification was rejected because it would not be pristine.
- M12 later strengthened the verifier execution boundary with capability-tested Bubblewrap isolation when supported, while keeping fallback state explicit rather than retroactively changing M8 task semantics.
- Final CI observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## M9 — Greenfield repository construction — DONE

### Implemented

- Extended `pristine.py` with a reusable submitted-tree boundary for files that do not exist in a benchmark baseline.
- `collect_submitted_tree()` accepts only a declared relative root, never follows symlinks, ignores operational cache directories and enforces configurable file-count and byte limits.
- `pristine_submitted_tree()` copies only that manifest into a new temporary verifier directory; files elsewhere in the mutable workspace are absent by construction.
- Added parametric `greenfield_registry` and Frontier v4 `greenfield_registry_001`.
- The generated workspace contains only a benchmark-owned public specification; there is no starter implementation under `submission/`.
- The agent may choose any internal module layout as long as the submitted tree exposes the documented `registry_app.Registry` public contract.
- Hidden deterministic verification covers import/API shape, Unicode-aware name normalization, invalid input, duplicate handling, sorted listing, deletion, persistence across new instances and malformed persisted storage.
- The benchmark golden witness uses a small two-file implementation, but verifier success never compares source text, module count or internal architecture against it.
- Seeded variants change public name-length constraints and example storage names while preserving the task family contract.
- Rich evaluation persists descriptive submitted-file count/bytes, verifier status and isolation metadata without adding a new scoring system.
- Frontier v4 discovery/preflight includes eight parametric tasks/families.

### Validation and strategic review

- Tests prove that the empty baseline fails and the benchmark-owned witness passes from the copied submission alone.
- Files placed outside `submission/` cannot satisfy verification, and modification of the benchmark specification is rejected before executing submitted code.
- Submitted-tree tests cover cache exclusion, out-of-tree exclusion, symlink rejection and both file-count and total-byte bounds.
- Verification is behavior/reference-solution independent: only the public contract is constrained; internal implementation choices remain hidden behind the submitted package interface.
- Ownership remains layered: generic extraction/reconstruction in `pristine.py`, domain specification/truth in `greenfield_registry.py`, golden satisfiability in `parametric_goldens.py`, and normal deterministic persistence/scoring in the existing evaluator path.
- No harness adapter, runner or GUI special case was added for greenfield semantics.
- M12 later strengthened execution isolation without changing the greenfield capability contract.
- Final documentation-state CI was observed green on Python 3.12, 3.13 and 3.14.

## M10 — Reference trajectory and adaptive efficiency — ACTIVE

### Implemented framework

- Added validated task-owned `trajectory_reference` definitions using semantic milestone ids and accepted canonical event types rather than exact command strings or tool arguments.
- Added `reference_trajectory.py`, which ignores inferred and runner-owned events, requires declared telemetry kinds, and matches milestones monotonically through canonical event order.
- Comparison occurs only for capability-successful tasks. Failed tasks report `capability_not_successful`; harnesses lacking required telemetry report `required_telemetry_missing` rather than guessed values.
- Added pilot milestone references to `greenfield_registry_001` and `long_horizon_pristine_001`: inspect -> author/coordinate -> verify.
- `FrontierRunner` enriches the canonical result at write time; capability evaluation, score, behavioral oracles and `task_execution` remain unchanged.
- Results expose milestone completion, reliable events to semantic completion and post-completion events with `affects_score=false`.
- `summary.json` publishes `reference_trajectory_efficiency` by aggregating only persisted trajectory evidence; reporting does not replay or reinterpret events.
- Tests cover validation, ordered matching, missing/inferred telemetry, failed-capability exclusion, incomplete ordering, result persistence and aggregation.
- README documents scope and non-scoring semantics.

### Strategic review and empirical blocker

- An initial design included manually chosen reference event counts. Review rejected this before milestone closure because a numeric ratio without a real successful reference trajectory would create false precision.
- The framework therefore publishes absolute observed effort only. `calibrated_reference_effort_available=false` remains explicit and no “times reference” metric exists.
- Semantic milestone references are already suite-fingerprinted because they live in task catalogs; the evaluator itself is also semantic source code.
- Ownership is separated: tasks own semantic milestones, `reference_trajectory.py` owns comparison semantics, the runner owns persistence, and reporting owns aggregation.
- Framework/documentation CI was observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.
- M10 remains `ACTIVE`, not `DONE`, until successful real Frontier v4 runs provide evidence from which a reference-effort calibration can be justified. This is an empirical dependency, not an implementation shortcut.

## M11 — Progressive environments and within-run learning — DEFERRED

Later evaluate reusable skill acquisition across related levels while explicitly separating persistent agent memory from workspace leakage. Resume only after trajectory, causal-state and cross-task ownership are mature.

## M12 — Task QA, aging, contamination and anti-cheat — ACTIVE

### Implemented

- Added machine-readable Frontier v4 QA registry schema `aios-bench/task-qa/v2`, keyed by task id and revision with lifecycle (`draft`/`pilot`/`stable`/`retired`), exposure, known issues, audit date and explicit review evidence.
- Automated grader evidence and manual/pilot evidence remain distinct. Pending ambiguity/oracle, adversarial/cheat, multi-agent, contamination and saturation reviews cannot be represented as passed by inference.
- Stable lifecycle is fail-closed: all manual reviews must be passed/not-applicable and known issues must be empty; promotion additionally requires automated baseline/golden validation.
- QA records now carry a SHA-256 semantic digest over task-owned meaning, including prompt, category/mode/tier, revision, tags, capability requirements, dependencies, acceptance, behavioral acceptance and trajectory reference. A same-revision semantic edit therefore invalidates the audit automatically.
- QA audits have an operational 180-day review interval. Aging does not rewrite historical benchmark semantics: an expired pilot remains structurally valid but maintenance-due/non-promotable, while an expired stable task violates the current promotion contract until re-audited. Tests inject `as_of` dates instead of depending on wall-clock time.
- Added a shared pristine-verifier execution boundary for M8/M9. Strong mode uses Bubblewrap with minimal read-only runtime/system bindings, writable pristine workspace, ephemeral `/tmp` and separated network/process namespaces.
- Added a reusable Bubblewrap capability probe. Presence of `bwrap` is no longer treated as evidence that namespaces can actually be created. `auto` records an explicit fallback reason when the host denies isolation; `required` fails closed.
- Applied the same capability detection to harness workspace sandboxing, removing the previous latent assumption that `shutil.which("bwrap")` implied confinement.
- Verifier metrics persist isolation strategy, filesystem/network confinement flags and fallback reason, so results cannot silently claim a stronger trust boundary than the host supplied.
- CI intentionally installs Bubblewrap. GitHub-hosted runners currently expose the binary but deny the required namespace operations; this real environment exercised and validated the capability-fallback path rather than being hidden by a skipped dependency.

### Validation and strategic review

- Stale-audit regressions prove that same-revision prompt and trajectory-reference changes invalidate the semantic digest.
- Aging regressions cover fresh stable promotion, expired pilot maintenance and expired stable contract failure.
- Sandbox regressions cover unavailable and unusable Bubblewrap, `required` fail-closed behavior, command-plan confinement metadata and harness fallback reporting.
- CI checkpoint after capability probing observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.
- QA lifecycle is task-design state; runtime sandbox capability is host/environment state. They remain separate instead of contaminating task correctness with machine-specific availability.
- The strong Bubblewrap verifier path is implemented and unit-covered, but GitHub-hosted runners cannot provide the namespaces needed for an end-to-end strong-isolation execution. Runtime proof therefore remains required on a compatible Linux host before M12 can be closed.
- All eight current Frontier v4 tasks remain `pilot` with manual reviews pending. No stable-promotion claim has been fabricated.

### Remaining before DONE

- expose more granular automated QA evidence and contamination-risk reporting without creating a second capability score;
- perform and record ambiguity/oracle and adversarial cheat reviews per task;
- run multi-agent pilots and empirical saturation checks on representative local models/harnesses;
- perform contamination review appropriate to a public repository and define revision/retirement policy when exposure becomes unacceptable;
- execute the strong verifier/harness sandbox contract on a Linux host where Bubblewrap namespaces are actually permitted, then record that evidence;
- complete a final milestone-wide strategic review after the empirical evidence exists.

## M13 — Multi-dimensional comparison UX — PLANNED

Expose deterministic capability, reliability/confidence intervals, failure taxonomy, trajectory behavior, inference speed, client resource cost, server/model resource cost and robustness/pressure response side-by-side. Prefer Pareto-style interpretation over arbitrary composite weighting and keep comparability warnings visible.

## Current execution order

1. Continue M12 with granular automated QA evidence and contamination-risk reporting.
2. Perform M12 adversarial/manual review and compatible-host isolation validation.
3. Calibrate M10 reference effort after successful real Frontier v4 trajectory data exists.
4. Expand M13 UX as each dimension stabilizes.

M11 remains deferred.

## Milestone update protocol

At every completed step:

- update status and implementation notes here;
- record architectural deviations and justified deferrals;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a strategic review for ownership, duplication, hidden dependencies, change amplification, races, shutdown/error paths and semantic drift;
- never mark work `DONE` based only on implementation without observed validation.
