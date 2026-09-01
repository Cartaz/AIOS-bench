# Frontier V4.11 — Learning & Transfer

## Purpose

V4.11 adds a longitudinal `learning_transfer` family to Frontier v4. The family measures whether an agent can infer a reusable procedure from demonstrations, preserve it across tasks, adapt only the concrete schema mapping when the environment changes, and repair the learned procedure itself after a controlled corruption.

The family deliberately does not ask the agent to write arbitrary executable code. The learned artifact is a declarative JSON skill and the benchmark provides a deterministic local application tool. This keeps procedure learning distinct from software-engineering ability and keeps the verifier independent of an LLM judge.

## Canonical task chain

1. `learning_acquire_001` — cold acquisition. The agent receives generated CSV/result demonstrations, infers the unique compatible reporting procedure, persists `skills/reporting_workflow.json`, and applies it to a fresh dataset.
2. `learning_transfer_001` — warm schema transfer. The learned rule values are omitted. The agent must reuse the persisted skill, adapt only the affected concrete column mappings described by the current schema transition, preserve learned rule semantics, and apply the updated skill.
3. `learning_repair_001` — warm self-correction. Exactly one persisted rule is silently corrupted before the task. Generated validation pairs expose the discrepancy. The agent must identify the incorrect rule, repair the reusable skill itself, and produce the current result plus an exact correction record.

Later tasks depend explicitly on their predecessor. If an earlier task fails, the normal runner dependency contract blocks the downstream phase instead of treating it as an independent observation.

## Learned skill contract

The persisted skill uses schema `aios-bench/learned-reporting-skill/v1` and contains two objects:

- `columns`: semantic roles `status`, `group`, `amount`, `direction`, and `verified` mapped to concrete CSV column names;
- `rules`: `required_status`, `minimum_abs_cents`, `direction_policy`, and `require_verified`.

Only `skills/` is declared as persistent family state. Demonstration files, current datasets, schema documents, validation cases, generated tools, and reports remain task-local. This prevents a later phase from succeeding by reading prior benchmark inputs rather than the learned procedure.

## Acquisition identifiability

A benchmark that expects one exact learned rule must ensure the demonstrations identify that rule uniquely. V4.11 therefore treats identifiability as a generator invariant rather than assuming it.

The acquisition teaching set covers the Cartesian product of status, threshold-relevant amount bands, direction, and verification state. Demonstration result files contain both the aggregate summary and exact included record IDs. The generator enumerates the complete canonical candidate space and fails closed unless exactly one candidate reproduces every demonstration. This avoids penalizing an agent for choosing a different procedure that is observationally equivalent on the supplied evidence.

## Independent task seeds and persistent truth

Each canonical task retains the ordinary Frontier v4 task-derived seed. Transfer and repair must therefore not regenerate the learned rule from their own local seed. During a real warm chain they read the actual persisted skill first. Seed-derived fallback state exists only so standalone benchmark-health/preflight materialization remains self-contained and deterministic.

A dedicated regression test runs acquisition, transfer, and repair with their distinct derived task seeds and verifies that learned rule semantics flow from persisted state across the chain.

## Deterministic grading

The grader requires all of the following:

- every benchmark-owned source named in `protected_sha256` remains byte-identical;
- the persisted declarative skill exactly matches the canonical learned/adapted/repaired procedure;
- the phase report exactly matches the hidden deterministic result;
- applying the persisted skill to the current task dataset reproduces that result.

The last condition prevents a model from passing by fixing only the final report while leaving a broken reusable skill behind.

## Pressure coordinates

`LearningTransferPressure` currently records:

- `demo_count = 3`
- `rows_per_demo = 54`
- `evaluation_rows = 60`
- `group_count = 6`
- `distractor_columns = 4`
- `schema_shift_fields = 4`

The coordinates are normalized into ordinary Frontier v4 execution identity through the shared family registry. V4.11 does not add dedicated CLI or GUI pressure editors; this is a deliberate interface restraint pending empirical evidence that these coordinates deserve routine sweep controls.

## Profile boundaries

V4.11 changes canonical Frontier v4 task semantics/catalog and therefore participates in the normal suite semantic fingerprint. It does not modify `aios_index_v1` or the generated long-horizon profile. AIOS-Index remains the seven-task V4.9 definition until empirical calibration demonstrates that a learning task improves its signal/time trade-off.

## Validation

The first branch-head functional matrix for V4.11 was GitHub Actions run `33474557843`. Python 3.12, 3.13 and 3.14 all passed install, Bubblewrap verification, compile, Ruff and pytest. The Python 3.12 job reported 458 passing tests.

Milestone closure additionally requires a successful branch-head matrix after this documentation and strategic review are committed.
