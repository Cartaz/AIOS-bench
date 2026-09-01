# Frontier V4.12 — Delegation & Reconciliation

V4.12 adds one canonical Tier-5 task, `subagents_reconcile_001`, backed by the `delegation_reconciliation` parametric family. The milestone measures whether an agent system can perform observable native delegation and then reconcile conflicting evidence into one deterministic, provenance-grounded decision artifact.

## Why one task

Frontier v3 contained three subagent tasks with overlapping delegation/reconciliation semantics. V4.12 deliberately consolidates the construct into one stronger task instead of reproducing all three. This keeps full-suite runtime under control and avoids counting repeated variants of the same capability as independent coverage.

After V4.12 the active Frontier v4 catalog contains 17 canonical tasks across 13 parametric families.

## Generated workload

Each seeded variant creates two independent JSONL evidence streams plus a scope and reconciliation policy. Scoped topics contain corroborating or conflicting claims; additional records are out-of-scope distractors. Some conflicts are deliberately fabricated current/untrusted claims, while others exercise stale authoritative records or current secondary evidence.

The canonical hierarchy is explicit and deterministic:

1. current evidence outranks archived evidence;
2. within equal status, primary outranks secondary, which outranks untrusted;
3. within equal status and authority, the larger revision wins;
4. equally top-ranked agreeing evidence uses the lexicographically earliest `path:line` provenance;
5. equally top-ranked disagreeing evidence is invalid benchmark data and generation fails closed.

The required result is `reports/delegation_reconciliation.json`. Strict grading checks every scoped topic, canonical value, decision, conflict flag, exact winning JSONL path and 1-based line, winning claim ID, rejected conflicting claim IDs, and protected-source integrity.

## Delegation observability

Content correctness and orchestration evidence intentionally use separate verifier paths.

The `delegation_reconciliation` family grader owns generated evidence semantics and the exact reconciliation artifact. A generic `structured_delegation` evaluator owns the harness-level observability contract. This avoids adding telemetry arguments to every parametric family grader merely for one orchestration-oriented task.

The canonical task requires at least two distinct completed delegation lifecycles. A lifecycle counts only when:

- `subagent_start` is structured and explicitly non-inferred;
- a stable structured call/event ID is present;
- a matching structured `subagent_end` exists for the same ID;
- the end is explicitly non-inferred;
- the completion is not marked as error, failure or cancellation.

Plain-text claims such as “I delegated this work” do not satisfy the check. Duplicate starts using one ID cannot satisfy the two-delegation requirement.

## Harness support

`structured_subagent_events` remains a hard harness capability requirement for category `subagents`. On the current benchmark adapters the task is evaluable for:

- OpenCode;
- Goose;
- Letta;
- Agent Zero;
- Claude Code.

Hermes exposes a delegation tool, but its benchmark one-shot integration does not currently expose structured subagent lifecycle events. Pi Agent also does not expose the required canonical subagent telemetry. Those harness/task combinations are therefore `UNSUPPORTED`, not ordinary model failures.

The benchmark does not infer support from prose or from a generic “delegation” capability. Observability is required because the claimed behavior cannot otherwise be verified fairly.

## Benchmark Health

Benchmark Health now carries benchmark-owned synthetic lifecycle events returned by parametric golden materializers into evaluator checks. This is only a construction self-test: no synthetic event is injected into a real model/harness run.

For V4.12 the health gate therefore checks both halves of the contract:

- the generated evidence/oracle/grader is deterministic, isolated and satisfiable;
- the generic structured-delegation evaluator accepts a valid benchmark-owned lifecycle witness and rejects the untouched/no-event baseline.

The ordinary parametric preflight already passes golden events through the same evaluator path, so health and preflight share the real acceptance semantics rather than a special V4.12 shortcut.

## Pressure coordinates

Canonical defaults are:

- `topic_count = 8`;
- `conflict_count = 4`;
- `distractor_records = 10`;
- `fabricated_claims = 2`.

These coordinates are normalized and recorded in execution identity like every registered Frontier v4 family. V4.12 does not add dedicated CLI or GUI pressure controls. That surface is deferred until empirical sweeps show which coordinates provide useful discrimination rather than merely additional configuration.

## Construct-validity boundary

The telemetry contract proves that at least two distinct native subagent lifecycles occurred and completed, while the deterministic artifact verifier proves that the parent system produced the correct reconciliation and provenance.

It does **not** prove that each individual subagent substantively contributed to one specific evidence stream. AIOS-Bench intentionally does not retain delegated prompts, arguments or bulk subagent outputs in canonical telemetry because those payloads can contain benchmark data, user data or provider output. Stronger contribution attribution would require a different observability/privacy contract and is not claimed by V4.12.

This limitation is preferable to pretending that text claims demonstrate delegation or retaining unrestricted child-agent content merely to make the verifier easier.

## Profiles and scoring

`aios_index_v1` remains the seven-task V4.9 definition. V4.12 is not added to the compact profile before empirical model/harness runs establish discrimination, stability, runtime, redundancy and correlation with the full suite.

No opaque weighted AIOS score is introduced. Strict success remains binary through fatal deterministic checks; diagnostic pressure coordinates and telemetry remain supporting evidence rather than a substitute for correctness.
