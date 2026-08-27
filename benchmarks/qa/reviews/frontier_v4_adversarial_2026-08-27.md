# Frontier v4 adversarial / cheat review — 2026-08-27

## Scope

This review evaluates whether each Frontier v4 deterministic grader rejects a plausible solution that appears locally successful while violating a material part of the task contract. It complements, but does not replace, the untouched negative baseline and the benchmark-owned positive golden witness.

The automated witnesses are owned by `core/benchmark/parametric_adversarials.py` and are executed by `validate_parametric_baseline()` against the same acceptance checks used for normal benchmark results. Validation schema `aios-bench/parametric-validation/v3` records the witness name, whether it was rejected and its partial acceptance score.

This review is deliberately narrower than host-level anti-cheat. It does **not** claim that an unconfined agent cannot escape its workspace, inspect the public repository or read benchmark internals. Runtime filesystem/process isolation and public-repository contamination remain separate M12 requirements. A compatible-host Bubblewrap proof is still required before M12 can close.

## Review criteria

A task passes this review only when:

1. the adversarial witness is a plausible shortcut or incomplete solution rather than an untouched/no-op duplicate;
2. the witness preserves enough of the requested behavior to exercise the grader boundary meaningfully;
3. the exact production grader rejects it deterministically;
4. rejection follows from a task-semantic violation rather than a harness-specific textual convention;
5. the positive golden witness continues to pass the same grader.

The CI checkpoint after integrating these witnesses was green on Python 3.12, 3.13 and 3.14 for install, compile, Ruff and pytest.

## autonomy_expense_001

Witness: `correct_totals_wrong_malformed_count`.

The witness implements a generic CSV report tool, computes the monthly totals from the supplied file and skips malformed rows, but deliberately reports the malformed-row count off by one. This is meaningfully stronger than the untouched baseline: the main accounting result is correct while a required auditability fact is wrong. The grader rejects it because the exact malformed count is part of the revised task contract.

Conclusion: **passed** at task/grader level.

## autonomy_causal_gateway_001

Witness: `symptom_only_runtime_patch`.

The witness patches only generated runtime state so the current symptom can appear repaired while leaving the source template wrong. The grader reconstructs runtime from the source of truth, causing the shortcut to disappear exactly as it would after a restart. This directly tests the causal/persistence distinction the task is intended to measure.

Conclusion: **passed** at task/grader level.

## autonomy_runtime_investigation_001

Witness: `probe_observed_but_stale_lane_repaired`.

The witness records the correct live probe evidence but edits the lane suggested by stale documentation rather than the lane observed at runtime. It therefore demonstrates that merely producing the expected evidence artifact is insufficient; the repair must actually reconcile belief with live state. The grader rejects the wrong-lane edit and also protects inactive lanes.

Conclusion: **passed** at task/grader level.

## tool_use_config_001

Witness: `correct_settings_incomplete_reference_chain`.

The report contains the correct effective settings and consumer path but omits one element of the authoritative reference chain. This tests completeness of grounded provenance rather than only value extraction. The grader rejects the incomplete chain while remaining implementation-independent about how the agent traverses files.

Conclusion: **passed** at task/grader level.

## tool_use_branching_001

Witness: `correct_case_fields_fabricated_lookup_receipt`.

The witness supplies the correct case type/id/value and inspection receipt but fabricates the branch lookup receipt. This tests that knowing or guessing the answer is not enough: the required authoritative branch interaction must have produced the exact receipt chain. The deterministic receipt verifier rejects the fabrication.

Conclusion: **passed** at task/grader level. Host-level access to benchmark secrets remains covered by the separate sandbox/contamination requirement noted above.

## tool_use_coverage_001

Witness: `partial_target_set_migration`.

The witness correctly migrates one required fragment and leaves the remainder untouched. It is a realistic locally-correct-but-incomplete solution. The finite-set oracle rejects it because false negatives remain, while still recording partial recall/completion descriptively.

Conclusion: **passed** at task/grader level.

## long_horizon_pristine_001

Witness: `all_but_one_required_policy_module`.

The witness applies benchmark-correct changes to all but one required policy module. This is a plausible long-horizon coordination failure and is evaluated only after reconstruction into a pristine verifier tree. Hidden integration/regression verification rejects the internally inconsistent rollout.

Conclusion: **passed** at task/grader level.

## greenfield_registry_001

Witness: `api_complete_but_nonpersistent_registry`.

The witness implements the documented Registry API and basic validation/list/delete behavior but stores entries only in memory. It can satisfy superficial single-process API checks while violating persistence across instances. The fresh hidden verifier rejects the implementation because persistence is part of the public contract.

Conclusion: **passed** at task/grader level.

## Result

All eight Frontier v4 tasks pass the scoped adversarial/grader review. The review does not change capability scoring and does not promote any task to `stable`. Remaining promotion evidence is multi-agent pilot data, contamination review and saturation review. M12 additionally still requires compatible-host proof of the strong workspace/verifier isolation contract before the milestone can be closed.
