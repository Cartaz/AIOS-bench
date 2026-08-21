# Frontier v4 pressure landscapes

Frontier v4 records generated workload coordinates on every parametric task result. The derived analysis treats those coordinates as observed workload descriptors, not as an assumed monotonic difficulty scale.

## Views

`summary.json` exposes two derived structures for the selected suite revision:

- `pressure_landscapes`: per-harness capability response grouped by model identity, parametric family and a pressure-excluded landscape execution profile.
- `pressure_paired_comparisons`: experiment-scoped harness deltas inside identical full pressure vectors.

Each landscape contains:

- `full_vector_cells`: the exact joint pressure vector and empirical outcomes for that cell;
- `axes`: marginal summaries for each coordinate value, explicitly labeled `marginal_over_other_coordinates`;
- pass rate and Wilson 95% interval;
- mean/median/range of deterministic task score;
- unique generated variant count and seeds;
- mutually exclusive failure-kind counts.

The dashboard renders marginal axes, joint cells and matched harness deltas separately.

## Comparability

A normal Frontier v4 `execution_fingerprint` includes pressure coordinates and therefore changes between pressure cells. For landscape aggregation the runner additionally records `landscape_execution_fingerprint`, computed from the same execution manifest after removing only `parametric.pressure_coordinates`.

This means cells are combined within a harness only when all other execution settings remain the same. Changes such as token caps, timeouts, sandbox strategy, adapter configuration or server settings produce a different landscape profile and therefore a separate landscape.

Strict model identity is also part of the landscape grouping key. Different model/inference identities are never silently combined.

Older Frontier v4 rows that predate `landscape_execution_fingerprint` are fail-closed: they are isolated by their ordinary execution fingerprint rather than combined across pressure configurations.

## Matched harness comparisons

Pressure-cell harness comparisons are descriptive and experiment-scoped. A pair is accepted only when both harnesses have the same strict model identity and observations match on:

- experiment;
- repeat;
- task;
- task seed;
- generated variant digest;
- full pressure vector.

Unmatched, unsupported or non-comparable observations are not imputed. Global inferential paired statistics remain in the existing `paired_comparisons` analysis; pressure-cell deltas report matched counts, mean/median score delta, wins/losses/ties and discordant pass outcomes.

## Interpretation

A marginal axis row such as `rows=96` is not evidence that `rows` alone caused the observed score. It summarizes all observed variants with that coordinate value across the other sampled coordinates. Use full-vector cells for exact workload combinations and design deliberate pressure sweeps when causal interpretation is desired.
