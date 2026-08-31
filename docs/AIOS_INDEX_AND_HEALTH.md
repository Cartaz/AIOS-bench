# AIOS-Index and benchmark health

Frontier v4 milestone V4.9 adds two complementary mechanisms: a compact routine-development profile and an agent-independent benchmark construction gate. Neither mechanism creates a new execution engine or a new scoring system.

## AIOS-Index

`aios_index_v1` is a compact profile over existing canonical Frontier v4 tasks. The current profile contains seven Tier-5 tasks covering:

- stateful multi-source autonomy;
- cross-artifact consistency;
- premise verification;
- exhaustive retrieval and provenance;
- black-box reconstruction;
- workspace dependency reasoning;
- tool selection and recovery.

The profile owns task selection and only the pressure coordinates of the families it actually executes. Families outside the compact profile do not participate in its profile digest.

The stable selection name is `aios_index_v1`. Each run also records a digest-qualified comparison identity in `experiment_context.profile_id` and the stable name in `experiment_context.profile_name`. The digest-qualified identity prevents results from two different definitions of the same named profile from being silently grouped by reporting code. `experiment_context.profile_digest` remains the authoritative full digest.

AIOS-Index always runs the canonical `no_skill` condition. It is reported separately from the ordinary full-suite leaderboard and does not alter canonical capability, reliability, failure or efficiency aggregates.

The desktop exposes AIOS-Index through the unified run-profile selector. Selecting the profile locks task selection to its canonical task set and disables skill intervention controls. Multi-harness execution still uses the shared matched interleaved scheduler.

## Semantic revision boundary

AIOS-Index selection/orchestration and benchmark-health validation are not task semantics. The following modules are deliberately outside the Frontier suite semantic fingerprint:

- `aios_index.py`;
- `aios_index_execution.py`;
- `health.py`.

Task catalogs, generators, runtimes, graders and other execution-semantic modules remain inside the fingerprint. A change to a compact profile or health checker therefore does not invalidate otherwise comparable Frontier results, while any change that can alter task behavior still changes suite identity.

## Benchmark health

`core/benchmark/health.py` validates benchmark construction without invoking an LLM or harness. The gate checks each canonical Frontier v4 task for:

- deterministic same-seed oracle generation;
- deterministic same-seed workspace generation;
- different-seed oracle diversity;
- different-seed workspace diversity;
- oracle schema validity;
- oracle/workspace separation;
- protected-source integrity;
- instruction/verifier contract consistency;
- untouched-workspace failure when action is required;
- benchmark-owned golden success;
- golden success on a second seed;
- deliberate missing-artifact near-miss failure;
- bounded deterministic grader runtime.

The automated test suite runs this health validation over the entire active Frontier v4 catalog. A task-family change that breaks generator determinism, oracle isolation, positive satisfiability, negative discrimination or the grader contract therefore fails CI independently of model performance.

## Validation

The repository validation contract remains:

```bash
.venv/bin/python -m compileall -q main.py config core ui tests
.venv/bin/ruff check main.py config core ui tests
.venv/bin/python -m pytest
```

The pytest suite includes the full Frontier v4 benchmark-health gate. GitHub Actions executes the validation matrix on supported Python 3.12+ versions and verifies the Bubblewrap capability required by strict black-box reconstruction grading.
