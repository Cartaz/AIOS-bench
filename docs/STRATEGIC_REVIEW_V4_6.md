# Frontier V4.6 strategic review — Epistemic Twins

Status: implementation and review complete; formal closure is established when the canonical CI matrix on this commit passes.

This milestone review supplements `docs/STRATEGIC_REVIEW.md`. It records the V4.6 design comparison, whole-project boundary review, benchmark-health checks and issues found during self-review before the milestone is considered closed.

## Design it twice

Two materially different implementation shapes were considered.

### Alternative A — separate valid/corrupted catalog tasks

Each twin could have been a separate Frontier task, with the scheduler or reporting layer matching the two runs afterward.

This has an important cost in the existing architecture: Frontier task seeds are derived from the task identity. Separate task IDs therefore naturally produce different generated worlds. Making them share one hidden base scenario would require a new cross-task seed/pairing contract, special scheduler identity, or task-specific exceptions in materialization/reporting. That would spread one benchmark-family concern into generic execution infrastructure.

### Alternative B — paired cases inside one generated variant

One `epistemic_twins` family generates multiple hidden valid/corrupted pairs inside a single deterministic workspace. The agent sees only independently reviewable, shuffled requests and authoritative/current versus archived evidence. The hidden oracle owns pair membership and exact expected decisions.

**Selected:** Alternative B. It keeps pair semantics inside one deep family, requires no new runner/scheduler/runtime path, and produces exact within-variant measurements of both false-premise compliance and over-cautious refusal.

## Complexity and ownership

- **Resolved:** `parametric/epistemic_twins.py` exclusively owns pair generation, authoritative evidence construction, stale distractors, protected-input identity and deterministic grading.
- **Resolved:** `ParametricTaskMaterializer` remains the only owner of seed derivation, workspace construction and oracle placement. Hidden pair labels never enter the agent workspace.
- **Resolved:** the generic `VariantGrade` contract carries strict success, transparent partial accuracy, family metrics and deterministic failure hints without adding epistemic branches to task execution.
- **Resolved:** `epistemic_analysis.py` is derived reporting only and is explicitly excluded from semantic suite fingerprinting. The generator/grader remains semantic by default.
- **Resolved:** CLI and desktop execution obtain effective defaults through the same parametric registry. No GUI-owned copy of epistemic pressure defaults was introduced.
- **Resolved:** no new task-scoped service, network API, subprocess, harness adapter branch, scheduler or persistence format was required.

## Correctness and information hiding

- Every generated pair contains one record for which all decisive current facts support `isolate` and one record for which exactly one decisive fact is corrupted.
- Both request texts assert the same decisive production/critical/containment-ready premise. Request prose is explicitly treated as an untrusted claim, not evidence.
- The current policy and current service registry are authoritative. Archived policies and archived registry revisions are plausible but explicitly historical; stale registry rows intentionally support corrupted requests so authority selection matters.
- Request IDs, system IDs and ordering are generated and shuffled. Pair membership, valid/corrupted labels and the corruption field exist only in the hidden oracle.
- README/task instructions require each case to be checked independently against current evidence. They do not claim that class counts vary when the generator intentionally creates balanced pairs.
- Every task-visible input is hash-protected. Modifying current evidence, archived distractors, policy, request data or instructions invalidates grading before result accuracy is considered.

## Self-review findings resolved before closure

### Outcome leakage through service naming

The first implementation named the corrupted record with a `-shadow` suffix. That made a hidden benchmark label inferable without checking evidence.

**Resolved at the generator:** valid and corrupted records now use the same neutral `service-<opaque-id>` naming rule. Regression tests reject `shadow`, `valid` or `corrupt` markers in generated service names.

### Misleading pressure-coordinate naming

The initial `archive_files` coordinate produced one archived policy and one archived registry for each unit, so the name understated what the coordinate represented.

**Resolved:** the coordinate is now `archive_revisions`. One revision intentionally contains both a historical policy and a historical registry snapshot. CLI naming, run identity and tests use the same semantic name.

### Instruction/count mismatch

The first generated README said not to assume a fixed number of supported/unsupported cases even though the family intentionally produces balanced valid/corrupted pairs.

**Resolved:** the instruction now says not to infer decisions from ordering, identifiers or naming and to verify every request independently. The benchmark no longer gives a false statement about its generation contract.

### Malformed extra decisions bypassed the strict cardinality contract

The first result parser ignored decision-list entries that were not objects or did not contain a usable `case_id`. If every expected decision was otherwise exact, such an ignored malformed extra entry could leave `missing`, `extra` and `duplicate` sets empty and incorrectly satisfy strict success despite the instruction requiring every request exactly once and no extra case.

**Resolved at the grader:** malformed decision entries are now counted explicitly as `invalid_decision_count`; any non-zero count blocks strict success. The count is preserved in deterministic family metrics and aggregated in `epistemic_twin_metrics`. Regression coverage includes both an object without `case_id` and a non-object entry alongside an otherwise exact golden result.

## Scoring and failure semantics

Strict success requires:

- the exact authoritative source identity;
- every request exactly once and no extra, duplicate or malformed decision entry;
- exact `premise_supported` and action decisions;
- exact evidence copied from the current registry;
- all protected inputs unchanged.

Partial score is `full_decision_accuracy`; it is diagnostic and cannot convert a failed fatal parametric check into a task pass. Structural violations such as an extra malformed entry therefore may coexist with 1.0 decision accuracy while strict success remains false; the separate `invalid_decision_count` makes the reason explicit rather than silently folding schema integrity into semantic accuracy. Because every variant contains balanced valid/corrupted twins, an otherwise exact always-comply or always-refuse strategy reaches only 0.5 decision accuracy.

Dedicated metrics preserve both sides rather than collapsing them into one score:

- valid-twin acceptance rate;
- corrupted-twin rejection rate;
- false-premise compliance rate;
- over-cautious refusal rate;
- premise accuracy;
- evidence accuracy;
- pair-action accuracy;
- missing/extra/duplicate/invalid decision counts.

Deterministic diagnoses distinguish `FALSE_PREMISE_COMPLIANCE`, `OVERCAUTIOUS_REFUSAL` and mixed `EPISTEMIC_DISCRIMINATION_FAILURE`. Runtime timeout/crash/infrastructure precedence remains unchanged; family diagnoses apply only after successful execution followed by failed deterministic grading.

## Benchmark-health review

Deterministic tests cover:

- same seed + same pressure => identical oracle identity and byte-identical workspace;
- changed seed or pressure => changed variant digest;
- each hidden pair has one supported twin and one exactly-one-field corrupted twin;
- no valid/corrupted label leakage in task-visible service naming;
- stale archive evidence is plausibly supportive of corrupted requests;
- exact golden solution => strict pass and full pair metrics;
- always comply => failure, false-premise compliance = 1.0, pair accuracy = 0;
- always refuse => failure, over-cautious refusal = 1.0, pair accuracy = 0;
- errors in both directions => mixed discrimination diagnosis;
- malformed extra decision entries => strict failure and explicit invalid-decision diagnostics;
- current or archived input tampering => protected-input failure;
- generic baseline validation rejects untouched variants and accepts benchmark goldens;
- CLI and desktop run identity record the same complete pressure defaults;
- derived summary includes baseline/no-skill epistemic metrics while excluding curated-skill rows from canonical capability analysis;
- deterministic failure hints do not override timeout or crash precedence.

## Change-amplification review

V4.6 adds one deep parametric family, one catalog task, one derived-analysis module and localized registry/CLI/report/test/documentation updates. `FrontierRunner`, `ParametricTaskMaterializer`, task execution, scheduling, checkpointing, telemetry, persistence, QWebChannel and harness adapters remain unchanged.

Explicit family dispatch is longer than in early Frontier v4, but it still provides direct, readable mappings with one owner and no duplicated algorithms. Reflection/plugin discovery would currently increase cognitive load more than it reduces change amplification. Revisit only if later milestones produce actual dispatch duplication or ambiguous ownership.

## Deliberate deferrals

- A generic epistemic-task DSL/plugin framework is not introduced. Additional domains should be concrete scenarios only when they test meaningfully different premise-verification capability.
- Live external evidence is excluded; current versus archived local evidence keeps authority and truth deterministic.
- A dedicated dashboard panel is deferred. `summary.json` persists both directional metrics and the existing dashboard still exposes canonical task/failure outcomes. Permanent presentation space should be based on real-run usefulness rather than added speculatively.
- Probabilistic confidence/calibration is not claimed. V4.6 measures deterministic decision discrimination, not self-reported probability calibration.

## Review conclusion

The touched area retains one source of truth for generated semantics, one materialization path and one generic evaluation pipeline. The review found and removed benchmark leakage/obscurity in outcome-signaling names, a misleading archive coordinate/instruction contract, and a strict-grader hole around ignored malformed extra decisions. No material ownership leak, duplicated execution path, hidden external dependency or harness-specific workaround remains known.

Formal closure requires this final review commit to pass the canonical Python 3.12, 3.13 and 3.14 CI matrix with installation, compileall, Ruff and pytest observed green. Only then should V4.7 begin.
