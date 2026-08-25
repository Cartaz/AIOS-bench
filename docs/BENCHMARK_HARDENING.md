# Benchmark hardening policy

AIOS-bench is a practical local benchmark, not an attempt to maximize task count. Improvements must increase information per unit of runtime.

## Runtime budget

- A normal full benchmark for one model/harness configuration should target **<= 12 hours** on the reference local setup.
- **24 hours is a hard design ceiling**, not a target. A proposed default task that can push a normal full run beyond that ceiling must replace or consolidate existing coverage instead of simply being appended.
- Repeats, pressure sweeps, exhaustive robustness campaigns and research experiments are opt-in and are not part of the normal full-run budget.
- Cheap deterministic benchmark self-validation does not count against agent runtime, but it should remain fast enough for routine development.

## Coverage policy

Prefer a small number of high-information Tier 3-5 tasks. Add a task only when it measures a capability or failure mode that existing tasks cannot measure cleanly. Prefer deeper decision-making, ambiguity, recovery, verification, memory/learning, conflicts and realistic AI-OS work over longer prompts or artificial context exhaustion.

Frontier v4 should expand by **representative parametric families**, not by cloning every static v3 task. The initial target is roughly 4-6 families spanning the highest-value capability clusters. A family may replace redundant static coverage once it is validated.

Security should be introduced as a compact adversarial slice (roughly 2-3 tasks/families), focusing on indirect prompt injection, untrusted tool/document instructions and excessive/destructive agency. It should not become a standalone hundreds-case security benchmark.

Robustness should primarily use generated variants and opt-in perturbation/fault campaigns. Equivalent prompt wording, distractors, schema variation, missing information and selected tool faults should reuse the same underlying task semantics rather than multiplying the default catalog.

## Oracle quality gate

Every deterministic grader should satisfy three contracts:

1. **Negative baseline:** the untouched fixture fails.
2. **Positive witness:** a benchmark-owned valid solution passes.
3. **Adversarial near-miss:** plausible but semantically wrong outputs fail.

Near-miss cases should target the actual construct being measured: wrong claim/evidence pairing, incomplete diffs, fabricated provenance, incorrect state transitions, shortcut/hard-coded answers, forbidden side effects, or false delegation telemetry. The goal is not mutation-test volume; one or two high-value near-misses per vulnerable oracle are preferable to dozens of superficial mutations.

A deterministic grader is not considered strong merely because it is deterministic. Structural checks should be supplemented with semantic invariants wherever the expected semantics can be encoded without an LLM judge.

## Scoring and comparability

Keep deterministic outcome/state grading authoritative. Do not add an LLM judge to the Frontier capability score. Subjective report quality may be collected later as a separate diagnostic metric.

Preserve strict suite/execution/model fingerprints, matched interleaving, unsupported/blocked semantics, repeated-trial reliability statistics and historical results. New benchmark revisions must not overwrite or silently merge older results.

## Expansion order

1. Harden the weakest existing v3 oracles with semantic invariants and adversarial near-miss tests.
2. Add a few high-information Frontier v4 families covering distinct capability clusters.
3. Add a compact security/adversarial slice.
4. Add opt-in metamorphic/fault-injection campaigns that reuse existing task semantics.
5. Add at most a small number of interactive insufficient-information tasks if they expose a capability not measurable by the existing workspace model.

At every milestone, reassess total default runtime and remove/reuse redundant coverage before adding more.