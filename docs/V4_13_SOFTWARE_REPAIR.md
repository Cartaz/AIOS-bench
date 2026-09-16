# V4.13 — Software repair (migration milestone)

This milestone preserves the frozen Frontier V3 catalog and adds `software_repair_001` to Frontier V4 as a seeded debugging task. It is **not** a refactoring benchmark, a long-horizon pipeline benchmark, or a live-browser benchmark.

## Construct and ownership

- `software_repair` owns generated broken ledger code, public contract/tests, hidden input generation and deterministic grading.
- Two independent defects are selected from three record-selection variants and two cutoff variants.
- A golden implementation repairs the defects, provides regression tests and writes a structured diagnostic report.
- The existing family registry, materializer, runner, scheduler and persistence continue to own their existing responsibilities.
- `isolated_verifier.py` is a generic bounded Bubblewrap-hidden Python verifier also reused by black-box reconstruction; candidate programs are never run outside isolation by the production grader.

The grader checks protected inputs, changed implementation, a correctly-shaped diagnostic artifact, all hidden JSONL outputs and public plus regression unittest success. Regression tests must also fail against the original seeded implementation inside a separate isolated mutation workspace, detecting no-op test files. Sources and produced artifacts are rechecked after test execution to reject test-induced tampering. The grader does not use an LLM judge. Its diagnostic-report schema check establishes structure and substantive length, **not factual truth** of prose; behavioral verification is the authoritative evidence. Mutation rejection proves the suite detects at least one original defect but does not establish comprehensive regression coverage.

## Pressure and comparison identity

`public_cases`, `hidden_cases`, `max_rows` and `distractor_files` are validated workload dimensions, recorded as effective coordinates in the suite manifest and variant digest. Different seeds produce independent public and hidden data; corner cases always cover negative amounts, zero, pending entries and inclusive boundaries.

## Validation and rollout

Apply the accompanying patch to a clean checkout, execute repository compile/Ruff/pytest plus the full catalog-wide Benchmark Health gate in a Linux environment with functional Bubblewrap. Verify a native/CachyOS run separately. Do not label V4.13 closed until the repository test run and a real harness task run succeed.

**Still outstanding before retiring V3:** behavior-preserving refactoring; an integrated multistage software workflow with checkpoints and recovery; browser-based research and source reconciliation; structured action extraction/procedure diff; and empirical multi-model/multi-harness calibration. Maintain historical V3 run artifacts and semantic fingerprints.
