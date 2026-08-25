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
