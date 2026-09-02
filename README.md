# AIOS-Bench

AIOS-Bench is a reproducible benchmark application for local AI operating-system agents. The desktop application is the canonical user interface; benchmark logic and state live in Python under `core/`, while the local HTML/CSS/JavaScript frontend is presentation-only and communicates through QWebChannel.

## Requirements

- Linux desktop (CachyOS/Arch + KDE is first-class)
- Python 3.12+
- Qt/PySide6 with WebEngine
- Bubblewrap (`bwrap`) for strict grader-hidden sandboxing; V4.8 black-box reconstruction fails closed when a functional sandbox is unavailable
- Optional harness runtimes configured through the in-app Setup / Doctor workflow

## Install

```bash
chmod +x install.sh
./install.sh
```

The installer resolves the repository root from any working directory, creates or repairs `.venv`, installs runtime/development requirements, verifies the critical Qt/application imports, provisions a project-local Node/npm runtime, installs the pinned managed Pi/OpenCode/Letta/Claude/DeepSeek harnesses into `.venv`, and probes whether an installed Bubblewrap can actually create the sandbox required by strict black-box reconstruction grading. Missing or unusable Bubblewrap is reported explicitly without preventing installation of the rest of AIOS-Bench. Hermes, Goose and Agent Zero remain intentionally external because their supported installation/service lifecycles are materially different. See `docs/INSTALLATION.md` for the exact pinned runtime contract.

## Launch

```bash
.venv/bin/python main.py
```

The desktop UI is currently Italian. It provides suite selection, per-harness toggles, per-task toggles, `Tutti` / `Nessuno` controls, benchmark configuration, progress/results, safe run cancellation, and an integrated Setup / Doctor panel for harness readiness and local-model gateway settings. Setup can discover the OpenAI-compatible `/models` list and **Test e configura** performs a real inference probe before replacing the saved canonical profile; an optional Anthropic-compatible route is probed separately for Claude Code. Frontier v4 additionally exposes the benchmark-owned skill condition, a matched `no_skill` ↔ `curated_skill` ablation toggle, and a unified run-profile selector for the compact AIOS-Index and benchmark-owned generated long-horizon pressure profiles. Selecting either profile locks task selection to the exact canonical tasks owned by that profile; AIOS-Index also fixes the canonical `no_skill` condition, while progress remains expressed in real task executions rather than a synthetic difficulty score.

Doctor discovery, gateway probing and harness installation run in Qt worker threads. Version probes, HTTP setup checks and installers therefore do not block the GUI event loop. Run cancellation is cooperative: the UI signals Python, the benchmark engine stops at a safe boundary, and active harness process groups are terminated by the benchmark-owned subprocess lifecycle. Qt worker threads are never force-terminated.

## Architecture

- `main.py` — logging configuration, QApplication wiring, controller/runtime/window lifecycle only.
- `config/` — persistent application settings and application logging configuration.
- `core/` — canonical application and benchmark logic.
- `core/benchmark/` — benchmark engine, harness registry, task materialization, adapters, deterministic evaluators, telemetry and reporting.
- `ui/` — native Qt shell, QWebChannel bridge, worker lifecycle and local web presentation.
- `benchmarks/` — task catalogs, fixtures and benchmark-owned reference material.
- `tests/` — deterministic test suite and GUI smoke coverage.

Persistent/operational state is owned by Python. JavaScript never writes settings or benchmark state directly.

### Frontier suites

Frontier v3 and v4 remain separate scientific catalogs so historical results and benchmark semantics stay identifiable, but they share one `FrontierRunner` execution engine.

- **Frontier v3** uses frozen/static task fixtures through `StaticTaskMaterializer`. Task-specific fixture preparation is declared by catalog `setup` entries rather than hard-coded task IDs in the materializer.
- **Frontier v4** uses deterministic seeded families through `ParametricTaskMaterializer`, with generated grader oracles stored outside the agent workspace. Its active families cover expense reporting, configuration traversal, stateful support worlds, dependency/tool gaps, workspace lineage, typed tool recovery, exhaustive local retrieval with provenance, cross-artifact reconciliation, paired premise verification, black-box software reconstruction, longitudinal persistent memory, learned-procedure acquisition/transfer/repair, and observable delegation with deterministic evidence reconciliation.
- **Workspace lineage** generates revision-pinned DAGs with coherent historical revisions and unrelated configuration distractors, requiring agents to recover provenance before deriving effective state.
- **Tool recovery** exposes a benchmark-owned task-scoped loopback API with typed operations, similarly named inactive tools, incomplete list responses, retryable read failures and `response_lost` writes. Operational state is hidden from the agent workspace while the API is active and restored for deterministic final-state evaluation. The verifier checks both final state and benchmark-owned action provenance, including idempotency-key reuse after ambiguous writes.
- **Wide retrieval** generates a frozen seeded local corpus with an explicitly authoritative current tree, plausible mirrors and stale conflicting archives. Agents must return every and only matching record with exact semantic fields and exact JSONL path/line provenance. Strict completion remains binary, while deterministic component metrics expose record precision/recall/F1, field accuracy and provenance recall without using an LLM judge.
- **Cross-artifact consistency** generates an authoritative integer-cent ledger plus archived distractor revisions and requires two independently consumable representations of the same account summary: strict JSON and strict Markdown. Each artifact is graded independently against the hidden canonical transformation and then reconciled field-for-field with the other. Source files are hash-protected, unsupported account rows fail strict grading, and a disagreement between otherwise parseable deliverables is diagnosed as `CROSS_ARTIFACT_MISMATCH`.
- **Epistemic twins** generates paired action requests whose prose makes the same decisive claim while the current authoritative registry supports one twin and contradicts exactly one decisive fact in the other. Opaque IDs and shuffled ordering prevent label-based shortcuts; stale archived registry revisions plausibly support the corrupted claims but are explicitly non-authoritative. The grader measures valid-twin acceptance, corrupted-twin rejection, false-premise compliance, over-cautious refusal, evidence accuracy and pair-level discrimination, so neither an always-comply nor an always-refuse policy can score well.
- **Black-box reconstruction** exposes only a public input/output contract, generated examples and a bounded task-scoped reference probe service. The agent must implement `solution/reconstruct.py` without receiving the hidden reference specification. The reference service is shut down before evaluation; deterministic hidden property, boundary and transfer cases then execute the candidate under a grader-hidden Bubblewrap sandbox. Strict success requires perfect hidden outputs and protocol compliance, while partial property/transfer/field accuracy and probe usage remain diagnostic only.
- **Persistent memory** generates durable preferences, transient session noise, stale historical distractors and deterministic updates across a cold capture task followed by warm application/update tasks. `ParametricTaskMaterializer` restores and persists family-declared state paths per runner, while strict grading verifies the complete durable store, exact update history and exclusion of transient values.
- **Learning & Transfer** generates a uniquely identifiable reusable reporting procedure, then tests warm reuse under concrete schema changes and controlled self-correction after one learned rule is corrupted. Only the declarative `skills/` artifact persists; task data and evidence remain local to each phase, and the deterministic grader requires the repaired skill itself to reproduce the current result.
- **Delegation & Reconciliation** generates independent evidence streams with current/archive and authority/revision conflicts, requires at least two distinct completed non-inferred native subagent lifecycles, and grades an exact provenance-grounded reconciliation artifact. Harnesses without observable structured subagent events are `UNSUPPORTED` rather than failed.
- **Generated long-horizon pressure** is an experiment profile over existing canonical v4 families rather than a synthetic mega-task. It executes ordered exact pressure cells for stateful worlds, dependency worlds, workspace lineage, tool recovery and wide retrieval while holding the generated task seed constant across cells within a repeat. Each cell still uses the ordinary family generator, runtime and deterministic grader.
- **AIOS-Index** is a compact profile over seven existing high-signal Tier-5 Frontier v4 tasks. It owns selection and only the pressure coordinates of the families it executes, is reported separately from the full-suite leaderboard, and records a digest-qualified comparison identity so different profile definitions cannot be silently aggregated.
- **Benchmark health** validates the active Frontier v4 catalog independently of any model or harness. The automated gate checks seeded determinism/diversity, oracle isolation and schema, source integrity, instruction/verifier consistency, untouched-state failure, two-seed golden success, deliberate near-miss failure and deterministic grader runtime bounds.

Materialization is a task/suite concern; harness execution, lifecycle, telemetry, scoring, persistence and scheduling are shared. Frontier v4 pressure defaults are normalized in the parametric family registry so CLI and desktop runs record the same complete coordinate set in execution identity. A future catalog therefore does not require a new execution engine merely because its task materialization strategy changes.

### Frontier v4 skill ablations

V4.3 supports benchmark-owned procedural skill interventions without treating the intervention as model capability. The two conditions are:

- `no_skill` — canonical Frontier v4 baseline;
- `curated_skill` — the same task plus a versioned benchmark-owned procedural skill package when one exists for that task.

A matched ablation runs both arms through the existing interleaved scheduler. Pairing fails closed unless the observations agree on strict model identity, experiment, task/repeat seed, generated variant digest, complete pressure vector, skill package identity and an execution profile that differs only in the skill arm. Ordinary execution fingerprints remain different between arms; a separate ablation fingerprint neutralizes only the arm selector.

Curated-skill rows are deliberately excluded from the canonical capability leaderboard, reliability aggregates, pressure landscapes, harness deltas, failure distribution and efficiency aggregates. They appear in the dedicated `skill_ablations` analysis as `curated_skill - no_skill` lift, pass flips and token deltas. This prevents a benchmark-provided intervention from inflating the measured base capability of a model/harness.

The desktop UI is the canonical interface. The engineering CLI exposes the same controls, for example:

```bash
aiosbench --suite frontier_v4 --piagent --model MODEL --skill-ablation --no-resume
```

Tool-recovery pressure can be varied through the `--v4-tool-*` coordinates, Wide Retrieval pressure through `--v4-retrieval-*`, cross-artifact pressure through `--v4-cross-*`, Epistemic Twins pressure through `--v4-epistemic-*`, and black-box reconstruction pressure through `--v4-black-box-*`. All effective pressure coordinates are recorded in execution identity. The desktop service consumes the same normalized family registry, so even families without dedicated GUI pressure editors retain their canonical defaults in run identity. Persistent Memory, Learning & Transfer, and Delegation & Reconciliation currently use their canonical normalized pressure defaults without dedicated CLI/GUI pressure editors.

### Frontier v4 generated long-horizon pressure

V4.7 adds the benchmark-owned `generated_long_horizon_v1` profile. The current profile contains 15 exact workload cells: three ordered pressure vectors for each of five existing families (`stateful_world`, `dependency_world`, `workspace_lineage`, `tool_recovery`, and `wide_retrieval`). It deliberately varies concrete workload coordinates such as state transitions, required actions, dependency depth/branching, recovery events, source depth, corpus size and distractor volume.

The profile is orchestration, not new task semantics. It has its own stable digest and does not alter the Frontier v4 suite semantic revision. Within one repeat, cells belonging to the same task use the same derived `task_seed`; therefore changes between cells are attributable to the recorded pressure vectors rather than different generated randomness. Repeats change the orchestration seed normally.

`summary.json` exposes `long_horizon_response_curves` grouped by exact profile digest, harness/model identity, suite revision and family. Every point retains its complete pressure vector, pass rate/Wilson interval, score, duration, token diagnostics, variant count and failure distribution. Cell order is a controlled workload path only: AIOS-Bench does **not** assume that a later cell is a scalar or monotonic notion of difficulty, and it does not fit a single cross-family difficulty score.

The desktop exposes the profile through the unified run-profile selector. The engineering CLI equivalent is:

```bash
aiosbench --suite frontier_v4 --piagent --model MODEL horizon
```

`--repeats`, `--seed`, skill ablations and matched multi-harness execution remain available. In `horizon` mode the benchmark-owned profile owns the exact pressure vectors, so manual `--v4-*` pressure options are not consulted. `--total-timeout` remains the existing per-runner active-execution budget and therefore resets for each pressure cell; no hidden profile-wide timeout was introduced.

### Frontier v4 black-box reconstruction

V4.8 adds `software_black_box_001`, a Tier-5 reconstruction task backed by the `black_box_reconstruction` parametric family. The generated variant changes the number of enabled hidden rules, public-example count, live probe budget, ignored distractor-field count and numeric input span. Those effective coordinates are part of normal run identity and can be controlled from the engineering CLI:

```bash
aiosbench --suite frontier_v4 --piagent --model MODEL \
  --v4-black-box-rules 8 \
  --v4-black-box-public-examples 20 \
  --v4-black-box-probe-budget 64 \
  --v4-black-box-distractor-fields 5 \
  --v4-black-box-max-units 900
```

The bounded reference API exists only while the task runtime is active. It never writes the hidden reference specification into the workspace, enforces authentication and a successful-probe budget, and records benchmark-owned probe provenance outside the agent workspace. Hidden verification occurs only after that service is closed. The candidate implementation receives JSONL over stdin and must emit exactly one strict output object per input line; stdout commentary, missing/extra lines or malformed objects are protocol failures.

The hidden verifier deliberately includes generated property cases, exact boundary combinations and high-range transfer cases outside the public-example distribution. It fails closed if grader-hidden sandboxing is unavailable. A passing task therefore means the reconstructed implementation generalized independently of the live reference service rather than replaying cached probe outputs or public examples. `summary.json` exposes dedicated black-box diagnostic aggregates including strict pass rate, property accuracy, transfer accuracy, exact-case accuracy, output-field accuracy, protocol-error rate and probe-budget utilization; none of these partial diagnostics substitutes for strict task success.

### Frontier v4 AIOS-Index and benchmark health

V4.9 adds `aios_index_v1`, a compact routine-development profile over seven canonical Tier-5 tasks. The stable selection name remains `aios_index_v1`, while each run records a digest-qualified comparison identity and the full profile digest in `experiment_context`. Only families actually selected by the profile contribute pressure coordinates to that digest. AIOS-Index uses canonical `no_skill`, supports matched multi-harness execution through the existing scheduler, and is excluded from the ordinary full-suite leaderboard and capability aggregates.

Benchmark health lives in `core/benchmark/health.py` and never invokes an LLM or harness. The pytest suite executes it over every active Frontier v4 task, so generator/oracle/grader regressions fail CI even when ordinary unit tests continue to pass. See `docs/AIOS_INDEX_AND_HEALTH.md` for the exact invariants.

AIOS-Index selection/orchestration and benchmark-health validation are explicitly outside the suite semantic fingerprint because they do not change canonical task semantics. Task catalogs, generators, benchmark-owned runtimes and graders remain inside the fingerprint.

### Frontier v4 persistent memory

V4.10 adds `memory_persist_001`, `memory_persist_002` and `memory_persist_003` as one `persistent_memory` family. The chain measures durable capture, later application when values are omitted from the new prompt, and safe durable updates. Downstream tasks are explicit dependencies and use warm workspaces backed by benchmark-owned persistent state, so a failed predecessor blocks later phases rather than producing misleading independent scores.

The family varies durable facts, transient facts, historical distractors and update count by seed/pressure coordinates. Generated source files are hash-protected and the oracle remains outside the agent workspace. Strict grading requires the complete canonical `.agent_memory/preferences.json` state plus the exact phase report; transient values, lost unrelated preferences or incorrect history fail deterministically.

The persistence mechanism is family-declared rather than memory-task-specific and is intended for reuse by future longitudinal families. Persistent Memory is not in `aios_index_v1`; the compact profile remains the seven-task V4.9 selection pending empirical calibration. See `docs/V4_10_PERSISTENT_MEMORY.md`.

### Frontier v4 learning and transfer

V4.11 adds `learning_acquire_001`, `learning_transfer_001` and `learning_repair_001` as one longitudinal `learning_transfer` family. Acquisition provides generated demonstration CSV/result pairs and requires the agent to infer a reusable declarative reporting skill. Transfer reuses that persisted skill under a changed concrete schema without restating the learned rule values. Repair silently corrupts exactly one learned rule and requires the agent to use generated validation pairs to repair the reusable skill itself.

Acquisition is fail-closed for ambiguity: the generator enumerates the canonical hypothesis space and accepts a variant only when exactly one procedure reproduces every demonstration, including included-record evidence. Warm phases treat the actual persisted `skills/reporting_workflow.json` as the source of truth even though each canonical task has its own derived seed. Only `skills/` persists; prior datasets and evidence do not.

Strict grading verifies protected source integrity, exact learned/adapted/repaired skill state, the exact phase report, and that the persisted skill can deterministically reproduce the current task result. The benchmark does not execute arbitrary agent-authored code for this family. Learning & Transfer is not in `aios_index_v1` pending empirical calibration. See `docs/V4_11_LEARNING_TRANSFER.md`.

### Frontier v4 delegation and reconciliation

V4.12 adds `subagents_reconcile_001` as one Tier-5 `delegation_reconciliation` family. The generated task provides two independent JSONL evidence streams containing scoped claims, current/archive revisions, authority levels, planted conflicts and out-of-scope distractors. The agent must reconcile every scoped topic into `reports/delegation_reconciliation.json` with the exact winning value, decision, conflict state and JSONL path/line provenance while preserving all benchmark-owned inputs.

Content correctness and delegation observability are deliberately separate. The family grader verifies the evidence hierarchy and exact result artifact; the generic `structured_delegation` evaluator requires at least two distinct, completed, non-inferred native subagent lifecycles with stable structured IDs. Plain-text claims of delegation, duplicate starts or failed/cancelled child lifecycles do not satisfy the contract.

The hard capability remains `structured_subagent_events`. The current observable integrations are OpenCode, Goose, Letta, Agent Zero and Claude Code. Hermes exposes delegation but its benchmark one-shot path does not currently provide the required structured child lifecycle; Pi Agent likewise lacks this observable contract. Those harness/task pairs are therefore reported as `UNSUPPORTED`, not model failures.

Canonical telemetry intentionally excludes delegated prompts, arguments and bulk child output. V4.12 can therefore establish that distinct native delegations completed and that the parent system produced the correct reconciliation, but it does not claim per-subagent attribution of each substantive conclusion. AIOS-Index remains the seven-task V4.9 definition pending empirical calibration. See `docs/V4_12_DELEGATION_RECONCILIATION.md`.

Only `benchmarks/tasks/frontier_v3/` and `benchmarks/tasks/frontier_v4/` are active Frontier catalogs. Root-level task JSON files and `frontier_v2.json` are retained historical assets and are not loaded by the desktop/current Frontier services. See `benchmarks/tasks/README.md`.

### Settings and environment precedence

Saved gateway settings own only environment keys that were not explicitly supplied before the application started. Process-level values therefore remain authoritative, while GUI-owned profile values can still be updated or cleared during the same session. The desktop and CLI use the same environment application helper.

### Sensitive harness environment

Harness processes intentionally start from the application environment because local/provider gateways may require credentials. Treat inherited provider credentials as secrets and never put their values in benchmark prompts, task fixtures or committed configuration. The benchmark-specific sensitive variables currently consumed directly include `AIOS_BENCH_OPENAI_API_KEY`, `AIOS_BENCH_DEEPSEEK_API_KEY`, `AIOS_BENCH_AGENTZERO_API_KEY`, `AIOS_BENCH_CLAUDE_API_KEY` and `AIOS_BENCH_CLAUDE_AUTH_TOKEN`; Claude Code may also inherit `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` when the namespaced overrides are absent. Claude Code enables subprocess credential scrubbing for child commands. Generated provider configuration and manifests record references/presence/identity metadata rather than these credential values.

### Logging

Diagnostics are written to stderr and to a rotating application log. By default the file is:

```text
${XDG_STATE_HOME:-~/.local/state}/aios-bench/app.log
```

The file rotates at 2 MiB with three backups. If the state directory cannot be created, AIOS-Bench continues with console logging and reports the logging setup failure there.

## Validation

```bash
.venv/bin/python -m compileall -q main.py config core ui tests
.venv/bin/python -m pytest
.venv/bin/ruff check main.py config core ui tests
```

CI runs these checks on supported Python 3.12+ versions, verifies that Bubblewrap can actually create the grader-hidden sandbox used by V4.8, performs the Qt/WebEngine smoke test offscreen, runs the full Frontier v4 benchmark-health gate through pytest, and separately executes the ordinary managed bootstrap to verify project-local Node/npm and managed harness ownership. Ruff enables the complete `F` (Pyflakes) correctness family in addition to `E9`; broader style migrations such as import sorting or pyupgrade remain separate changes.

## Benchmark properties

AIOS-Bench uses deterministic evaluators rather than an LLM judge. Results record execution identity, model/provider metadata, benchmark semantic fingerprints and failure taxonomy. Frontier v4 additionally records seeded variant identity and pressure coordinates. V4.3 adds deterministic tool-recovery diagnoses for tool selection, schema/argument misuse, excessive retry loops and failed recovery. V4.4 adds deterministic `INCOMPLETE_RETRIEVAL` and `WRONG_AUTHORITY` diagnoses plus dedicated retrieval-quality metrics in `summary.json`. V4.5 adds independent machine/human artifact accuracy, cross-artifact reconciliation metrics and the deterministic `CROSS_ARTIFACT_MISMATCH` diagnosis. V4.6 adds deterministic `FALSE_PREMISE_COMPLIANCE`, `OVERCAUTIOUS_REFUSAL` and `EPISTEMIC_DISCRIMINATION_FAILURE` diagnoses plus dedicated paired-premise metrics in `summary.json`. V4.7 adds benchmark-owned generated pressure profiles and exact family-specific capability response curves while preserving the original family graders and explicit joint pressure vectors. V4.8 adds deterministic black-box reconstruction with a bounded reference probe, post-runtime hidden property/transfer verification, `VERIFICATION_FAILURE` diagnosis and dedicated generalization/probe-use metrics. V4.9 adds a compact high-signal AIOS-Index profile plus an agent-independent health gate over the complete active v4 catalog. V4.10 adds deterministic cross-task persistent-memory capture/application/update with exact durable-state/history verification and benchmark-owned warm-state isolation per runner. V4.11 adds deterministic learned-procedure acquisition, schema transfer and self-correction with fail-closed acquisition identifiability and exact reusable-skill verification. V4.12 adds deterministic delegation-and-reconciliation with matched completed structured subagent lifecycles plus exact evidence/provenance grading. Strict task success still requires all fatal acceptance checks to pass; partial family metrics remain diagnostic rather than a way to convert an incorrect decision set into a pass.

Execution/scoring source files are included in suite semantic fingerprints by default, reducing the risk that a new engine module changes benchmark behavior without invalidating resume/comparability metadata. Derived reporting, benchmark-owned experiment-profile/orchestration modules and benchmark-health validation remain outside that semantic boundary; long-horizon and AIOS-Index profiles carry their own digests so changing an experiment path does not masquerade as a task-semantic revision.

The GUI does not bypass benchmark semantics: it prepares a validated `PreparedRun` through the same Python service used for execution, so catalog validation is performed once and the validated task set is passed to the worker without a second catalog reload.
