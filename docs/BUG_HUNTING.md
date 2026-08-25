# Post-audit corrective campaign

This document records the adversarial bug-hunting pass performed after the desktop/strategic refactor.

## Findings closed

- Removed obsolete `Report A.md` and `Report B.md`.
- Local harness sandboxes hide the AIOS-Bench repository by default and expose only the writable task workspace.
- Agent Zero launches with the canonical `core.benchmark.agentzero_client` module and the current Python interpreter.
- Saved local-model gateway settings are applied by Python before benchmark execution.
- Unexpected single-harness failures abort run metadata rather than leaving a run marked `running`.
- Multi-harness cleanup attempts every runner even when one abort fails.
- Pi RPC drains stderr concurrently to prevent pipe backpressure deadlocks.
- Doctor installation uses owned subprocess lifecycle/cancellation; privileged and remote shell installers remain manual.
- QWebChannel run inputs receive strict runtime type/range validation.
- Frontend backend transport is centralized in `ui/web/backend.js` and WebEngine smoke tests exercise the loaded DOM/QWebChannel path.
- `total_timeout` is defined consistently as active execution budget per harness (reset per repeat), for sequential and interleaved execution.
- Bubblewrap availability is treated as a runtime capability, not merely an installed binary; `auto` records an unconfined fallback when namespaces are unavailable, while `required` fails closed.

## Remaining deliberate limitations

- Agent Zero is a trusted local transport exception: its local client needs package access, while grader/golden/fixture/result material is masked and the model executes in a separately isolated service project.
- A real Bubblewrap integration test runs when the host permits unprivileged namespaces; hosted CI environments that prohibit namespace creation skip that kernel-dependent execution check while retaining structural sandbox tests.
- The test-suite compatibility alias for the historical `aios_bench` namespace remains test-only technical debt and should not be reintroduced into production code.
