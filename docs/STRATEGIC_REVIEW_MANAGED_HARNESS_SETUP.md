# Strategic Review — Managed Harness Installation & Centralized Gateway Setup

**Status:** CLOSED only after the final branch-head CI run succeeds.

## Scope reviewed

This milestone changes infrastructure rather than benchmark task semantics. It covers:

- project-local Node/npm ownership and pinned managed harness installation;
- Doctor installation/repair behavior;
- the single persisted local-inference profile;
- endpoint/model discovery and live protocol probes;
- translation of that canonical profile into isolated harness-specific runtime configuration;
- QWebChannel/worker integration and Setup UI;
- workspace sandbox exposure of generated provider configuration;
- run provenance and comparability metadata;
- installation/setup documentation and automated validation.

The benchmark catalogs, deterministic graders, Frontier v3/v4 task semantics, AIOS-Index definition and score aggregation are intentionally unchanged.

## Strategic design review

### One installation owner

The central design invariant is that a managed harness version has exactly one owner: `core/benchmark/managed_runtimes.py`.

`install.sh` calls that module for the ordinary bootstrap path. Doctor's **Installa** action now delegates to the same `install_managed_harness()` operation. Runtime discovery uses `runtime_paths.py`, which prefers `.venv/bin` before ambient `PATH`.

A competing design was to leave Doctor with independent `npm install -g ...` recipes. It was initially present and the milestone review exposed its cost immediately: Doctor still referenced an unpinned OpenCode package and the deprecated `@mariozechner/pi-coding-agent` namespace while the canonical installer used pinned current packages. Keeping both paths would create version drift, non-reproducible repairs and confusing ownership. The duplicate path was removed rather than documented as an exception.

Hermes and Goose remain deliberately external because their supported Linux installation paths are remote release/shell installers. Agent Zero remains an external service. AIOS-Bench does not broaden the installer abstraction merely to hide those materially different lifecycles.

### One persistent inference profile

`SettingsStore` remains the sole owner of persistent application settings. The profile contains only:

- model id;
- OpenAI-compatible base URL;
- optional Anthropic-compatible base URL.

JavaScript never writes settings. `DoctorService` normalizes and coordinates the profile, while `core/inference_setup.py` owns protocol validation and probing.

The mandatory OpenAI-compatible route is saved only after:

1. URL validation;
2. successful `/models` discovery;
3. exact presence of the selected model id;
4. a real `chat/completions` request;
5. rejection if the server explicitly reports a different resolved model.

A failed test therefore cannot overwrite a previous valid saved profile. The Anthropic route is optional and tested independently so Claude Code support cannot block the shared OpenAI route used by the other local harnesses.

Explicit process-level endpoint variables that existed before `DoctorService` starts remain operator-owned overrides. Saved desktop settings own only unprotected keys. This preserves deliberate CLI/operator configuration without creating another persistence mechanism.

### Harness translation at one boundary

Two implementation alternatives were considered:

1. **Persistently modify every harness's personal provider configuration.** Rejected because it mutates user state, introduces schema/version migration for every external project, and makes benchmark identity depend on ambient configuration.
2. **Add per-harness endpoint/model conditionals to the runner.** Rejected because provider translation is not runner lifecycle logic and would amplify every future harness/configuration change across execution code.

The chosen design uses a single post-adapter `bind_invocation()` boundary in `local_gateway.py`. Adapters still own harness execution semantics, commands, capabilities and telemetry. The binder owns only translation from the canonical benchmark profile to the harness's effective provider/model route.

This preserves concrete adapter types — especially Pi's RPC dispatch — and avoids adding setup logic to `task_execution.py`.

### Isolated configuration instead of ambient state

The canonical route avoids personal provider state where a controlled mechanism exists:

- Pi receives a benchmark-owned task-scoped `models.json` through `PI_CODING_AGENT_DIR`;
- OpenCode receives `OPENCODE_CONFIG_CONTENT` plus private XDG/OpenCode directories;
- Goose receives provider/endpoint/main/fast-model environment overrides;
- Letta receives its current `llama-cpp` provider route and private local backend directory;
- Hermes receives an explicit OpenAI-compatible provider route;
- DeepSeek receives benchmark-owned isolated DSH settings and a private `DSH_HOME`;
- Claude already uses a private per-workspace config directory and now consumes the canonical optional Anthropic route;
- Agent Zero remains honestly external because its API cannot be made equivalent to a local one-process provider config.

Pi's generated profile and DeepSeek's generated settings are mounted read-only into Bubblewrap. They are exceptions only in the sense that the harness must read benchmark-owned configuration; neither is writable agent state.

### Model fairness across auxiliary surfaces

Where a harness exposes an auxiliary model surface that could silently use a second model, the benchmark pins it to the same requested model when the harness contract allows it:

- OpenCode `small_model` equals the benchmark model;
- Goose `GOOSE_FAST_MODEL` equals the benchmark model;
- Claude's default model aliases and subagent model equal the benchmark model;
- Agent Zero requires both declared main and utility models to equal the requested model.

This is a fairness constraint, not merely convenience. Allowing a hidden stronger/faster helper model would invalidate cross-harness comparisons.

## Review findings resolved during the milestone

### OpenCode schema drift

The first OpenCode binder implementation used a future V2-style `providers/package/settings` shape. Automated unit tests initially mirrored that assumption, so they could not detect the upstream incompatibility.

The review checked the exact pinned OpenCode `1.18.26` source/documentation and found that the stable contract is singular `provider` with `npm`, `options` and `models`. The implementation and tests were corrected to the pinned schema, and regression tests now assert both the required stable fields and absence of the incompatible V2 fields.

This was treated as a design/version-contract failure rather than patched by adding fallback schemas. Supporting multiple OpenCode configuration generations speculatively would add ambiguity and hidden behavior; AIOS-Bench instead pins one tested release and one tested schema.

### Doctor installer drift

Doctor's legacy automatic npm recipes had diverged from `install.sh`, including the deprecated Pi package namespace. The fix was to remove the independent source of package/version truth and route managed Doctor installation through `managed_runtimes.py`.

Tests now assert that all five managed Doctor recipes are derived from the registry and that managed installation never falls back to the generic npm recipe path.

## Complexity and layer review

### Change amplification

The new responsibilities are deliberately concentrated:

- `managed_runtimes.py`: managed runtime versions and installation;
- `runtime_paths.py`: executable/runtime resolution;
- `inference_setup.py`: endpoint and protocol probing;
- `DoctorService`: setup orchestration and persistence boundary;
- `local_gateway.py`: harness route translation;
- adapters: harness execution semantics;
- `sandbox.py`: filesystem isolation;
- `DesktopRuntime`: long-running Qt worker lifecycle;
- `Bridge`: thin validation/transport surface;
- web frontend: presentation and temporary form state only.

Adding another OpenAI-compatible local harness should normally require one registry entry/adapter plus one binder translation, not changes in the runner, settings store and frontend.

### Cognitive load

The milestone introduces two new focused modules instead of expanding `doctor.py` or adapters indefinitely. `DoctorService` exposes user-facing setup operations without forcing UI code to understand HTTP protocols, environment precedence or filesystem state. `local_gateway.py` centralizes the otherwise scattered provider mapping.

The setup flow remains one conceptual model for the user: one endpoint, one model, optional Anthropic route.

### Hidden dependencies

The critical external contracts are made explicit and tested where possible:

- project-local Node version;
- exact npm package versions;
- OpenCode 1.18.26 configuration schema;
- DeepSeek Node/Bubblewrap prerequisites;
- exact server model id from `/models` and response model when reported;
- Agent Zero remote attestations.

Provider credentials are not encoded into endpoint URLs. Configuration/manifests retain presence/identity metadata but sanitize secret values.

## Security review

- No automatic `curl | bash`, `sudo`, Docker installation or service startup was introduced.
- Endpoint URLs reject embedded credentials, query strings and fragments before persistence.
- OpenCode API keys are referenced from environment rather than embedded in retained inline configuration.
- Personal Pi/OpenCode/Letta/Claude/DeepSeek state is not used as the canonical local gateway configuration source.
- Bubblewrap continues to own local workspace write confinement and grader hiding.
- Generated Pi/DeepSeek configuration is read-only inside the agent sandbox.
- Agent Zero keeps its existing dedicated service/project isolation and explicit operator attestations rather than receiving unsafe local shortcuts.

## Concurrency and lifecycle review

Model discovery, gateway testing, Doctor inspection and installation all run through the existing owned Qt worker lifecycle. HTTP requests and installers therefore do not block the GUI thread.

Cancellation is cooperative at operation boundaries and subprocesses remain owned by the existing process-group termination infrastructure. No force-terminated Qt threads or unowned background processes were added.

## Provenance and comparability

No second provenance system was added. The binder returns the effective route in `AgentInvocation`; existing `build_run_manifest()` already records and sanitizes:

- requested/resolved model and resolution method;
- provider;
- endpoint;
- effective harness configuration;
- executable path/version;
- declared/computed model digest and inference configuration when supplied.

Strict comparability still requires the existing model-digest and inference-configuration evidence. A successful Setup probe establishes route validity, not publication-grade equivalence by itself.

## UI review

The desktop retains Python as canonical state. The frontend owns only temporary fields, discovered-model choices and display state. QWebChannel exposes focused operations for discovery/configuration instead of arbitrary filesystem/command access.

The canonical action is **Test e configura**. **Salva senza test** remains an explicitly labeled expert/manual override rather than being presented as verified setup; runs constructed from such a profile can still fail normally if the endpoint is invalid.

The Setup panel reports per-harness distinctions rather than reducing everything to one false green state: runtime missing/blocked/ready, gateway configured, Anthropic route required/failed, or external service.

## Validation boundary

Automated CI can and does verify:

- ordinary `./install.sh` managed bootstrap on a clean Ubuntu runner;
- project-local Node/npm/harness ownership and executable presence;
- Python 3.12/3.13/3.14 compile, Ruff and complete pytest suite;
- functional Bubblewrap creation;
- Qt/WebEngine offscreen smoke coverage through the existing suite;
- deterministic gateway probing behavior with controlled HTTP-call test doubles;
- exact isolated binding contracts and secret non-embedding.

CI does **not** have the user's live llama.cpp server. Therefore this milestone does not claim that GitHub Actions executed `Test e configura` against a real Ornith/Qwen llama.cpp instance. That live endpoint validation occurs when the user runs the Setup flow locally.

Likewise, GitHub CI does not establish native CachyOS/KDE interactive behavior; its desktop boundary remains Ubuntu/offscreen. Hermes, Goose and Agent Zero are not converted into managed-bootstrap installations because doing so would violate the explicit external-runtime design above.

## Remaining deliberate deferrals

- No automatic installation/startup of Agent Zero or other service-backed infrastructure.
- No automatic execution of upstream remote shell installers for Hermes/Goose.
- No speculative multi-version OpenCode config compatibility layer; the benchmark pins and tests one release.
- No claim that an OpenAI-compatible server also supports Claude; Anthropic compatibility remains separately probed.
- No credentials UI/persistence system in this milestone; existing environment-based secret handling remains the safer narrow contract.
- No benchmark task/catalog/version changes: infrastructure setup is intentionally separate from Frontier scientific semantics.

## Milestone conclusion

The milestone reduces rather than increases configuration ambiguity: one installer registry owns managed versions, one settings abstraction owns the local inference profile, one probing module validates it, and one post-adapter binder translates it without leaking provider logic into the runner. The two material architecture defects found during review — OpenCode schema mismatch and Doctor installer drift — were corrected at their source and guarded by regression tests.

The milestone may be reported as closed only after the CI run triggered by the final closure commit finishes successfully across managed bootstrap and the full Python matrix.
