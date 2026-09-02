# Harness setup for AIOS-Bench

AIOS-Bench now owns one canonical local-inference profile instead of requiring a separate persistent provider configuration in every CLI harness.

The desktop **Setup / Doctor** flow is the canonical path:

1. enter the OpenAI-compatible server URL, normally `http://127.0.0.1:8080/v1`;
2. use **Trova modelli** to read the server's `/models` list;
3. select or enter the exact model id;
4. optionally provide an Anthropic-compatible base URL for Claude Code;
5. use **Test e configura**.

The mandatory OpenAI route is saved only after the selected model is present in `/models` and a real `chat/completions` request succeeds. If the server reports a different model id, setup fails rather than silently accepting model substitution. A failed test does not replace the previous valid saved profile. The optional Anthropic route is tested independently so Claude configuration cannot block the other harnesses.

Persistent settings remain Python-owned in `SettingsStore`; JavaScript never writes the settings file directly. Explicit process-level `AIOS_BENCH_ENDPOINT` or `AIOS_BENCH_CLAUDE_BASE_URL` values that existed before the desktop service started remain operator-owned overrides.

## Installation ownership

`./install.sh` creates/repairs `.venv`, installs Python requirements, provisions project-local Node through `nodeenv`, and installs the managed npm harnesses into the same `.venv`. Doctor's **Installa** action uses that same managed-runtime registry and installer; there is no second unpinned npm path.

Managed project-local runtimes are currently:

| Harness | Pinned package |
| --- | --- |
| Pi Agent | `@earendil-works/pi-coding-agent@0.84.4` |
| OpenCode | `opencode-ai@1.18.26` |
| Letta Code | `@letta-ai/letta-code@0.31.11` |
| Claude Code | `@anthropic-ai/claude-code@2.1.236` |
| DeepSeek Harness | `@deepseek-ai/dsh@0.1.2-alpha.5` |

AIOS-Bench prepends `.venv/bin` for owned subprocesses, so the project-local runtime wins over an ambient executable with the same name.

Hermes Agent and Goose remain manual installs because their supported Linux installation paths are remote shell/release installers. AIOS-Bench displays the upstream command but never runs `curl | bash` automatically. Agent Zero remains a separately managed service/container.

## Canonical gateway binding

The saved OpenAI-compatible endpoint and model are translated at one post-adapter binding boundary. The adapter still owns harness semantics and event parsing; the gateway binder owns only provider/model routing. This keeps the runner free of per-harness setup special cases.

| Harness | AIOS-Bench binding |
| --- | --- |
| Hermes | forces `--provider openai-api`, `OPENAI_BASE_URL`, requested model |
| Pi Agent | task-scoped `models.json`, `PI_CODING_AGENT_DIR`, provider `aios-bench` |
| OpenCode | isolated `OPENCODE_CONFIG_CONTENT`, provider `aios-bench`, main and `small_model` pinned to the benchmark model |
| Goose | provider `openai`, `OPENAI_HOST`/`OPENAI_BASE_PATH`, main and fast model pinned |
| Letta Code | provider handle `llama-cpp/<model>` with `LLAMA_CPP_BASE_URL` |
| DeepSeek Harness | benchmark-owned isolated headless DSH settings from `AIOS_BENCH_ENDPOINT` and the requested model |
| Claude Code | Anthropic-compatible base URL; main/default aliases/subagent model all pinned to the benchmark model |
| Agent Zero | external service; model/service identity remains operator-attested and fails closed on mismatch |

The OpenCode configuration deliberately follows the pinned **1.18.26** stable schema: `provider` + `npm` + `options`. AIOS-Bench does not use the incompatible future-V2 `providers/package/settings` shape. The custom provider uses `@ai-sdk/openai-compatible` and the real server model id as the model key.

For gateways requiring an OpenAI API key, set `AIOS_BENCH_OPENAI_API_KEY`. The key is passed through environment/config references and is not embedded into retained provider configuration or run provenance. DeepSeek Harness retains its dedicated optional `AIOS_BENCH_DEEPSEEK_API_KEY`. Claude accepts the existing benchmark-namespaced Claude credentials supported by its adapter.

## Harness execution profiles

### Hermes Agent

Hermes remains an external install, but its model route is now configured by AIOS-Bench. The benchmark uses one-shot mode with explicit built-in toolsets and `--ignore-rules`; ambient memory/session-search tools are excluded. Structured usage is read from the benchmark-owned `--usage-file` sidecar. Hermes has native delegation but the current one-shot integration does not expose trustworthy structured child lifecycles, so tasks requiring `structured_subagent_events` are `UNSUPPORTED`.

### Pi Agent

Pi runs through stdio RPC using `pi --mode rpc --no-session`. AIOS-Bench generates a task-scoped `models.json` outside the agent workspace and mounts only that benchmark-owned profile read-only under Bubblewrap. Personal `~/.pi/agent` provider state is not needed for the canonical local gateway path. Warm benchmark state is materialized explicitly by AIOS-Bench rather than through Pi sessions.

### OpenCode

OpenCode uses `opencode run --dir <workspace> --format json --auto`. Provider state is supplied inline and XDG/OpenCode state directories are redirected to private `/tmp` locations. The built-in `task` tool supplies structured delegation evidence when present. OpenCode's persistent `serve` mode is not silently substituted for the one-process-per-task benchmark profile.

### Goose

Goose remains a manual CLI install. AIOS-Bench runs `goose run --no-session --quiet --output-format stream-json --with-builtin developer`, forces the OpenAI-compatible route, and pins both `GOOSE_MODEL` and `GOOSE_FAST_MODEL` to the benchmark model. Structured Summon `delegate` request/response records provide subagent lifecycle evidence. Browser tasks remain unsupported by the default profile because the extra browser extension is not enabled.

### Letta Code

Letta uses an ephemeral headless profile: `-p --ephemeral --output-format stream-json --yolo --no-mods --skill-sources bundled`. AIOS-Bench binds the current `llama-cpp` provider to the canonical endpoint and redirects local backend state to private `/tmp`. Personal Letta agents/mods/skills are not resumed. Structured `Agent`/`Task` tool messages provide delegation evidence.

### Claude Code

Claude Code uses a per-workspace `CLAUDE_CONFIG_DIR`, safe mode, no transcript persistence, strict/disabled customization surfaces, and the benchmark model is pinned across the main model, default aliases and subagent model. Claude requires an Anthropic-compatible gateway when the local inference server does not expose Anthropic's `/v1/messages` contract. Missing Anthropic support is reported explicitly and does not invalidate the shared OpenAI profile for other harnesses.

### DeepSeek Harness

DeepSeek Harness uses a benchmark-owned isolated headless profile. Its `DSH_HOME` is private and the generated settings file is mounted read-only inside Bubblewrap. Ambient DSH state is not inherited. The managed release requires compatible Node (`^22.19.0 || >=24.0.0`) and functional Bubblewrap; Doctor distinguishes an installed-but-blocked runtime from a missing runtime.

### Agent Zero

Agent Zero is intentionally not rewritten as a local CLI. It runs as a dedicated external service/container and must remain benchmark-isolated from personal projects/mounts. Configure at minimum:

```bash
export AIOS_BENCH_AGENTZERO_URL=http://127.0.0.1:80
export AIOS_BENCH_AGENTZERO_API_KEY=<api-key>
export AIOS_BENCH_AGENTZERO_PROJECT=aios-bench
export AIOS_BENCH_AGENTZERO_PROJECTS_ROOT=/path/to/dedicated/agent-zero/usr/projects
export AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE=1
export AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION=1
export AIOS_BENCH_AGENTZERO_REVISION=<release-commit-or-immutable-image-digest>
export AIOS_BENCH_AGENTZERO_RESOLVED_MODEL=<model>
export AIOS_BENCH_AGENTZERO_UTILITY_MODEL=<model>
```

Both declared Agent Zero models must exactly match the model requested by the benchmark. The external API does not provide a benchmark-controlled remote model/version setter, so service revision and model binding are recorded honestly as operator-declared provenance rather than presented as adapter-pinned state. Each attempt receives a unique physical project and fresh chat context; the benchmark validates the neutral template, copies task artifacts through the dedicated projects-root bridge, terminates the context, validates copy-back and removes the ephemeral project when normal cleanup can run.

## Provenance and comparability

The gateway binder returns the effective route through `AgentInvocation`. `build_run_manifest()` therefore records, after secret sanitization:

- requested and resolved model;
- model-resolution method;
- provider;
- endpoint;
- effective harness configuration;
- executable path/version;
- model digest and inference configuration when supplied.

A configured route does not by itself make runs strictly comparable. Publication-grade comparisons still require a common model digest and valid inference configuration, and server-side telemetry remains preferred for efficiency when available.

## Capability policy

Correctness remains deterministic and missing telemetry is unavailable rather than zero. Harnesses that cannot expose a required native capability are marked `UNSUPPORTED`, `score: null`, `comparable: false` for that task instead of being treated as failed or accepted on prose claims.

For delegation tasks, only normalized non-inferred structured subagent lifecycles count. For browser tasks, only profiles that explicitly expose the benchmark's browser capability are eligible.

## Workspace isolation

On Linux, local CLI harnesses run under Bubblewrap when available: the host root is read-only, the benchmark repository/grader material is hidden, and only the current task workspace plus private temporary state is writable. Pi's generated gateway profile and DeepSeek's generated settings are mounted read-only as explicit benchmark-owned exceptions. Agent Zero additionally receives only its dedicated benchmark projects-root bridge.

Set `AIOS_BENCH_SANDBOX=required` to fail closed when Bubblewrap is unavailable. `AIOS_BENCH_SANDBOX=off` is a deliberate diagnostic mode and is rejected for DeepSeek because its isolated DSH home depends on Bubblewrap.
