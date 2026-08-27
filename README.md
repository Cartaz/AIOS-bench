# AIOS-Bench

AIOS-Bench is a reproducible benchmark application for local AI operating-system agents. The desktop application is the canonical user interface; benchmark logic and state live in Python under `core/`, while the local HTML/CSS/JavaScript frontend is presentation-only and communicates through QWebChannel.

## Requirements

- Linux desktop (CachyOS/Arch + KDE is first-class)
- Python 3.12+
- Qt/PySide6 with WebEngine
- Optional harness runtimes configured through the in-app Setup / Doctor workflow

## Install

```bash
chmod +x install.sh
./install.sh
```

The installer resolves the repository root from any working directory, creates or repairs `.venv`, installs runtime/development requirements, and verifies the critical Qt/application imports.

## Launch

```bash
.venv/bin/python main.py
```

The GUI provides suite selection, per-harness toggles, per-task toggles, `Tutti` / `Nessuno` controls, benchmark configuration, progress/results, safe run cancellation, and an integrated Setup / Doctor panel for harness readiness and local-model gateway settings.

Run cancellation is cooperative: the UI signals Python, the benchmark engine stops at a safe boundary, and active harness process groups are terminated by the benchmark-owned subprocess lifecycle. Qt worker threads are never force-terminated.

## Architecture

- `main.py` — logging, QApplication wiring, controller/runtime/window lifecycle only.
- `config/` — persistent application settings.
- `core/` — canonical application and benchmark logic.
- `core/benchmark/` — benchmark engine, harness registry, task materialization, adapters, deterministic evaluators, telemetry and reporting.
- `ui/` — native Qt shell, QWebChannel bridge, worker lifecycle and local web presentation.
- `benchmarks/` — task catalogs, fixtures and benchmark-owned reference material.
- `tests/` — deterministic test suite and GUI smoke coverage.

Persistent/operational state is owned by Python. JavaScript never writes settings or benchmark state directly.

### Frontier suites

Frontier v3 and v4 remain separate scientific catalogs so historical results and benchmark semantics stay identifiable, but they share one `FrontierRunner` execution engine.

- **Frontier v3** uses frozen/static task fixtures through `StaticTaskMaterializer`.
- **Frontier v4** uses deterministic seeded families through `ParametricTaskMaterializer`, with generated grader oracles stored outside the agent workspace.

Materialization is a task/suite concern; harness execution, lifecycle, telemetry, scoring, persistence and scheduling are shared. A future catalog therefore does not require a new execution engine merely because its task materialization strategy changes.

Frontier v4 may also use benchmark-owned loopback runtime fixtures when a task must distinguish static inspection from live state. These services are started by the materializer, bind only to `127.0.0.1`, have bounded startup/shutdown, and are always cleaned up by the runner even if task execution raises. Ephemeral endpoint files are operational state and are not treated as seeded semantic fixture content.

The causal gateway family distinguishes source-of-truth repair from generated-state patching by reconstructing runtime state during verification. The runtime-investigation family exposes live state only through a read-only probe while static documentation contains a deliberately stale but plausible hypothesis.

The adversarial tool-branching family materializes benchmark-owned tool wrappers backed by a stateful loopback service. The authoritative inspection result determines which branch-specific lookup is valid. Plausible legacy/cache/metrics/archive/directory tools are distractors, and broad probing or selection of the wrong branch contaminates that task session. The final artifact must contain branch-specific receipts verified by the deterministic oracle. This avoids using harness-specific textual log parsing as the ground truth for tool selection. Receipt/session hardening against an agent that deliberately escapes the benchmark workspace remains part of M12 contamination/anti-cheat work.

The coverage-migration family verifies complete finite-set work rather than only the first correct edit. The hidden oracle records the required target set and protected out-of-scope files. Strict PASS still requires exact completion, while deterministic TP/FP/FN, precision, recall and Jaccard completion are persisted as descriptive evidence. `summary.json` aggregates these already-persisted metrics under `coverage_completeness`; reporting never recomputes task truth or weakens capability scoring.

The pristine-refactor family verifies selected agent-authored source artifacts outside the mutable task workspace. AIOS-Bench reconstructs a fresh temporary repository from a benchmark-owned baseline, overlays only the task-declared source artifacts, and runs hidden integration/regression checks through the shared pristine-verifier boundary. When Bubblewrap is both installed **and capability-tested as usable**, the verifier sees only a minimal read-only runtime/system view plus the writable pristine tree, uses an ephemeral `/tmp`, and separates the network/process namespaces. If the host exposes a `bwrap` binary but denies the required namespaces, `auto` mode records an explicit unconfined fallback and its reason instead of claiming isolation; `required` mode fails closed.

The greenfield-registry family starts without implementation source code. The agent creates a self-contained tree under `submission/`; AIOS-Bench copies only that bounded tree into a fresh temporary verifier directory, ignores operational caches, rejects symlinks and excessive submissions, then uses the same pristine-verifier boundary for hidden deterministic API, validation, persistence and integration checks. Internal module structure is not compared against the benchmark golden witness: only the documented public contract and behavior determine capability success. Verification metrics persist the isolation strategy, filesystem/network confinement flags and any isolation fallback reason.

The harness workspace sandbox uses the same Bubblewrap capability-probe principle. Presence of the executable alone is not considered evidence that namespace isolation works. `AIOS_BENCH_SANDBOX=required` therefore means the confinement capability must actually be available; `auto` may fall back, but that fallback remains explicit in the run metadata.

### Task QA lifecycle

Frontier v4 has a machine-readable QA registry under `benchmarks/qa/` using schema `aios-bench/task-qa/v4`. QA lifecycle state is separate from benchmark capability scoring: a task can have a valid deterministic grader while still being only a `pilot` because multi-agent or saturation evidence is pending.

Each QA record is tied to both `task_revision` and a SHA-256 semantic digest derived from task-owned meaning: prompt, category/mode/tier, revision, tags, required capabilities, dependencies, capability acceptance, behavioral acceptance and semantic trajectory reference. A meaning-changing edit therefore invalidates the prior audit even if someone forgets to bump the numeric revision.

Manual-review evidence is additionally bound to a separate `review_context_digest` over the task semantic digest plus its current exposure state. Exposure is intentionally not part of benchmark semantic identity, but moving a task from private/limited circulation to a public repository changes contamination assumptions and therefore invalidates the old review context automatically. Completed reviews use structured provenance (`kind`, `reference`, `observed_at`, optional `notes`); pending reviews require `evidence=null`.

QA audits also age independently of historical benchmark reproducibility. The current maintenance interval is 180 days. An expired pilot record remains structurally valid but becomes maintenance-due and cannot be promotion-ready; an expired `stable` record violates the current promotion contract until it is reviewed again. The report date is injectable in tests so aging behavior is deterministic rather than dependent on the CI clock.

Frontier v4 automated QA is exposed as five named checks: same-seed determinism, different-seed variation, untouched negative-baseline rejection, benchmark-owned golden-witness acceptance and benchmark-owned adversarial-witness rejection. Missing and failed checks remain distinct. The adversarial witnesses are plausible but materially wrong solutions—such as symptom-only runtime repair, partial finite-set migration or an API-complete but non-persistent registry—and run through the exact production graders. They are QA evidence only and never become a second capability score.

The ambiguity/oracle, scoped task/grader adversarial and public-repository contamination reviews have been completed for all eight current Frontier v4 tasks and are recorded under `benchmarks/qa/reviews/`. The ambiguity review found two genuine public-contract gaps: `autonomy_expense_001` and `autonomy_causal_gateway_001` were clarified and bumped to revision 5 rather than silently preserving revision 4. All tasks remain `pilot`; only multi-agent and saturation reviews remain pending.

The contamination review deliberately does not call the public suite “clean.” Public task prompts, generators, graders and golden materializers expose family semantics and canonical strategies, so every current Frontier v4 task remains `contamination_risk=high`. Seeded generation protects concrete future instance values from fixed-fixture memorization but cannot restore novelty of public task semantics. Results are suitable for disclosed public/open-benchmark comparisons; they must not be described as uncontaminated novel-task generalization without independent model-provenance evidence.

Run-local generated oracles remain outside the agent workspace and under local result storage. `results/.local/` is ignored by Git, and aggregate publication produces only derived summary/dashboard outputs plus their seal. A publication regression injects an oracle-like sentinel into raw evaluation/artifact fields and verifies that it does not transit into `summary.json`, `dashboard.html` or `publication.json`. Accidental publication of a concrete oracle/secret compromises that generated instance; semantic/family leakage requires revision or retirement rather than merely reseeding. The full revision/rotation/retirement policy is recorded in the contamination review document.

Promotion requires current automated validation, completed manual review evidence, no known issues, a fresh audit and a non-retired lifecycle. Contamination risk remains descriptive rather than becoming a capability-score penalty. The scoped adversarial and contamination reviews do **not** claim protection against an agent escaping an unconfined workspace and reading public benchmark internals. Compatible-host proof of the strong Bubblewrap verifier/workspace boundary remains an M12 requirement.

### Semantic reference trajectories

Selected tasks may define task-owned semantic trajectory milestones such as inspecting the contract, authoring the change and verifying the result. AIOS-Bench compares these milestones only after capability success and only when the required canonical event types are available from non-inferred harness telemetry. Runner-owned metrics/evaluations and inferred events are excluded. The result records ordered milestone completion, reliable events observed up to semantic completion and post-completion activity under `reference_trajectory`; `summary.json` aggregates only these persisted values under `reference_trajectory_efficiency`.

Trajectory references are descriptive and always `affects_score=false`: they never change capability correctness or score, and extra inspection or verification is not treated as a failure. No numeric “times slower than reference” metric is published yet because Frontier v4 does not yet have an empirically calibrated successful reference trajectory for these new tasks. `calibrated_reference_effort_available=false` remains explicit until real run data can support that comparison rather than assigning an arbitrary reference budget.

### Deterministic behavioral oracles

Task catalogs may define optional `behavioral_acceptance` checks in addition to their normal capability `acceptance` oracle. Behavioral checks are deterministic, task-owned observations used to characterize how an agent behaved; they do not change capability success or score.

The initial behavioral-oracle schema supports required state, forbidden state, preservation of pre-task files, untouched decoy files and required structured evidence events. Preservation baselines are captured by the benchmark after workspace materialization and before the agent runs. Behavioral results are persisted independently as `behavioral_evaluation`.

Generic trajectory telemetry never guesses whether an action was useful, destructive or irrelevant. Such claims require explicit deterministic task evidence. Behavioral state paths are restricted to safe relative workspace paths, and behavioral definitions are part of the suite semantic revision through the catalog/source fingerprint.

### Resource telemetry

Resource telemetry is observational and never changes deterministic task scoring.

Every task automatically samples the AIOS-Bench process tree and the client host at a one-second interval by default. Results keep process-attributed CPU/RAM separate from host totals. On Linux DRM systems, AIOS-Bench also attempts per-client GPU/VRAM attribution from DRM `fdinfo`, while retaining host-total GPU/VRAM counters as separate context. Unsupported GPU telemetry remains explicitly unavailable rather than being reported as zero.

The sampling interval can be changed from the CLI with `--resource-poll-interval`.

Inference-server resource telemetry is optional and uses a small read-only HTTP agent rather than SSH or arbitrary remote command execution. Run the agent on the inference-server host against the already-running server PID:

```bash
AIOS_BENCH_RESOURCE_TOKEN='<token>' \
  .venv/bin/python -m core.benchmark.resource_agent \
  --pid <INFERENCE_SERVER_PID> \
  --bind 0.0.0.0 \
  --port 8766
```

Then point AIOS-Bench at it from the client:

```bash
export AIOS_BENCH_SERVER_RESOURCE_URL='http://SERVER_IP:8766'
export AIOS_BENCH_RESOURCE_TOKEN='<token>'
```

The bearer token is optional on loopback but recommended whenever the resource agent is reachable over the LAN. The server channel records the inference-server process-tree RSS and, where DRM attribution is available, its VRAM and GPU engine usage. Baseline, mean, p95, peak and peak delta are kept separately from server-host totals. This resource channel is independent of llama.cpp `/metrics`, which remains the source for verified token counts and inference throughput.

## Validation

```bash
.venv/bin/python -m compileall -q main.py config core ui tests
.venv/bin/python -m pytest
.venv/bin/ruff check main.py config core ui tests
```

CI runs these checks on supported Python 3.12+ versions and performs the Qt/WebEngine smoke test offscreen. CI also installs Bubblewrap so tests exercise the important case where the binary exists but the hosted runner denies namespace creation; capability probing must detect that condition and avoid a false confinement claim.

## Benchmark properties

AIOS-Bench uses deterministic evaluators rather than an LLM judge. Results record execution identity, model/provider metadata, benchmark semantic fingerprints and failure taxonomy. Frontier v4 additionally records seeded variant identity and pressure coordinates.

Execution/scoring source files are included in suite semantic fingerprints by default, reducing the risk that a new engine module changes benchmark behavior without invalidating resume/comparability metadata.

The GUI does not bypass benchmark semantics: it calls the same Python runner/scheduler services used by the engine.
