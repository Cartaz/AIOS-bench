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

The desktop UI is currently Italian. It provides suite selection, per-harness toggles, per-task toggles, `Tutti` / `Nessuno` controls, benchmark configuration, progress/results, safe run cancellation, and an integrated Setup / Doctor panel for harness readiness and local-model gateway settings.

Doctor discovery and harness installation run in Qt worker threads. Version probes and installers therefore do not block the GUI event loop. Run cancellation is cooperative: the UI signals Python, the benchmark engine stops at a safe boundary, and active harness process groups are terminated by the benchmark-owned subprocess lifecycle. Qt worker threads are never force-terminated.

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
- **Frontier v4** uses deterministic seeded families through `ParametricTaskMaterializer`, with generated grader oracles stored outside the agent workspace.

Materialization is a task/suite concern; harness execution, lifecycle, telemetry, scoring, persistence and scheduling are shared. A future catalog therefore does not require a new execution engine merely because its task materialization strategy changes.

Only `benchmarks/tasks/frontier_v3/` and `benchmarks/tasks/frontier_v4/` are active Frontier catalogs. Root-level task JSON files and `frontier_v2.json` are retained historical assets and are not loaded by the desktop/current Frontier services. See `benchmarks/tasks/README.md`.

### Settings and environment precedence

Saved gateway settings own only environment keys that were not explicitly supplied before the application started. Process-level values therefore remain authoritative, while GUI-owned profile values can still be updated or cleared during the same session. The desktop and CLI use the same environment application helper.

### Sensitive harness environment

Harness processes intentionally start from the application environment because local/provider gateways may require credentials. Treat inherited provider credentials as secrets and never put their values in benchmark prompts, task fixtures or committed configuration. The benchmark-specific sensitive variables currently consumed directly are `AIOS_BENCH_AGENTZERO_API_KEY`, `AIOS_BENCH_CLAUDE_API_KEY` and `AIOS_BENCH_CLAUDE_AUTH_TOKEN`; Claude Code may also inherit `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` when the namespaced overrides are absent. Claude Code enables subprocess credential scrubbing for child commands. Manifests record configuration/presence metadata rather than these credential values.

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

CI runs these checks on supported Python 3.12+ versions and performs the Qt/WebEngine smoke test offscreen. Ruff enables the complete `F` (Pyflakes) correctness family in addition to `E9`; broader style migrations such as import sorting or pyupgrade remain separate changes.

## Benchmark properties

AIOS-Bench uses deterministic evaluators rather than an LLM judge. Results record execution identity, model/provider metadata, benchmark semantic fingerprints and failure taxonomy. Frontier v4 additionally records seeded variant identity and pressure coordinates.

Execution/scoring source files are included in suite semantic fingerprints by default, reducing the risk that a new engine module changes benchmark behavior without invalidating resume/comparability metadata.

The GUI does not bypass benchmark semantics: it prepares a validated `PreparedRun` through the same Python service used for execution, so catalog validation is performed once and the validated task set is passed to the worker without a second catalog reload.
