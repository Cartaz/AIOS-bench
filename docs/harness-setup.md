# Harness setup for AIOS-bench

The benchmark intentionally does not hide harness-specific setup behind magic flags. Configure each harness once, then run the common benchmark command.

## Hermes

Install a current Hermes Agent and configure the provider/model. The benchmark
uses Hermes' script-oriented one-shot mode rather than the interactive chat UI:

```bash
export AIOS_BENCH_HERMES_PROVIDER=openai   # optional when Hermes can resolve it
aiosbench --hermes --model <model>
```

The effective invocation pins the built-in toolsets `terminal,file,web,browser,
skills,todo,code_execution,delegation`, disables rules/ambient memory injection
with `--ignore-rules`, requests the model explicitly, and uses `--oneshot`.
`memory` and `session_search` are deliberately absent, so Hermes cannot gain an
extra persistent-state channel beyond the benchmark-owned workspace artifacts.
Because the selected toolsets are explicit built-ins, personal plugin/MCP tools
are not added to the task surface. Provider configuration remains available so
named/custom local endpoints can still be resolved; set
`AIOS_BENCH_HERMES_PROVIDER` when an explicit provider is needed.

Hermes writes its structured one-shot accounting report through `--usage-file`.
AIOS-bench reads input/output/reasoning tokens plus model/provider/session
identity from that sidecar and removes it before deterministic artifact grading.
The model's final stdout text is never parsed as tool telemetry. Server-verified
llama.cpp counters remain the preferred efficiency source when configured.

Hermes has native `delegate_task`, but current one-shot mode does not expose an
unforgeable structured tool-event stream. Therefore the default Hermes profile
**does not** declare `structured_subagent_events`: Frontier `subagents` tasks are
reported as unsupported rather than accepting a prose claim or a writable
session database as evidence. Hermes' explicit browser toolset does make browser
tasks eligible when the local browser dependencies are installed. ACP exposes
structured tool activity and may support a future dedicated benchmark profile,
but its current fixed `hermes-acp` surface also includes native memory/session
search and is therefore not used as the default cross-harness profile.

## Pi Agent

Install the Pi coding agent. AIOS-bench currently uses Pi's stdio JSONL RPC
mode, not human-readable output or one-shot JSON mode:

```bash
aiosbench --piagent --model <provider/model>
```

For each task the runner starts `pi --mode rpc --no-session` in the isolated
workspace, sends one `prompt` request on stdin, consumes structured events until
`agent_settled`, and then closes the process. Tool, usage, error, and lifecycle
events are normalized into the common trajectory schema. A per-task timeout
terminates an RPC process that does not settle. `--no-session` supplies cold
task isolation; the benchmark itself explicitly materializes warm state for
memory and learning chains.

## OpenCode

Install a current OpenCode release. AIOS-bench uses
`opencode run --dir <workspace> --format json --auto`, so the fixture directory
and raw JSON event stream are explicit:

```bash
aiosbench --opencode --model <provider/model>
```

The adapter normalizes OpenCode `tool_use`, `step_finish`, structured error and
lifecycle records. Tool input/output is not copied into benchmark telemetry.
Per-step token usage is accumulated into whole-session input/output totals.
OpenCode's built-in `task` tool is treated as structured delegation evidence:
one native `task` call produces a non-inferred `subagent_start`, and a terminal
tool state produces the corresponding `subagent_end`. Consequently OpenCode is
eligible for Frontier v3 `subagents` tasks; prose that merely says a subagent was
used still does not count.

OpenCode's `serve` API remains separate from this one-process-per-task adapter.
If a future persistent-server profile is added, it should have its own execution
fingerprint rather than silently changing the current isolation semantics.

## Goose

Install a current Goose CLI and configure its provider. AIOS-bench runs each task
with an isolated non-session CLI process and requests Goose's NDJSON stream:

```bash
export AIOS_BENCH_GOOSE_PROVIDER=openai
aiosbench --goose --model <model>
```

The effective invocation uses `goose run --no-session --quiet --output-format
stream-json --with-builtin developer`. Developer is requested explicitly so the
benchmark's shell/write/edit surface does not depend on a personal extension
toggle. Goose's default-enabled Summon platform extension remains available and
its native `delegate` tool creates real subagent sessions.

AIOS-bench parses only structured `message`, `error`, `notification` and
`complete` records. Nested `toolRequest`/`toolResponse` records become canonical
tool events without retaining prompts, tool arguments or tool output. A
structured `delegate` tool request becomes a non-inferred `subagent_start`, and
the matching tool response becomes `subagent_end`; prose mentioning delegation
never counts. Goose is therefore eligible for Frontier v3 `subagents` tasks.

The final `complete.total_tokens` value is retained only as a structured total.
AIOS-bench does not invent an input/output split from it; server-verified
llama.cpp counters remain the authoritative efficiency source. Browser tasks
remain unsupported by the default Goose benchmark profile because browser
control requires an additional extension that is not enabled by this adapter.

## Letta Code

Install a current Letta Code release and configure the backend/provider that can
resolve the model passed to AIOS-bench:

```bash
aiosbench --letta --model <model>
```

The benchmark profile intentionally does **not** resume a personal Letta agent.
Each task uses `letta -p --ephemeral --output-format stream-json --yolo --no-mods
--skill-sources bundled`, plus the requested `--model`. `--ephemeral` gives the
task a fresh temporary conversation with no persisted agent memory/MemFS;
`--no-mods` and bundled-only skill sources prevent personal/project extensions
or skills from silently changing the run. `--yolo` only removes interactive tool
approval prompts; AIOS-bench's outer workspace sandbox remains authoritative for
write isolation. The legacy `AIOS_BENCH_LETTA_AGENT` variable is ignored by this
default benchmark profile.

Warm memory/learning chains remain benchmark-owned: AIOS-bench materializes the
prior task's `.agent_memory` or `skills` artifacts into the next workspace. This
keeps the state mechanism identical across harnesses rather than giving Letta an
additional private persistent-memory channel.

Letta's headless `stream-json` protocol exposes system/init, tool-call,
tool-return, retry/error and final result records. AIOS-bench normalizes those
records without retaining assistant text, reasoning, tool arguments,
stdout/stderr or tool returns. Final structured usage supplies harness-reported
input/output token counts when available; llama.cpp server counters remain the
preferred efficiency source when configured.

Letta's internal `Task` subagent tool is surfaced to current models as `Agent`.
A structured `Agent`/`Task` `tool_call_message` produces a non-inferred
`subagent_start`, and its matching `tool_return_message` produces
`subagent_end`. Plain-text claims never count, so Letta is eligible for Frontier
v3 `subagents` tasks only through native structured delegation evidence. Browser
tasks remain unsupported in the default Letta profile because no browser
facility is explicitly enabled by the adapter.

## Agent Zero

Agent Zero is integrated through its documented external HTTP API, not by scraping its Web UI. Start a local Agent Zero instance and create a dedicated benchmark project/workspace that maps to the benchmark fixture.

```bash
export AIOS_BENCH_AGENTZERO_URL=http://127.0.0.1:80
export AIOS_BENCH_AGENTZERO_API_KEY=<api-key>
export AIOS_BENCH_AGENTZERO_PROJECT=aios-bench
aiosbench --agentzero --model <model>
```

The project must be configured so Agent Zero can operate on the isolated fixture. Do not point it at the real personal workspace during benchmark runs.

## Capability policy

Missing telemetry is recorded as unavailable, not as zero. This matters because
Hermes, Pi, OpenCode, Goose, Letta and Agent Zero expose different native
observability surfaces. Correctness remains based on the common deterministic
evaluator whenever possible.

For the `subagents` category specifically, a successful result requires the
harness integration to emit normalized `subagent_start` events. Plain-text
claims in the final answer or logs are intentionally not accepted as delegation
evidence. Treat a harness that cannot expose these events as unsupported for
that category when making cross-harness comparisons. The result uses
`status: "unsupported"`, `score: null`, and `comparable: false`; it is not a
failed task and does not enter comparable score aggregates.

The exact executable/version, requested and best-effort resolved model,
provider, redacted endpoint, declared capabilities, Python version, and
platform are captured in the run manifest. Review that manifest before treating
two runs as equivalent. See [Run lifecycle, manifests, and result
publication](RUNS_AND_RESULTS.md).

## Workspace write isolation

On Linux, local CLI harnesses are wrapped with bubblewrap: the host root is
read-only and only the task workspace and a temporary `/tmp` are writable;
network access remains available for research tasks. The chosen strategy and
whether writes were confined are recorded in
`run.json.manifest.configuration`.

Set `AIOS_BENCH_SANDBOX=required` to fail closed when bubblewrap is unavailable,
or `AIOS_BENCH_SANDBOX=off` only for a deliberately unconfined diagnostic run.
The default `auto` mode records an explicit `cwd_only_unconfined` fallback on
platforms without bubblewrap. Agent Zero additionally depends on its configured
remote project boundary; never point that project at a personal workspace.
