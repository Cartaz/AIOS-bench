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

The adversarial tool-branching family materializes benchmark-owned tool wrappers backed by a stateful loopback service. The authoritative inspection result determines which branch-specific lookup is valid. Plausible legacy/cache/metrics/archive/directory tools are distractors, and broad probing or selection of the wrong branch contaminates that task session. The final artifact must contain branch-specific receipts verified by the deterministic oracle. This avoids using harness-specific textual log parsing as the ground truth for tool selection. Receipt/session hardening against an agent that deliberately escapes the benchmark workspace is part of the later contamination/anti-cheat work; current tools follow the same workspace trust boundary as the rest of Frontier.

The coverage-migration family verifies complete finite-set work rather than only the first correct edit. The hidden oracle records the required target set and protected out-of-scope files. Strict PASS still requires exact completion, while deterministic TP/FP/FN, precision, recall and Jaccard completion are persisted as descriptive evidence. `summary.json` aggregates these already-persisted metrics under `coverage_completeness`; reporting never recomputes task truth or weakens capability scoring.

The pristine-refactor family verifies selected agent-authored source artifacts outside the mutable task workspace. AIOS-Bench reconstructs a fresh temporary repository from a benchmark-owned baseline, overlays only the task-declared source artifacts, and runs hidden integration/regression checks in a separate Python subprocess. Workspace-local tests, modified documentation, or edits to protected high-level integration code therefore cannot become the final verifier. This is pristine evaluation within the existing workspace trust model, not an OS-level security sandbox; stronger isolation remains part of later anti-cheat work.

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

CI runs these checks on supported Python 3.12+ versions and performs the Qt/WebEngine smoke test offscreen.

## Benchmark properties

AIOS-Bench uses deterministic evaluators rather than an LLM judge. Results record execution identity, model/provider metadata, benchmark semantic fingerprints and failure taxonomy. Frontier v4 additionally records seeded variant identity and pressure coordinates.

Execution/scoring source files are included in suite semantic fingerprints by default, reducing the risk that a new engine module changes benchmark behavior without invalidating resume/comparability metadata.

The GUI does not bypass benchmark semantics: it calls the same Python runner/scheduler services used by the engine.
