# 2026-08-28 audit remediation

This note maps the findings from the 2026-08-28 Cartaz Desktop Application Standard audit to the corrective implementation. It is a traceability record, not a replacement for the canonical validation commands.

## Finding closure matrix

| Finding | Corrective implementation | Regression/verification hook | Status |
| --- | --- | --- | --- |
| F1 — Doctor inspection on GUI thread | `DesktopRuntime.inspect_doctor()` runs Doctor discovery in the existing `QThread` worker lifecycle; install returns its post-install inspection payload from the worker; bridge/frontend consume `doctorChanged` asynchronously. Doctor inspection accepts cooperative cancellation between bounded probes, and each version probe uses the benchmark-owned subprocess lifecycle so timeout cleanup covers the process group. | `tests/test_runtime_doctor.py`, `tests/test_runtime_shutdown.py`, GUI smoke | Addressed in patch; full Qt smoke pending in canonical environment |
| F2 — narrow Ruff gate | `ruff.toml` enables `E9` plus the complete Pyflakes `F` family. Import sorting/pyupgrade remain a later style migration rather than being mixed into this correctness pass. | canonical Ruff command | Addressed in patch; full-repo Ruff execution pending |
| F3 — suite not whitelisted in catalog | `BenchmarkService.catalog()` rejects names outside `SUITE_NAMES` before filesystem access. | `tests/test_run_service_preparation.py` | Addressed |
| F4 — Agent Zero unbounded HTTP request | Agent Zero derives an explicit message timeout from the active task budget and caps control/log/cleanup calls to a shorter bound. The task executor passes the active timeout to the client environment. | `tests/test_agentzero_timeout.py` | Addressed |
| F5 — duplicate profile-environment semantics | Desktop and CLI use `apply_settings_environment()`. Process values present before desktop service startup are protected; profile-owned values can be updated/cleared without stale state. | `tests/test_doctor_environment.py`, existing Doctor tests | Addressed |
| F6 — production `assert` for Pi RPC pipes | Pipe availability is checked explicitly; failure performs owned-process cleanup and raises `RuntimeError`. | `tests/test_pi_rpc_pipe_validation.py` | Addressed |
| F7 — inconsistent selector focus / unreachable responsive breakpoint | Custom selectors have explicit `:focus-visible`; body minimum width is removed; the native minimum size is reduced so the 1100 px responsive layout is reachable. | `tests/test_audit_architecture.py`, GUI smoke | Addressed in patch; visual/native check still required |
| F8 — divergent reference-check code style | Reference-check modules use future annotations, descriptive names, type hints and a shared `CheckResult` alias while keeping category routing explicit. | `tests/test_audit_architecture.py`, reference-oracle tests | Addressed in patch; full oracle suite pending |
| F9 — duplicate run validation / O(n) checkpoint rereads | GUI preparation returns immutable `PreparedRun`; execution consumes the already selected tasks. `BenchmarkRunner` keeps a signature-aware latest-result cache updated on append and invalidated by external changes. | `tests/test_run_service_preparation.py`, `tests/test_checkpoint_cache.py` | Addressed |
| F10 — undocumented Italian UI / legacy catalogs | README declares the UI language and active suite boundary; `benchmarks/tasks/README.md` labels root JSON catalogs as historical provenance. | `tests/test_audit_documentation.py` | Addressed |
| F11 — radius/logging informational gaps | UI uses the 28/22/16/12 radius scale for the audited elements; application logging adds a bounded XDG rotating file plus console fallback. Result snapshots without a verified publication seal are documented as historical only. | `tests/test_audit_architecture.py`, `tests/test_logging_config.py`, `tests/test_audit_documentation.py` | Addressed |
| F12 — task executor reaches runner private members | `task_execution.py` depends on the public `TaskExecutionRunner` protocol (`prepare_workspace`, `record_event`, `result_identity`, `record_result`). Compatibility aliases remain in the runner for existing callers only. | `tests/test_audit_architecture.py` | Addressed |
| F13 — task-ID-specific static setup | `Task.setup` is catalog data; `StaticTaskMaterializer` dispatches setup capabilities, not task IDs. The three affected v3 tasks declare setup explicitly and increment task revisions. | `tests/test_audit_architecture.py`, catalog tests | Addressed |

## Additional audit note: sensitive environment

Harness launches intentionally inherit the application environment because provider gateways may require credentials. The README now explicitly identifies the benchmark-specific Agent Zero/Claude credential variables, the Anthropic credentials that Claude may inherit, and Claude Code's subprocess credential scrubbing. Credential values remain runtime secrets and must not be committed into profiles, prompts or fixtures.

## Validation state

The corrective overlay has been syntax-compiled successfully, both modified JavaScript modules pass `node --check`, and the documentation/logging tests that can run without the untouched repository or PySide6 pass locally. This overlay is not a complete repository checkout, so the milestone is **not merge-validated yet**. Before closure on the real working tree run exactly:

```bash
.venv/bin/python -m compileall -q main.py config core ui tests
.venv/bin/python -m pytest
.venv/bin/ruff check main.py config core ui tests
```

Then run the Qt/WebEngine offscreen smoke test and a native CachyOS/KDE launch check. Any failure reopens the corresponding finding; do not weaken a test or lint rule merely to make the gate green.
