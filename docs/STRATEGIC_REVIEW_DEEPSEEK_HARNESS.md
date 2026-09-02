# Strategic review — DeepSeek Harness integration

Status: **CLOSED for merge**

Scope: add the official `deepseek-ai/deepseek-harness` CLI as an AIOS-Bench harness without changing benchmark task semantics.

## Design decisions

The built-in `headless` profile is used instead of a custom SDK integration. It already owns the one-task process lifecycle, stdout/stderr behavior and exit semantics, so AIOS-Bench does not duplicate those responsibilities or couple itself to internal DeepSeek Harness APIs.

Ambient `DSH_HOME` reuse was rejected because saved sessions, plugins and preferences would contaminate benchmark runs. A writable DSH home inside the task workspace was also rejected because it would mix harness state with graded task state. The selected design retains only a run-owned configuration source and mounts it read-only into a fresh process-lifetime `DSH_HOME` inside Bubblewrap's private `/tmp`.

The current headless process interface does not emit a stable structured tool/subagent event stream. AIOS-Bench therefore does not infer such events from prose and leaves tasks that require observable structured delegation as `UNSUPPORTED`.

## Ownership and complexity

- Python remains the canonical owner of benchmark state and runtime configuration.
- `deepseek_runtime.py` owns DSH-specific endpoint validation and settings rendering.
- `deepseek_adapter.py` owns invocation construction and capability declaration.
- The common runner, scheduler, deterministic evaluators, persistence, server metrics and task runtimes are reused unchanged.
- The harness registry remains the single owner of active harness selection.
- The sandbox has one narrow DSH state-mount hook rather than a second execution path.
- Doctor now separates `installed` from `ready`, allowing runtime prerequisites to block a detected harness without misreporting it as absent.
- No new frontend framework or Node dependency was added to AIOS-Bench itself; Node remains an external prerequisite of the optional DSH CLI.

## Runtime boundaries

- Missing or invalid model/endpoint configuration fails before execution.
- Retained settings never contain authentication material.
- DSH telemetry is disabled during benchmark runs.
- DeepSeek execution fails closed if Bubblewrap is unavailable or explicitly disabled.
- Doctor enforces the upstream Node range exactly: `^22.19.0 || >=24.0.0`; Node 23 is intentionally rejected.
- Browser and structured subagent-event capabilities are not claimed without observable support.

## Change-amplification review

Adding DeepSeek Harness required no changes to task catalogs, generators, graders, scheduler algorithms, report schemas or frontend event handling. CLI and GUI discover it from the canonical harness registry. The only cross-cutting changes are Doctor readiness reporting and the sandbox mount needed for DSH runtime state.

The adapter lives in its own module rather than enlarging the generic adapter module. The registry composes it with the existing adapters. Generalizing this into a plugin/factory layer now would be speculative; that should be reconsidered only if several future harnesses need separate adapter modules.

## Validation observed

GitHub Actions run `33646097523` succeeded on Python 3.12, 3.13 and 3.14. Every matrix job passed native setup, Bubblewrap verification, project installation, compileall, Ruff and pytest. Python 3.12 reported **473 passed**.

The tests cover invocation construction, endpoint/model validation, retained-settings isolation, Bubblewrap mounting, fail-closed sandbox behavior, capability non-claims, Doctor installation metadata, exact Node compatibility and installed-but-blocked readiness.

## Explicit deferrals

- No live end-to-end execution against an installed `dsh` binary and real local model was observed in CI; optional harness runtimes remain machine-level Doctor/smoke checks.
- Structured tool/subagent telemetry remains unavailable through the current headless interface and should only be added when an upstream stable structured interface exists.
- The integration pins `@deepseek-ai/dsh@0.1.2-alpha.5`; upgrading it requires explicit revalidation of the CLI and configuration contract.

No unresolved architectural finding blocks merge.