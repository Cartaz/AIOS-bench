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

- Frontier v4 QA registry is now schema `aios-bench/task-qa/v4`, keyed by task id/revision with lifecycle (`draft`/`pilot`/`stable`/`retired`), exposure, known issues, audit date and explicit review state.
- Completed manual reviews require structured provenance (`kind`, `reference`, `observed_at`, optional `notes`); pending reviews require `evidence=null`.
- QA records carry both a semantic digest over task-owned meaning and a separate `review_context_digest` over semantic identity plus exposure. Meaning changes invalidate the semantic audit; exposure changes invalidate manual-review context without pretending benchmark semantics changed.
- QA audits have a 180-day operational review interval. Expired pilots remain structurally valid but maintenance-due/non-promotable; expired stable tasks violate the current promotion contract until re-audited.
- Automated QA is granular rather than one opaque boolean. Frontier v4 reports same-seed determinism, different-seed variation, untouched negative-baseline rejection, golden-witness acceptance and adversarial-witness rejection. Missing and failed checks remain distinct and no QA check changes capability score.
- Added `parametric_adversarials.py` as the single owner of deterministic plausible-but-wrong witnesses. Validation materializes a fresh variant, applies the witness and executes the same production grader used by real results.
- Witnesses cover: correct expense totals with wrong malformed count; correct effective config with incomplete provenance; symptom-only gateway runtime repair; correct live probe with stale-lane repair; correct case data with fabricated lookup receipt; partial finite-set migration; all-but-one-module pristine rollout; and API-complete but non-persistent greenfield registry.
- Completed ambiguity/oracle review across all eight Frontier v4 tasks. It found two real contract mismatches; `autonomy_expense_001` and `autonomy_causal_gateway_001` were clarified and bumped from revision 4 to 5 rather than preserving misleading comparability.
- Completed scoped adversarial/cheat review across all eight tasks. The scope is task/grader-level bypass resistance; it explicitly does not claim that an unconfined process cannot escape the workspace and inspect public benchmark internals.
- Contamination risk is derived from canonical exposure (`private` low, `limited` medium, `public_repository` high) and remains descriptive rather than becoming a second score.
- Completed public-repository contamination review across all eight current tasks. The suite is explicitly classified as high-risk public/open rather than contamination-free; seeded variants protect concrete instance values but cannot restore novelty of public family semantics.
- Added `qa-evidence` for empirical M12 evidence collection from local raw results. It accepts only comparable current-revision Frontier v4 attempts and reports profile/harness/model diversity, outcome distribution, score range, canonical `status`/`failure_kind` counts, pressure-coordinate diversity and canonical generated-variant identity.
- `qa-evidence` exposes per-task `collection_state`, ordered `collection_gaps` and aggregate gap counts for four minimum contrast axes: at least one current-revision attempt, a second harness, a second model and a second generated variant identity. Cross-profile diversity remains separately visible but is not duplicated as an independent collection requirement. These are collection gaps only, not promotion or saturation thresholds, and they never mutate QA lifecycle state.
- Added a shared pristine-verifier execution boundary for M8/M9. Strong mode uses Bubblewrap with minimal read-only runtime/system bindings, writable pristine workspace, ephemeral `/tmp` and separated network/process namespaces.
- Bubblewrap availability is capability-tested rather than inferred from executable presence. `auto` records an explicit fallback reason when namespaces are denied; `required` fails closed. Harness workspace sandboxing uses the same capability principle.
- Added `qa_isolation.py` as a fail-closed combined boundary diagnostic. `.venv/bin/python -m core.benchmark.qa_isolation` now returns `aios-bench/qa-isolation-boundaries/v1` with separate pristine-verifier and workspace-sandbox evidence and exits 2 unless both pass.
- The pristine proof tests writable submitted state, unreadable sibling host state and unreachable host loopback in addition to verifier-reported filesystem/network confinement.
- The workspace proof uses the actual local-harness sandbox plan and separately verifies current-workspace writes plus repository/grader hiding. It explicitly publishes `network_isolation_claimed=false`; the workspace sandbox does not unshare the network namespace.
- Strategic review found and fixed two Agent Zero sandbox defects. The writable `AIOS_BENCH_AGENTZERO_PROJECTS_ROOT` bridge was previously reported as `write_confined=true`; it now correctly reports false while retaining `grader_hidden=true`. Separately, masking the entire `results/` tree could hide Agent Zero's current canonical workspace; the sandbox now rebinds only that current workspace after masking while leaving sibling results/oracles hidden.
- `SandboxPlan` owns a path-free public serialization of strategy, write confinement, grader hiding, network-isolation claim and fallback error so security metadata has one canonical representation and command/path internals need not be exposed.
- GitHub-hosted CI intentionally installs Bubblewrap. Hosted runners expose the binary but deny the required namespace operations; this exercises the explicit fallback path rather than producing a false strong-isolation claim.

### Validation and strategic review

- Semantic-digest regressions cover same-revision prompt and trajectory-reference changes; review-context regressions cover exposure changes independently.
- Review-evidence tests reject opaque completed evidence, invalid provenance and dangling evidence on pending reviews.
- Aging regressions cover fresh stable promotion, expired pilot maintenance and expired stable contract failure.
- Sandbox regressions cover unavailable/unusable Bubblewrap, `required` fail-closed behavior, local workspace-only plans, Agent Zero writable-bridge semantics, current-workspace rebind after result masking, and a real Bubblewrap execution contract when the host supports namespaces.
- Parametric validation schema `aios-bench/parametric-validation/v3` requires all eight adversarial witnesses to be rejected while the corresponding golden witnesses still pass.
- QA report schema `aios-bench/task-qa-report/v6` exposes the five automated checks, exact missing/failed blockers and contamination-risk counts.
- Empirical QA regressions reject stale revisions and non-comparable/other-suite attempts, preserve outcome/score/profile summaries, distinguish pressure-coordinate diversity from canonical `variant_digest` diversity, expose raw status/failure-kind taxonomy without reclassifying it, and verify deterministic collection-gap reporting without automatically passing manual review.
- Isolation QA regressions cover both boundaries independently and together. The pristine proof requires the real strong strategy plus all three observations and converts namespace/timeout failures into failed evidence. The workspace proof requires write confinement plus grader hiding, rejects an Agent Zero writable-bridge plan as workspace-only confinement, verifies its workspace-written probe and explicitly refuses a network-isolation claim.
- Agent Zero sandbox hardening and the combined isolation proof checkpoints were observed green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.
- Ownership remains layered: task families own truth; `parametric_adversarials.py` owns negative-but-plausible witnesses; `validation.py` owns preflight orchestration; `task_qa.py` owns lifecycle/report semantics; `qa_empirical.py` owns descriptive real-run evidence; `qa_isolation.py` owns environment-specific proof orchestration; `sandbox.py` owns workspace confinement plans; and `pristine_verifier.py` remains the pristine execution-boundary owner. No second capability score was introduced.
- QA lifecycle/task review and runtime sandbox capability remain separate. A grader-level adversarial pass must not be interpreted as proof of host confinement.
- Both proof mechanisms are implemented and unit-covered, but GitHub-hosted runners cannot provide the namespaces needed for an end-to-end combined `ok=true` execution. Runtime proof remains required on a compatible Linux host before M12 can close.
- All eight current Frontier v4 tasks remain `pilot`. Ambiguity/oracle, scoped adversarial and contamination reviews are passed; multi-agent and saturation reviews remain pending.

### Remaining before DONE

- run multi-agent pilots on representative local models/harnesses, using `qa-evidence` collection gaps to prioritize experiments that add missing contrast rather than redundant repeats, and record task-level evidence;
- perform empirical saturation checks using successful/failed run distributions and `status`/`failure_kind` taxonomy rather than subjective difficulty labels or infrastructure failures;
- execute `.venv/bin/python -m core.benchmark.qa_isolation` on a Linux host where Bubblewrap namespaces are actually permitted, retain the combined `ok=true` evidence and record it in the M12 review;
- complete the final milestone-wide strategic review after the empirical and environment-specific evidence exists.

## M13 — Multi-dimensional comparison UX — PLANNED

Expose deterministic capability, reliability/confidence intervals, failure taxonomy, trajectory behavior, inference speed, client resource cost, server/model resource cost and robustness/pressure response side-by-side. Prefer Pareto-style interpretation over arbitrary composite weighting and keep comparability warnings visible.

## Current execution order

1. Complete M12 multi-agent pilot and saturation evidence on representative local models/harnesses, guided by `qa-evidence` collection gaps.
2. Run and record the combined M12 isolation diagnostic on a compatible host.
3. Calibrate M10 reference effort from successful real Frontier v4 trajectories gathered during those pilots.
4. Expand M13 UX as each dimension stabilizes.

M11 remains deferred.

## Milestone update protocol

At every completed step:

- update status and implementation notes here;
- record architectural deviations and justified deferrals;
- run compile, Ruff and pytest plus relevant native/offscreen checks;
- perform a strategic review for ownership, duplication, hidden dependencies, change amplification, races, shutdown/error paths and semantic drift;
- never mark work `DONE` based only on implementation without observed validation.