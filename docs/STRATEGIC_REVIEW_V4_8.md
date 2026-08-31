# Frontier V4.8 strategic review — Black-Box Reconstruction

Status: implementation and strategic review complete; formal milestone closure requires the canonical CI matrix on this review commit to pass.

This review supplements `docs/STRATEGIC_REVIEW.md`. V4.8 adds one generated software-engineering family that requires behavior inference and reconstruction without exposing a reference implementation. The existing Frontier runner, parametric materializer, task runtime, scoring, telemetry, persistence and reporting pipeline remain authoritative.

## Purpose

The milestone evaluates whether an agent can infer a deterministic program from a public contract, a limited set of examples and a bounded live probe interface, then produce a standalone compatible implementation that generalizes to hidden cases.

The canonical task is `software_black_box_001`, family `black_box_reconstruction`. It varies explicit workload coordinates:

- hidden rule count;
- public example count;
- probe budget;
- ignored distractor-field count;
- numeric input span.

Success is not based on a textual explanation. The agent must create `solution/reconstruct.py`, and the deterministic grader executes it against hidden generated property and transfer cases.

## Design comparison

### Alternative A — ship a hidden reference executable inside the workspace

Rejected. Even if undocumented, a local reference binary or source artifact would create a leakage and reverse-engineering shortcut that bypasses the intended behavioral-inference task.

### Alternative B — grade only on the public examples

Rejected. A fixture-specific lookup table could score perfectly without reconstructing the behavior. Public examples are observations, not the oracle.

### Alternative C — bounded live reference service plus offline hidden verification

Chosen. During the task, a benchmark-owned localhost service exposes only the public contract and bounded probes. After agent execution the runtime is closed before artifact evaluation. Hidden verification then runs the submitted implementation independently against seeded property and transfer cases.

This keeps the problem behavior-observable while preserving a hidden oracle and makes generalization deterministically testable.

## Ownership and abstraction boundaries

### `core/benchmark/black_box_service.py`

Owns the deterministic reference behavior, input validation, public contract semantics, probe accounting and probe provenance. It has no HTTP or runner responsibilities.

### `core/benchmark/black_box_api.py`

Owns the localhost transport, bearer-token binding, generated workspace client and bounded runtime lifecycle. It returns the existing generic `TaskRuntime`; no new runner or executor path was introduced.

### `core/benchmark/parametric/black_box_reconstruction.py`

Owns family pressure validation, deterministic generation, public examples, hidden test-case generation and deterministic grading. The hidden oracle contains the seeded reference specification and verification seeds outside the agent workspace.

The grader returns the common `VariantGrade` contract, including strict pass/fail plus deterministic diagnostics such as property accuracy, transfer accuracy, exact-case accuracy, field accuracy, protocol errors and probe use.

### `core/benchmark/materialization.py` and task execution

The existing `ParametricTaskMaterializer` remains the sole owner of generated task materialization and hidden-oracle persistence. It starts the family runtime through the generic runtime hook.

`task_execution.py` closes the runtime in its `finally` block before deterministic artifact evaluation begins. Therefore the reference service is unavailable during hidden verification by construction rather than convention.

### Reporting

`reconstruction_analysis.py` owns family-specific derived diagnostics. `report.py` feeds it only canonical capability rows, preserving the existing intervention and long-horizon filtering rules. No parallel leaderboard or scoring engine was added.

## Hidden-verifier isolation

V4.8 materially strengthened the sandbox boundary because the submitted artifact is executable code.

The hidden verifier:

- requires the Bubblewrap grader-hidden sandbox;
- sees the task workspace but not the benchmark repository/oracle material;
- uses the base Python interpreter rather than depending on a `.venv` path hidden with the repository;
- executes Python with isolated mode (`-I`);
- receives a minimal deterministic environment;
- runs with a private network namespace so it cannot contact the live reference API or external endpoints;
- runs with a private PID namespace so it cannot inspect unrelated host grader/runtime processes;
- has a bounded verification timeout.

If the required grader-hidden sandbox is unavailable, verification fails closed instead of silently falling back to an exposed verifier.

The installation and CI path now verifies Bubblewrap capability functionally rather than only checking whether the executable exists.

## Scientific identity and reproducibility

The black-box family is canonical Frontier v4 task semantics, so its generator, reference behavior and grader participate in the suite semantic fingerprint. Pressure values are normalized through the existing parametric registry and recorded as complete execution identity.

Same seed and pressure values reproduce the hidden specification, public examples and hidden verification distributions; different seeds or pressure coordinates change the variant digest.

The public-example distribution intentionally covers only part of the numeric range. Transfer cases emphasize the held-out high range and combinations of tags/activity, while property cases include generated boundary values. This prevents a public-example memorization strategy from being equivalent to reconstruction.

## Findings discovered during milestone review

### The first verifier test used a stale `VariantGrade` field name

A test still asserted `partial_credit` after the grading contract had standardized on `score`.

**Resolved:** the V4.8 test now uses the canonical `VariantGrade.score` field rather than reintroducing a compatibility alias solely for one test.

### Repository hiding initially broke the canonical workspace path

The first Bubblewrap rebind attempted to recreate the task workspace after masking the repository, but the bind target did not exist inside the sandbox.

**Resolved:** the sandbox preserves the workspace through a private alias before masking the repository, recreates the canonical parent path, and exposes the canonical workspace through a symlink to the preserved alias. Integration tests execute the actual Bubblewrap command and verify both source hiding and workspace writes.

### `/workspace` could not be created under the read-only root

An intermediate fix attempted to create a top-level alias after mounting `/` read-only.

**Resolved:** the preserved workspace alias lives below the private writable `/tmp` tmpfs instead. The final contract avoids a writable global host-root mount.

### Hidden verification could still observe host network/process state

Repository hiding alone was insufficient for executable submissions: code under test could theoretically reach a service endpoint or inspect host processes.

**Resolved:** the dedicated verifier sandbox profile now adds both network and PID namespace isolation. Regression tests assert both capabilities.

### Probe accounting needed concurrency safety

The runtime uses a threaded HTTP server. A plain integer budget check/increment could race under concurrent probes.

**Resolved:** probe budget consumption and provenance writes are serialized by the service so the configured successful-probe ceiling is deterministic under concurrent requests.

## Complexity review

### Change amplification

The family uses the existing parametric pressure registry, materializer, runtime hook, evaluator and report pipeline. There is one reference behavior implementation and one family grader; the HTTP layer does not duplicate reference rules.

### Cognitive load

The behavior service, transport/runtime and generated family semantics are distinct modules. The family file is relatively large because it owns generation plus hidden verification, but the responsibilities are cohesive and currently share the same deterministic oracle model. Splitting it further would add interfaces without removing a present dependency.

### Hidden dependencies

The main operational dependency introduced by V4.8 is Bubblewrap for strict hidden execution. This is explicit in installation verification, CI and failure behavior. The benchmark does not silently downgrade black-box verification when that capability is absent.

### Special cases

No harness-specific V4.8 execution path was added. The task declares the existing `benchmark_local_runtime` capability because the bounded probe service is localhost-owned; harnesses unable to access benchmark-local runtimes remain unsupported rather than receiving a weaker alternate task.

The sandbox accepts a verifier execution role in addition to harness names. This is intentionally contained in the sandbox module; no runner or task semantics depend on it.

### Parametric registry growth

`core/benchmark/parametric/__init__.py` now dispatches ten families and its materialize/runtime/evaluate branches are becoming a visible change-amplification point. This is not a V4.8 correctness defect, and replacing it mid-milestone would create unnecessary semantic churn after the family is already validated.

**Explicit deferral to V4.9:** benchmark-health consolidation should replace repeated family dispatch branches with one declarative family specification registry if the refactor can preserve current public functions and exact semantics. V4.9 is the appropriate milestone because it is specifically about benchmark health and consolidation rather than adding another capability family.

## Validation coverage

Deterministic tests cover, among other cases:

- pressure validation and unknown coordinates;
- same-seed reproducibility and seed/pressure sensitivity;
- absence of hidden reference specification from the workspace;
- bounded reference probes, authentication and cleanup;
- concurrent probe-budget enforcement;
- golden implementation success on hidden property and transfer suites;
- fixture-specific and protocol-noisy implementations failing hidden verification;
- protected-source tampering failure;
- family-specific derived analysis;
- CLI pressure coordinates and result identity;
- task catalog, GUI catalog, registry and validation integration;
- sandbox repository hiding with real Bubblewrap execution;
- verifier network and PID isolation;
- install/CI Bubblewrap capability checks.

Before this review commit, the implementation HEAD `edbc3fc52d9e2348bfb0b87856445c3209d2b723` passed the complete GitHub Actions matrix on Python 3.12, 3.13 and 3.14, including install, Bubblewrap capability verification, compileall, Ruff and pytest.

## Deliberate deferrals

### No arbitrary-language reconstruction contract

The first family requires a Python implementation. Allowing arbitrary compiled languages would require language/runtime discovery, build isolation, additional sandbox policies and broader reproducibility controls. That complexity is not necessary to test black-box reconstruction itself.

### No adaptive probe-budget allocation

The budget is a fixed pressure coordinate. Adaptive budgets based on model behavior would make later observations conditional on earlier outcomes and weaken matched comparability.

### No stochastic fuzzing

Hidden cases are generated deterministically from the oracle seed. Deterministic property expansion gives the benchmark the useful part of fuzz-style coverage without introducing run-to-run randomness.

### No live-network reference service

The reference service remains localhost benchmark-owned. Remote service dependence would add availability, versioning and confidentiality problems without improving the target capability.

## Review conclusion

V4.8 adds executable black-box reconstruction without introducing a new runner, an LLM judge or an exposed reference implementation. The final design separates reference semantics from transport, closes the live service before grading, verifies generalization on hidden deterministic distributions and executes untrusted candidate code inside a fail-closed repository-hidden, network-isolated and PID-isolated sandbox.

The review found and resolved concrete failures in grading-contract assumptions and Bubblewrap workspace construction, then strengthened concurrency and verifier isolation beyond the initial implementation.

The only material architectural pressure identified is the growing parametric dispatch registry. It is explicitly deferred to V4.9 because consolidation is the next milestone's purpose and the current public interfaces can remain stable while that internals-only refactor is evaluated.

Formal V4.8 closure requires this review commit to pass the canonical Python 3.12, 3.13 and 3.14 CI matrix with installation, Bubblewrap verification, compileall, Ruff and pytest observed green. Only then should V4.9 begin.
