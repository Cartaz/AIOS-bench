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
