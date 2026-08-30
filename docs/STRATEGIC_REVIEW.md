# Strategic programming review

This document records milestone-level design reviews. It is not a feature roadmap; findings are resolved before the next milestone when they materially affect correctness, ownership, information hiding, or future change cost.

## M3 — unified benchmark architecture

### Complexity and ownership

- **Resolved:** Frontier v3 and v4 no longer own separate execution engines. `FrontierRunner` owns execution/lifecycle semantics; `TaskMaterializer` owns workspace/oracle construction.
- **Resolved:** V3 task-specific setup no longer appears in the generic runner. Static fixture quirks are isolated in `StaticTaskMaterializer`.
- **Resolved:** harness configuration has one owner, `harness_registry.py`; compatibility modules re-export the same objects rather than constructing copies.
- **Resolved:** `BenchmarkRunner` is now a lifecycle/persistence base rather than a second legacy V2 execution engine.
- **Resolved:** scheduler integration uses a small public runner surface (`latest_results`, `record_unsupported`, `record_noncomparable`, `finalize`) instead of reaching through multiple private methods.
- **Resolved:** semantic source fingerprinting is include-by-default, so new execution/scoring modules are incorporated automatically rather than relying on a manually maintained allowlist.
- **Resolved:** run cancellation is a cooperative core concern. Qt only owns the signal/lifecycle boundary; process termination remains in the benchmark subprocess layer.

### Layering

- `main.py` remains wiring only.
- Qt thread ownership remains in `ui/runtime.py`.
- QWebChannel remains a thin presentation bridge.
- Canonical run/configuration state remains in Python.
- Task materialization, execution, scheduling, result persistence and presentation are distinct responsibilities.

### Deliberate compatibility surfaces

- `frontier_v3_runner.py` and `frontier_v4_runner.py` remain as thin constructors for existing internal/CLI imports. They contain no execution semantics and may be removed in a future breaking cleanup.
- `core/benchmark/config.py` remains a thin compatibility re-export of the canonical harness registry.
- Tests still expose the old `aios_bench` namespace through `tests/conftest.py`. This is test-only migration scaffolding, not a production dependency. Removing it would require broad low-value import churn and is deferred until a test-layout cleanup; no new test should depend on it when a `core.benchmark` import is practical.
- The legacy CLI remains available as a secondary engineering interface. The desktop application is canonical. Decomposing argparse command handlers further is deferred because current command logic delegates to core services and does not affect GUI/domain ownership.

## Pre-merge system-prompt audit hardening

The complete pre-merge audit identified three concrete gaps and all were resolved before merge readiness:

- **Resolved:** `DoctorService` no longer calls the private `doctor._run_install` helper. Doctor exposes a public argv-only install contract, and remote shell pipelines remain display-only/manual.
- **Resolved:** `install.sh` now detects an incompatible or broken `.venv`, recreates it with Python 3.12+, and verifies the virtualenv interpreter version before installing dependencies.
- **Resolved:** desktop shutdown is bounded and idempotent. Benchmark shutdown signals cooperative cancellation, workers quit their own Qt thread so shutdown does not depend on queued GUI delivery, and the runtime waits for bounded completion without `QThread.terminate()`.
- **Regression coverage added:** public Doctor install boundary, virtualenv repair contract, bounded benchmark/non-benchmark shutdown, and idle shutdown idempotence.

### Review conclusion

No known high-impact tactical workaround remains in the desktop/core boundary. Remaining compatibility shims are narrow, explicit and non-authoritative. New benchmark suites should be added as catalog/materialization definitions over the shared runner rather than by creating another version-specific execution engine.

## Post-audit corrective milestone — complete conformance pass

### Correctness and responsiveness

- **Resolved:** Doctor inspection no longer executes executable/version probes on the Qt GUI thread. Discovery, installation and post-install reinspection share the existing worker lifecycle and return through Qt signals. Doctor inspection is cooperatively cancellable between its individually bounded probes, and those probes use the shared owned-process lifecycle so timeout cleanup covers descendants as well as the direct child.
- **Resolved:** desktop and CLI gateway environment precedence now use one helper. Process-level values present before startup are protected; GUI-owned values can be updated or cleared without leaving stale environment state.
- **Resolved:** `BenchmarkService.catalog()` rejects suites outside the canonical registry before touching the filesystem.
- **Resolved:** Agent Zero HTTP calls have explicit bounded timeouts. The message request uses the active task budget and control/log/cleanup requests use a shorter bounded timeout.
- **Resolved:** Pi RPC validates its required stdio pipes with an explicit runtime error instead of relying on a production `assert`.
- **Resolved:** Ruff now enables the complete Pyflakes `F` correctness family rather than only a narrow subset.

### Complexity and ownership

- **Resolved:** GUI validation now produces an immutable `PreparedRun`; the worker consumes that validated task set directly instead of reloading and revalidating the catalog.
- **Resolved:** checkpoint latest-result lookup uses a file-signature-aware in-memory index. Normal runner writes update the index incrementally, while external test/recovery edits still invalidate and reload it.
- **Resolved:** `task_execution.py` depends on a small public runner protocol (`prepare_workspace`, `record_event`, `result_identity`, `record_result`) instead of reaching into private runner methods.
- **Resolved:** static fixture setup is catalog-declared through `Task.setup`; the materializer maps setup capabilities to handlers and no longer contains task-ID dispatch logic.
- **Resolved:** reference-oracle helpers were normalized into readable, typed modules with descriptive parameter names while preserving deterministic semantics.

### UI, operations and documentation

- **Resolved:** keyboard focus for custom task/harness selectors now has a dedicated visible orange focus state. The native minimum size and CSS minimum width no longer make the responsive desktop breakpoint unreachable.
- **Resolved:** neumorphic radius usage is brought back to the 28/22/16/12 scale; pill-only `999px` rounding was removed from the run badge.
- **Resolved:** application diagnostics now use console plus bounded rotating-file logging under the XDG state directory, with a console-only fallback if file setup fails.
- **Resolved:** README now declares the Italian desktop UI, environment precedence, log location, one-pass prepared-run validation and active catalog layout. `benchmarks/tasks/README.md` explicitly separates active versioned catalogs from historical root-level assets; `results/README.md` distinguishes verified publications from historical derived snapshots.
- **Resolved:** the README now documents the sensitive harness environment boundary: benchmark-specific Agent Zero/Claude credentials, inherited Anthropic credentials, and Claude subprocess credential scrubbing are explicit operational assumptions rather than hidden dependencies.

### Review conclusion

The corrective patch addresses the audit findings at their source rather than patching the presentation layer. No new event bus, DI container, framework or speculative abstraction was introduced. Compatibility aliases remain only where they preserve existing tests/CLI imports without owning behavior. Future task-specific fixture preparation should be added as catalog setup capabilities, and future task execution needs should extend the public runner protocol only when a concrete requirement appears.

This milestone is not considered closed until the patch is applied to the complete repository and the canonical compileall/pytest/Ruff gates plus Qt/WebEngine smoke and native desktop checks have been observed successfully. The per-finding validation state is tracked in `docs/AUDIT_2026-08-28_REMEDIATION.md`.

## Frontier V4.3 — harness ablations and tool recovery

### Complexity and ownership

- **Resolved:** skill interventions are one execution-condition abstraction owned by `interventions.py`; task prompts do not contain arm-specific branching and neither adapters nor individual harnesses know how curated skills are represented.
- **Resolved:** ordinary execution identity remains strict. `no_skill` and `curated_skill` have different execution fingerprints, while a dedicated ablation fingerprint neutralizes only the arm selector and keeps the skill-catalog digest, model profile and all other execution semantics visible to matching.
- **Resolved:** paired skill execution reuses `MatchedInterleavedScheduler`. No second scheduler, scorer, persistence path or ablation-specific runner was introduced.
- **Resolved:** canonical capability rows have one reporting boundary. Curated intervention rows are excluded before leaderboard, reliability, pressure, harness-delta, failure and efficiency aggregation, while raw results remain intact for dedicated skill-lift analysis.
- **Resolved:** duplicate exact ablation cells, missing model/profile identity, invalid skill-application identity, same-arm execution fingerprints and inconsistent skill packages fail closed instead of being silently averaged or overwritten.

### Tool-recovery layering and information hiding

- **Resolved:** `parametric/tool_recovery.py` owns generated workload semantics and hidden oracle data; `tool_recovery_service.py` owns typed domain operations, deterministic failures and external action provenance; `tool_recovery_api.py` owns only the task-scoped authenticated loopback transport/lifecycle.
- **Resolved:** operational state is moved out of the agent-visible workspace while the runtime is active and restored deterministically for final-state grading. The agent can mutate it only through the benchmark-owned typed interface.
- **Resolved:** final-state verification and action-provenance verification are separate checks. A plausible report cannot hide wrong-tool use, duplicate side effects, incomplete reads or incorrect idempotency recovery.
- **Resolved:** action logging is serialized under the service lock so the threaded HTTP transport cannot create duplicate/out-of-order sequence numbers.
- **Resolved:** every valid tool-recovery variant contains both recovery modes promised by the task: at least one retryable read failure and at least one ambiguous committed write requiring same-key replay.

### Failure paths and observability

- **Resolved:** deterministic post-execution diagnoses distinguish `TOOL_SELECTION_ERROR`, `TOOL_SCHEMA_ERROR`, `RETRY_LOOP` and `RECOVERY_FAILURE` while runtime timeout/crash/infrastructure precedence remains unchanged.
- **Resolved:** retry-loop detection is keyed by logical operation rather than idempotency key, preventing a client from evading diagnosis by rotating keys.
- **Resolved:** malformed typed identifiers are recorded in benchmark-owned provenance before returning the schema error.
- **Resolved:** desktop progress includes the active skill condition, and the skill-ablation checkbox has an explicit accessible focus state rather than inheriting full-width text-input styling.

### Change-amplification review

Adding V4.3 required one new parametric family registration, one execution condition and one derived analysis. The shared runner, task executor, scheduler, result checkpoint format and scoring path remained intact. The CLI and desktop service both consume the same pressure registry and execution-condition semantics rather than owning duplicate benchmark rules. This is the intended extension shape for V4.4: a new family should plug into materialization/evaluation without modifying generic harness execution.

### Deliberate deferrals

- Statistical inference for skill lift remains descriptive until enough repeated matched observations exist to justify a stable confidence-interval/test contract. Raw matched cells are preserved so this can be added later without changing task semantics.
- Curated skills exist only for the two V4.3-relevant tasks that currently justify them. A generic skill authoring/plugin system would be speculative and is intentionally not introduced.
- Live remote tool ecosystems remain out of scope. Tool recovery is local and deterministic so benchmark results do not inherit service drift or availability noise.

### Review conclusion

**Closed 2026-08-30.** No material ownership leak, duplicated execution path or tactical special-case layer was found after the V4.3 cleanup. The complete post-review implementation passed the canonical CI matrix on Python 3.12, 3.13 and 3.14, including install verification, compileall, Ruff and pytest with the existing offscreen Qt/WebEngine coverage. V4.4 should start from the current materialization/evaluation interfaces rather than changing the runner.

## Frontier V4.4 — exhaustive retrieval and provenance

### Complexity, ownership and extension shape

- **Resolved:** `parametric/wide_retrieval.py` owns generated corpus semantics and deterministic grading. It does not add a second runner, scheduler, persistence path, transport layer or harness-specific implementation.
- **Resolved:** the existing `ParametricTaskMaterializer` remains the only owner of seeded workspace/oracle construction. The hidden oracle is written under the run directory, outside the agent workspace, exactly like the other Frontier v4 families.
- **Resolved:** partial deterministic grading is exposed through the small `VariantGrade` contract. Existing binary families continue to use `VariantGrade.binary`, so V4.4 did not duplicate the evaluator or alter their semantics.
- **Resolved:** family-specific derived aggregation lives in `retrieval_analysis.py`; it reads persisted evaluation metrics and does not participate in task execution or grading. The module is deliberately non-semantic, while the generator/grader remains part of the suite fingerprint.

### Information hiding and benchmark integrity

- **Resolved:** the generated workspace contains only task-visible corpus, query and authority metadata. Expected target rows and protected-input digests remain in the benchmark-owned oracle outside the workspace.
- **Resolved:** every generated corpus has one explicit authoritative root plus plausible mirrors and retired conflicting records. At least one target receives a stale conflicting representation so authority/provenance errors remain observable rather than depending on a lucky seed.
- **Resolved:** all corpus, query, authority and instruction inputs are hash-protected. Modifying any protected source invalidates grading before result metrics are considered.
- **Resolved:** grading requires exact authoritative JSONL path and 1-based source line, so a semantically correct record copied from a mirror or retired source cannot receive a strict pass.
- **Resolved:** V4.4 stays completely offline. No live web, remote search service or externally drifting corpus is involved.

### Scoring, diagnostics and failure taxonomy

- **Resolved:** strict complete pass remains the canonical success condition. Partial score is deterministic diagnostic signal only and cannot turn an incomplete fatal parametric check into a task pass.
- **Resolved:** retrieval quality is decomposed into record precision, recall/F1, field-level correctness and provenance recall, with explicit counts for missing, extra and duplicate rows plus wrong-authority, stale-source and mirror-source use.
- **Resolved:** deterministic failure precedence classifies missing target records as `INCOMPLETE_RETRIEVAL` before considering provenance loss caused by the same omission; actual citation/authority failures are classified as `WRONG_AUTHORITY` once retrieval completeness is satisfied.
- **Resolved:** baseline/no-skill filtering remains centralized in the existing canonical reporting boundary. Curated-skill runs therefore cannot inflate the V4.4 capability or retrieval-quality aggregates.
- **Resolved:** pressure coordinates remain descriptive workload dimensions (`corpus_size`, `target_count`, `duplicate_records`, `conflict_records`, `source_depth`). Existing landscape code records exact joint vectors and does not assume that a marginal coordinate is causally monotonic difficulty.

### Benchmark-health review

- **Verified by deterministic tests:** same seed plus same pressure reproduces the same variant identity and targets; changing seed or pressure changes the variant digest.
- **Verified by deterministic tests:** the golden complete answer receives strict pass and full metrics.
- **Verified by deterministic tests:** missing targets, extra rows, field corruption, stale citations and source tampering are rejected with the expected metric/failure behavior.
- **Verified by integration tests:** the structured grade, partial credit and family metrics survive through the generic evaluator, run identity, summary and dashboard paths.
- **Verified by UI/service tests:** the new task and all effective default pressure coordinates come from the same Frontier v4 catalog/registry used by CLI and desktop execution.

### Change-amplification review

One new family still requires explicit registration in the parametric pressure map plus catalog/CLI/service/reporting coverage. This is visible change, but it remains localized and preserves clear ownership. Replacing the explicit family dispatch with a plugin/factory registry now would add indirection without reducing a demonstrated maintenance bottleneck. The current explicit dispatch is therefore retained; revisit only if later families make this extension surface materially repetitive or error-prone.

The structured `VariantGrade` abstraction is justified by a concrete present need: V4.4 has meaningful deterministic partial metrics while earlier families are binary. It hides that distinction from the generic evaluator rather than spreading family checks into execution code.

### Deliberate deferrals

- Live-web retrieval is intentionally excluded because source drift, availability and search-provider behavior would weaken reproducibility and comparability.
- Cross-artifact reconciliation is not folded into this family; it belongs to V4.5 so retrieval and artifact-consistency semantics remain independently understandable.
- No weighted opaque retrieval composite is promoted to the dashboard. Raw dimensions and strict pass remain visible until empirical runs justify any stronger summary contract.
- `source_depth` currently describes generated authoritative path depth, not a causal difficulty scale; reporting must continue treating it as an observed pressure coordinate only.

### Review conclusion

**Closed 2026-08-30.** The post-review V4.4 commit passed the canonical CI matrix on Python 3.12, 3.13 and 3.14, including installation, compileall, Ruff and pytest. No material ownership leak, hidden external dependency, duplicated state owner or harness-specific special case remained at closure. V4.5 can therefore build on the shared materialization/evaluation contract without changing the runner.

## Frontier V4.5 — cross-artifact consistency

### Design alternatives and selected boundary

Two materially different approaches were considered before implementation:

1. add a generic multi-artifact schema/plugin engine and make tasks declaratively describe arbitrary artifact types; or
2. add one deep parametric family whose generator owns the concrete source-of-truth transformation and whose grader independently parses the two required deliverables.

The second design was selected. A generic artifact framework would be speculative: there is currently only one concrete cross-artifact family, and abstracting format grammar, reconciliation keys and semantic transforms prematurely would spread configuration across layers rather than hide complexity. The selected module presents the same small family interface as existing V4 generators while keeping its CSV/domain rules private.

### Complexity and ownership

- **Resolved:** `parametric/cross_artifact.py` exclusively owns generated ledger semantics, deterministic source-of-truth transformation, independent JSON/Markdown parsing and cross-artifact reconciliation. Generic evaluator and task execution code remain family-agnostic through `VariantGrade`.
- **Resolved:** `ParametricTaskMaterializer` remains the sole owner of seeded workspace/oracle construction. Expected summaries and protected digests live only in the hidden run oracle.
- **Resolved:** no task-scoped runtime, API, harness adapter branch or new scheduler is needed. The workload is ordinary local-file reasoning over the same shared Frontier runner.
- **Resolved:** derived aggregation is isolated in `cross_artifact_analysis.py` and explicitly excluded from semantic suite fingerprinting, while generator/grader code remains semantic by default.
- **Resolved:** CLI pressure controls instantiate the same `CrossArtifactPressure` type registered in the canonical family registry. The desktop service consumes normalized registry defaults, avoiding a second owner for effective pressure identity.

### Correctness, negative constraints and information hiding

- **Resolved:** the authoritative input uses integer cents, not floating-point money. Posted negative adjustments are therefore exact and deterministic.
- **Resolved:** every account is guaranteed at least one posted source row, while pending/voided rows and archived ledger revisions create meaningful exclusion/distractor pressure without changing the authoritative transform.
- **Resolved:** README, authority metadata, current ledger and distractor ledgers are hash-protected. Agent modification of any benchmark input fails before artifact scoring.
- **Resolved:** machine-readable and human-readable artifacts are parsed independently. A correct JSON file cannot mask a wrong Markdown file, and vice versa.
- **Resolved:** unsupported account groups are measured explicitly and prevent strict success even if both output artifacts contain the same unsupported claim.
- **Resolved:** exact account sets, per-account posted counts/net cents, overall count, grand total and source identity must all agree with the hidden canonical transformation.

### Scoring and failure semantics

- **Resolved:** strict completion remains the task success criterion. Deterministic component accuracy and reconciliation are diagnostic partial metrics carried through the existing structured grade; fatal acceptance remains fatal.
- **Resolved:** `CROSS_ARTIFACT_MISMATCH` means exactly that two parseable deliverables disagree with each other. If both deliverables agree but are jointly wrong relative to the authoritative source, the ordinary deterministic `WRONG` category remains semantically correct rather than overloading the mismatch diagnosis.
- **Resolved:** machine accuracy, human accuracy and reconciliation rate remain separate dimensions in `summary.json`; no opaque weighted cross-artifact index is introduced.
- **Resolved:** extra groups are reported separately rather than silently changing the field-accuracy denominator. They still make strict completion impossible, preserving a readable distinction between incorrect expected fields and unsupported additional claims.

### Benchmark-health review

- **Verified by deterministic tests:** same seed plus same pressure reproduces the same hidden expected summary and variant digest; changing seed or pressure changes variant identity.
- **Verified by deterministic tests:** the exact dual-artifact golden receives full strict success.
- **Verified by deterministic tests:** a JSON/Markdown disagreement is detected and classified as `CROSS_ARTIFACT_MISMATCH`.
- **Verified by deterministic tests:** two mutually consistent but authoritative-wrong artifacts fail without being mislabeled as an inter-artifact mismatch.
- **Verified by deterministic tests:** unsupported groups and source tampering fail strict grading.
- **Verified by integration tests:** partial metrics and failure kind propagate through the generic evaluator/classifier, canonical summary aggregation, CLI pressure identity and desktop catalog/default-pressure paths.

### Change-amplification review

V4.5 required one family module, one catalog entry, one derived-analysis module and localized registry/CLI/report/test updates. The runner, scheduler, task executor, persistence format, Qt bridge and frontend required no semantic special cases. This is consistent with the strategic extension shape established in V4.3–V4.4.

The explicit family dispatch is becoming longer but has not yet produced duplicated behavior or ambiguous ownership: each branch is a direct mapping from a stable family name to its pressure/generator/grader. Introducing reflection, plugin discovery or factories now would increase cognitive load. Revisit only if V4.6+ demonstrates actual change amplification beyond these localized registrations.

### Deliberate deferrals

- DOCX/PDF or other rich document formats are intentionally excluded until their parsing/rendering dependencies can be validated deterministically; strict JSON plus Markdown satisfies the milestone without adding fragile document infrastructure.
- A dedicated dashboard panel for V4.5 component metrics is deferred. The canonical task score/failure remains visible in the existing dashboard and the machine/human/reconciliation dimensions are persisted in `summary.json`. A presentation-specific panel can be added once multiple real runs demonstrate which cross-artifact dimensions are useful enough to warrant permanent UI space.
- Additional artifact pairs (for example CSV + memo, configuration + report) should be added as concrete scenarios only when they test meaningfully different reconciliation capability; a generic authoring framework remains intentionally absent.

### Review conclusion

The V4.5 implementation preserves one source of truth for task semantics, one parametric materialization path and one generic evaluation pipeline. No material ownership leak, new external dependency, duplicated execution path or tactical harness special case was found. Formal closure requires the canonical post-review CI matrix to pass on Python 3.12, 3.13 and 3.14; only after observing that result should V4.6 begin.
