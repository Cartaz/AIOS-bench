# Frontier v4 ambiguity and oracle review — 2026-08-27

Scope: `ambiguity_oracle_review` only. This document does **not** satisfy adversarial/cheat review, multi-agent pilot, contamination review, or saturation review.

## Review criteria

A task passes this review only when all three conditions hold:

1. The public prompt and benchmark-provided task specification identify the required result without contradictory instructions.
2. The deterministic oracle verifies the requested behavior/state rather than requiring one arbitrary implementation strategy where alternatives should be valid.
3. A necessary condition enforced by the oracle is not hidden from the agent when that condition is part of the public task contract rather than intentionally hidden test data.

Review inputs included the Frontier v4 task catalogs, the corresponding parametric generators/checkers, pristine reconstruction/verifier contracts for the long-horizon and greenfield families, and the automated baseline/golden validation already exercised by CI.

Validation checkpoint after review-driven task revisions: GitHub Actions run `33093449112`, green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## Findings requiring revision

Two review findings were corrected instead of being waived:

- `autonomy_expense_001` revision 4 required the exact malformed-row count in generated reports through `_report_has_expected()`, while the prompt only said to skip malformed rows. The prompt now explicitly requires reporting the exact skipped count and the task revision is 5.
- `autonomy_causal_gateway_001` revision 4 hash-protected the service registry and restart tooling, but the prompt did not explicitly prohibit changing all of that state. The prompt now identifies the service registry and diagnostic/restart tooling as protected, and the task revision is 5.

The revision increments intentionally invalidate prior task-semantic QA digests and prevent revision-4 results from being silently treated as equivalent to the clarified contracts.

## autonomy_expense_001

**Conclusion: PASS — revision 5.**

The authoritative and alternate CSV roles are disclosed by the generated workspace. The prompt now states that malformed rows must be skipped without guessing and that each generated report must state the exact skipped count. The checker executes the submitted tool independently on both generated datasets, verifies generated totals/counts and the saved primary report, protects source inputs, and rejects embedding generated fixture totals in the tool source. It verifies transferable behavior rather than a specific implementation layout.

## autonomy_causal_gateway_001

**Conclusion: PASS — revision 5.**

The prompt requires diagnosis of the current 502, a root-cause repair that survives restart/reconstruction, and a clean health check afterward. It now explicitly protects logs, diagnostic/restart tooling, the service registry, and unrelated retention state. The checker reconstructs runtime from the source template itself and executes the benchmark-owned health check, so a transient runtime-only patch cannot pass. Historical incident logs remain deliberate distractors rather than hidden required information.

## autonomy_runtime_investigation_001

**Conclusion: PASS — revision 4.**

The prompt explicitly requires use of the benchmark-provided live read-only probe, verbatim preservation of the resulting probe JSON, modification of only the live lane, and preservation of inactive lanes and historical documentation. The checker compares the saved probe evidence to the actual benchmark-owned live payload and verifies only the active route changed to the observed backend port. No hidden solution method beyond the disclosed live probe is required.

## greenfield_registry_001

**Conclusion: PASS — revision 4.**

The generated README is the public behavioral contract. The agent is free to choose internal module structure under `submission/`; the final verifier reconstructs only that bounded submitted tree and tests the documented `registry_app.Registry` API, normalization, validation, duplicate handling, ordering, deletion, persistence, and malformed-storage behavior. Source text or architecture is not compared with the benchmark golden witness.

## long_horizon_pristine_001

**Conclusion: PASS — revision 4.**

The prompt and generated README identify the priority-tier rollout, protected files, required preservation of standard/express semantics, and the need for consistency across validation, pricing, routing, serialization, and integrated service behavior. Verification reconstructs a pristine repository from benchmark-owned baseline files plus only declared mutable artifacts and tests behavior across the integrated path. The checker does not require matching the benchmark golden source implementation.

## tool_use_config_001

**Conclusion: PASS — revision 4.**

The prompt explicitly requires following the generated reference chain from README, reporting every effective setting, the complete ordered chain, and the consumer path, while ignoring historical/decoy files and preserving source state. The checker verifies precisely those disclosed outputs and rejects a report that selects a decoy configuration. It does not constrain the inspection technique used to discover the chain.

## tool_use_branching_001

**Conclusion: PASS — revision 4.**

The prompt discloses that tools differ in authority/freshness, that the live case type/id must first be determined, that broad non-authoritative probing can invalidate the session, and that the final JSON must contain exactly the five named fields including receipts. The authoritative tools themselves return the receipts. The checker verifies the branch-specific receipt chain and protected benchmark tools without prescribing an exact shell-command sequence.

## tool_use_coverage_001

**Conclusion: PASS — revision 4.**

The prompt identifies `config/runtime_index.json` as the authoritative finite loaded set, requires migration of every loaded fragment still using the deprecated key, and explicitly forbids changing already-current loaded fragments or retired history. The evaluator computes exact target completion and false-positive protected modifications; partial completion and out-of-scope edits fail exactly as stated. Continuous coverage metrics remain descriptive and do not weaken the binary task contract.

## Review result

All eight current Frontier v4 tasks satisfy the ambiguity/oracle criteria after the two revision-5 clarifications above. This result supports only `ambiguity_oracle_review=passed`. Promotion remains blocked by the four other pending review categories and by any applicable empirical evidence requirements.
