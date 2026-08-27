# Frontier v4 public-repository contamination review — 2026-08-27

## Scope and conclusion

Frontier v4 is published in a public repository. This review therefore does not attempt to classify the suite as contamination-free. Its purpose is to determine what is exposed, whether AIOS-Bench accidentally publishes per-run hidden truth, and which claims remain scientifically supportable under public exposure.

**Conclusion:** the current eight Frontier v4 tasks pass the contamination review as an explicitly **high-risk public/open benchmark**. Passing this review means the exposure has been assessed and bounded; it does **not** reduce `contamination_risk` from `high` and does not imply that a tested model has never seen AIOS-Bench source code or task families during training or post-training.

Frontier v4 results are therefore suitable for local longitudinal comparison, harness comparison and reproducible agentic-system evaluation under a disclosed public-test assumption. They must not be described as an uncontaminated estimate of novel-task generalization unless independent model-provenance evidence supports that stronger claim.

## What is public

The repository intentionally exposes:

- task prompts, revisions, tags and acceptance declarations;
- parametric family generator code;
- deterministic grader code;
- benchmark-owned golden materializer code used to prove grader satisfiability;
- adversarial witness definitions used for QA;
- aggregate published benchmark results.

A model trained or deliberately tuned on this repository could therefore learn the intended family structure and canonical solution strategies. Deterministic seeded variants prevent simple memorization of one fixed fixture's concrete values, but they cannot make public task semantics novel again. Parametric generation is a robustness measure, not a proof against training contamination.

## What remains run-local

Per-run generated oracle instances are stored under the local run tree and are consumed by the evaluator from `run_dir/oracles/`. They are not placed in the agent workspace. `results/.local/` is ignored by Git, while the tracked `results/` directory contains only the public aggregate README/dashboard/summary snapshot.

The publication pipeline regenerates `summary.json` and `dashboard.html` from raw results and seals only hashes/file metadata for the raw source index. It does not copy raw `results.jsonl`, run-local workspaces or oracle files into the published result directory.

A dedicated regression injects `AIOS_BENCH_HIDDEN_ORACLE_SENTINEL_9f3e7c` into raw evaluation detail and an artifact-like raw field. The publication test requires the sentinel to remain present in raw input while being absent from `summary.json`, `dashboard.html` and `publication.json`. The checkpoint was observed green on Python 3.12, 3.13 and 3.14.

## Task-level assessment

### autonomy_expense_001

Concrete rows, malformed positions and totals are seed-generated. Public code reveals the reporting contract and generation distribution but not the future variant's concrete totals. Risk remains high because the intended strategy and grader semantics are public.

Disposition: **review passed, residual risk high**.

### autonomy_causal_gateway_001

Ports, decoys and runtime state are generated per variant. Public source reveals that durable repair belongs in the source template and that runtime is reconstructed. A trained model could therefore know the causal pattern in advance even though it cannot memorize the future port value.

Disposition: **review passed, residual risk high**.

### autonomy_runtime_investigation_001

Live lane/runtime values vary by seed and are exposed to the agent through the benchmark runtime probe. Public code reveals that static documentation is deliberately stale and that live evidence is authoritative. This prevents fixed-answer memorization but not family-strategy contamination.

Disposition: **review passed, residual risk high**.

### tool_use_config_001

Reference-chain depth, settings and distractors vary. Public generator/grader code reveals the traversal pattern and completeness requirements. Exact future settings are not a fixed public answer.

Disposition: **review passed, residual risk high**.

### tool_use_branching_001

Branch, case id, expected value, observation id and receipt secret are variant-specific. The per-run secret is not published through aggregate results. Public code nevertheless exposes the receipt construction and the intended inspect-then-branch protocol, so this is not a hidden benchmark family.

Disposition: **review passed, residual risk high**.

### tool_use_coverage_001

Target sets and expected migrated payloads are generated per variant. The public family discloses that exact finite-set completion and out-of-scope preservation are required. Concrete future target membership remains variant-specific.

Disposition: **review passed, residual risk high**.

### long_horizon_pristine_001

The public family and golden materializer disclose the architecture and expected rollout pattern. Generated specification coordinates vary, and final verification is performed from a pristine reconstruction, but a model could have learned the benchmark family itself.

Disposition: **review passed, residual risk high**.

### greenfield_registry_001

The public contract and reference implementation strategy are inspectable in the repository. Variant constraints change, but the persistent-registry task family is not novel to a model that has ingested the repository.

Disposition: **review passed, residual risk high**.

## Revision, rotation and retirement policy

1. **Normal semantic change:** bump `task_revision`; the semantic digest also invalidates stale QA evidence.
2. **Exposure-state change:** recompute `review_context_digest` and repeat contamination review. Exposure is not folded into semantic identity.
3. **Accidental publication of a concrete per-run oracle/secret:** treat the affected generated instance as compromised. Do not use or resume that instance for contamination-sensitive evidence; rotate to a new orchestration seed/run. If the leak reveals new family semantics rather than only one generated value, revise the task/family instead of relying on seed rotation.
4. **Accidental publication of raw agent artifacts/evaluation detail:** stop publication, fix the derivation boundary, and regenerate published outputs from clean local raw sources. Do not treat deletion from the latest Git tree as proof that previously public data was never exposed.
5. **Known targeted training or tuning on AIOS-Bench:** the resulting measurement may still describe performance on this public benchmark, but it must not be interpreted as clean novel-task generalization. Such model-specific provenance is outside what task QA can infer automatically.
6. **Family saturation or memorized strategy makes the task non-discriminating:** revise or retire the affected task based on empirical saturation evidence; do not hide the issue by changing weights or silently reseeding.
7. **Static secret/answer becomes public and cannot be made variant-specific without changing the construct:** retire or replace the task rather than claiming contamination resistance.

## Residual limitations

- Public source exposure is permanent for already published commits; deleting or obscuring source later cannot restore a clean pre-exposure test set.
- Seeded generation protects concrete instance values, not the novelty of public task semantics.
- AIOS-Bench cannot reliably infer a model's training corpus. Model-specific contamination claims require external provenance evidence.
- An unconfined agent process may be able to inspect the repository during execution. That is a runtime isolation issue, not solved by this review. M12 still requires an end-to-end strong Bubblewrap proof on a compatible Linux host.
- The current `high` contamination label is intentional and should remain visible even though the review status is passed.

## Result

All eight current Frontier v4 tasks have a completed contamination assessment and may retain `pilot` status with `contamination_risk=high`. This review does not promote them to `stable`. Multi-agent pilot and saturation evidence remain pending, as does compatible-host strong-isolation proof for M12 milestone closure.
