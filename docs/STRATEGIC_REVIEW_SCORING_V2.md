# Strategic review — integer scoring v2

## Milestone

This milestone changes score resolution only. Frontier task prompts, tiers, generated pressure coordinates, workload generation, timeout behavior, harness capability declarations and strict deterministic PASS requirements are intentionally unchanged.

## Problem found

The previous public score combined two different concepts:

- deterministic artifact acceptance contributed 80%;
- process execution success contributed 20%;
- any task whose final `Trajectory.success` was false was capped at 49.

That created artificial score bands and made a `/100` scale misleading. Parametric families with legacy binary graders amplified the problem by discarding useful deterministic evidence before the public score was calculated.

## Design alternatives considered

### 1. Keep 80/20 and only round to integers

Rejected. It would change presentation without fixing the missing score bands or the coupling between correctness and process outcome.

### 2. Add more top-level acceptance checks to every task catalog

Rejected. It would duplicate family-specific oracle knowledge in task JSON, create change amplification, and make the catalog responsible for grading internals.

### 3. Separate quality from outcome and deepen the grader abstraction

Chosen. The public score is now deterministic acceptance quality only, quantized to an integer 0–100. PASS/WRONG/TIMEOUT/etc. remain a separate operational outcome. Existing strict checkers remain the source of truth for PASS, while legacy parametric families expose partial deterministic quality through one focused `partial_credit` module.

## Ownership and interfaces

- `core/benchmark/scoring.py` owns public score semantics and integer quantization.
- Parametric family checkers continue to own strict correctness.
- `core/benchmark/parametric/partial_credit.py` owns partial-quality decomposition for the six families that previously collapsed failures to binary zero.
- `VariantGrade.passed` remains strict; `VariantGrade.score` may be fractional.
- `evaluate_artifacts()` continues to combine deterministic check credits and enforce fatal checks. A high partial score cannot override a failed fatal requirement.
- Runner failure taxonomy continues to own operational state and comparability. Infrastructure, crash and unavailable rows remain non-comparable with `score=None`.

## Comparability

The scoring contract is explicitly named `aios-bench/scoring/v2`. In addition, `scoring.py` and the parametric grader modules are semantic benchmark sources included in `FrontierRunner._revision()`. Therefore runs produced before and after this milestone receive different `suite_revision` fingerprints and are not silently grouped as the same benchmark semantics.

## Complexity review

- No new event bus, plugin layer or grader framework was introduced.
- Partial-credit logic is centralized rather than duplicated across six generators/checkers.
- Existing strict checkers were not rewritten, reducing the risk that increased resolution accidentally changes PASS semantics.
- The new module reads only benchmark-owned oracle data and final workspace state; no LLM judge or harness-specific telemetry is used for correctness credit.
- Provenance remains explicitly represented for mediated-world and tool-recovery tasks.
- Difficulty calibration is deferred until complete empirical runs are available; no speculative tier or pressure adjustments were made.

## Validation requirements

Before merge, CI must pass the repository's ordinary compile, Ruff and pytest matrix. Focused regression tests additionally require:

- every public integer score from 0 through 100 is representable;
- half-point quantization is deterministic and half-up;
- invalid/non-finite acceptance values are rejected;
- execution failure does not cap deterministic quality;
- strict PASS behavior remains intact on a complete legacy-family solution;
- all six former binary parametric families can produce deterministic partial credit on incomplete work.

## Deferred work

Task difficulty/tier calibration remains deliberately deferred until the current benchmark execution is complete and there is enough empirical evidence to distinguish harness/model capability from task calibration effects.
