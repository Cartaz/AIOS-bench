# DeepSeek Harness integration

AIOS-Bench integrates the official `deepseek-ai/deepseek-harness` CLI as the `deepseek` harness. The integration targets the built-in `headless` profile because it has the lifecycle AIOS-Bench needs for deterministic benchmarking: one task per process, no GUI or listening server, a defined process exit code, final text on stdout and provider reasoning on stderr.

## Runtime contract

The Doctor installs the pinned developer-preview package `@deepseek-ai/dsh@0.1.2-alpha.5`. DeepSeek Harness publishes the Node engine range `^22.19.0 || >=24.0.0`; Node 23 is therefore intentionally rejected. AIOS-Bench also requires Bubblewrap for this harness because the isolated DSH state is part of the benchmark boundary rather than an optional convenience.

The benchmark invokes:

```text
dsh --profile headless <task prompt>
```

The model is not selected through a `dsh --model` flag. Instead AIOS-Bench generates a credential-free `settings.yaml` for the requested model and the configured OpenAI-compatible endpoint. The retained source document is mounted read-only into a fresh process-lifetime `DSH_HOME` inside Bubblewrap's private `/tmp`. DSH profiles, sessions, storage and other mutable state therefore disappear with the task process and never reuse the user's ambient DeepSeek Harness home.

The OpenAI-compatible endpoint comes from the normal AIOS-Bench `AIOS_BENCH_ENDPOINT` setting. An authenticated gateway can provide `AIOS_BENCH_DEEPSEEK_API_KEY`; unauthenticated local servers receive a non-secret dummy value because the provider interface expects a credential reference.

During benchmark execution AIOS-Bench sets `DSH_TELEMETRY_DISABLED=1`. It also selects DeepSeek Harness' non-interactive permission mode only inside the outer AIOS-Bench Bubblewrap confinement, where the benchmark workspace remains the sole writable task surface and benchmark-owned graders/oracles remain hidden.

## Capabilities and observability

The adapter exposes the headless local workspace capabilities that AIOS-Bench can actually rely on: sessions, terminal/tool execution, skills and delegation primitives. It does **not** claim browser support.

DeepSeek Harness' current headless process output exposes reasoning and the final answer but not a structured stream of tool/subagent lifecycle events. AIOS-Bench therefore does not claim `tool_events`, `json_events` or `structured_subagent_events` for this harness. In particular, Frontier v4 tasks whose grading requires observable structured delegation are reported `UNSUPPORTED`, even though DeepSeek Harness can use subagents internally. This preserves the benchmark rule that capability claims must be observable and verifiable rather than inferred from implementation features.

Token/efficiency measurements continue to prefer the benchmark's server-side metrics when configured. Headless stdout/stderr alone are not treated as structured harness telemetry.

## Doctor behavior

Doctor reports three distinct states:

- `OK`: the harness executable is installed and its runtime prerequisites are satisfied;
- `MISSING`: the executable is not detected;
- `BLOCKED`: the executable exists but a required runtime prerequisite is missing or incompatible.

For DeepSeek Harness, `BLOCKED` currently means an incompatible/unverifiable Node version or missing Bubblewrap. Doctor does not misreport those conditions as a missing `dsh` installation.

## Comparability

Each invocation records the requested and adapter-pinned model, provider id, sanitized endpoint, headless profile, isolation mode and whether a real API key was configured. Credentials and benchmark prompts are excluded from the run manifest. Strict model comparability still follows the existing AIOS-Bench manifest rules: a model digest and valid inference configuration must be recorded where required for strict cross-run comparison.