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

Development and review: [PR #44](https://github.com/Cartaz/AIOS-bench/pull/44). The [V3-retirement issue #43](https://github.com/Cartaz/AIOS-bench/issues/43) remains the release gate. On a clean checkout run `./install.sh`, `.venv/bin/python -m compileall -q main.py config core ui tests`, `.venv/bin/ruff check main.py config core ui tests`, `.venv/bin/python -m pytest`, and the full-catalog Benchmark Health gate with a functional Bubblewrap sandbox. Verify a native CachyOS/KDE harness run separately; CI on Ubuntu does not establish that native hardware and inference are functional. Do not label V4.13 fully closed until the repository tests and real harness task run succeed.

**Still outstanding before retiring V3:** behavior-preserving refactoring; an integrated multistage software workflow with checkpoints and recovery; browser-based research and source reconciliation; structured action extraction/procedure diff; and empirical multi-model/multi-harness calibration. Maintain historical V3 run artifacts and semantic fingerprints.
