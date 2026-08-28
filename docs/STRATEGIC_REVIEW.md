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
