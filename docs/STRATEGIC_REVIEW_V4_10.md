# Strategic Review — Frontier V4.10 Persistent Memory

Status: **CLOSED on development branch after matrix validation**

## Review scope

This review covers the Persistent Memory milestone introduced after V4.9. The purpose is not only to confirm that the new family works, but to check whether the design leaves Frontier v4 easier or harder to extend with the remaining V3-derived capability gaps.

## Complexity review

### Ownership

Ownership remains explicit:

- the `persistent_memory` generator owns generated preference/update content and hidden expected state;
- the family grader owns correctness of durable memory and phase reports;
- `ParametricFamilySpec` declares whether a family needs benchmark-owned persistent paths;
- `ParametricTaskMaterializer` alone owns restore/persist lifecycle;
- task JSON owns phase/state-scope metadata through `variant_context`;
- runner/scheduler continue to own execution, dependency blocking and per-harness run directories.

No memory-task ID appears in the parametric materializer or runner.

### Change amplification

Two validation paths previously decoded parametric task metadata differently: the runtime materializer parsed `parametric_reference`, while `validation.py` had a private family parser. V4.10 initially exposed that duplication because contextual memory phases were lost in preflight. The fix removed the duplicate parser and made preflight use `ParametricTaskMaterializer.family()` and `variant_context()` just like benchmark health/runtime.

This is a net reduction in change amplification: future contextual families now have one catalog-decoding boundary.

### Abstraction depth

The persistent-state interface is deliberately small:

- family declaration: `persistent_paths`;
- task declaration: optional `variant_context` including `state_scope`;
- materializer implementation hides restore, snapshot, copy semantics and safe path handling.

That is deeper than adding a memory-specific branch to `FrontierRunner` or `ParametricTaskMaterializer`, and it is immediately reusable by Learning & Transfer.

### Layering

No persistent-state policy was placed in JS, GUI service, bridge, scheduler or runner. The scheduler already preserves one stateful runner per harness, so no additional orchestration layer was introduced.

The generator does not perform lifecycle copies, and the materializer does not understand durable-preference semantics.

### State leakage and isolation

Persistent state is rooted below each runner's `run_dir`. Repeats use separate run IDs and matched harnesses use separate runner/run directories. Therefore memory does not cross harness or repeat boundaries.

`state_scope` is converted to a safe path component and declared persistent paths reject absolute paths and parent traversal.

### Benchmark validity

The three tasks form one dependency chain. Downstream tasks are blocked if the preceding state-producing task fails, preventing a later phase from being interpreted as an independent model failure.

Benchmark health still validates each phase's generator/grader contract independently. A dedicated lifecycle test covers actual warm-state transfer, so independent constructibility does not replace longitudinal verification.

The oracle-only synthetic prior state used by standalone validation is not written into the agent workspace. It therefore cannot make a real warm task pass when persistence is broken.

### AIOS-Index boundary

Persistent Memory is not added to `aios_index_v1`. The profile still exposes only pressure coordinates for its seven selected families. This preserves the V4.9 rule that unrelated full-catalog families do not enter the compact profile definition merely by being registered.

Ordinary Frontier v4 suite semantic revision does change, as expected, because a new canonical task family and shared materialization behavior have been added.

## Alternatives considered

### A. Keep V3 memory tasks only

Rejected. They are static and would leave a known capability gap in the primary V4 methodology.

### B. Add memory-specific conditionals to the V4 materializer

Rejected. This repeats the V3 category-special-case pattern and would force Learning & Transfer to add another branch later.

### C. One single large memory task

Rejected for this capability. A single workspace can test selection and editing, but cannot establish that durable state survives a real task boundary without the prompt repeating the values.

### D. Three independent memory tasks

Rejected. It would inflate task count without testing persistence. The chosen design treats the three catalog entries as one longitudinal family with explicit dependencies.

## Remaining risks / deliberate deferrals

- The current family measures portable file-backed durable memory rather than harness-native proprietary memory stores. This is intentional for cross-harness comparability; native-memory-specific experiments may be added separately if a common capability contract becomes possible.
- Persistent Memory has canonical pressure defaults but no dedicated GUI/CLI pressure editor yet. This is deferred until empirical sweeps establish useful axes.
- No curated skill package is added for memory in V4.10. Existing skill-ablation infrastructure therefore records `skill_available=false` for these tasks.
- Persistent Memory is not in AIOS-Index pending empirical discrimination/runtime evidence.
- No native CachyOS/KDE live benchmark run was observed in this milestone; CI uses Ubuntu/offscreen where GUI coverage is involved.

## Validation observed

First branch CI exposed four failures: three stale 10-task catalog expectations and one duplicated preflight metadata parser that discarded contextual phases. These were corrected at the source rather than bypassed.

Second branch CI run `33460175310` completed successfully on Python 3.12, 3.13 and 3.14. Each job passed install/native prerequisites, compile, Ruff and pytest. Python 3.12 reported **454 passed**.

## Milestone conclusion

No important architectural drift remains in the touched area. Persistent state now has one generic owner and one declarative family interface, contextual variant metadata has a single parser used by runtime/health/preflight, and the new family is isolated from AIOS-Index selection.

V4.10 is therefore ready for documentation finalization and, after explicit user authorization, later integration. The next logical capability milestone is Learning & Transfer, which should reuse the new persistent-state contract rather than introduce another lifecycle mechanism.
