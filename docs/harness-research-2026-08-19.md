# Harness integration research — 2026-08-19

This document records the current integration surface used by AIOS-bench. Commands and capabilities were checked against current upstream documentation before adapter work.

## Core benchmark harnesses

### Hermes Agent

Hermes is the strongest fit for the longitudinal AI-OS hypothesis. Current documentation describes persistent memory, a skills system that creates reusable procedural memory, session search, terminal/file/browser tools, delegation, MCP and multiple terminal backends. It supports `hermes chat -q` for non-interactive invocation and model selection. Its delegation system can run isolated child agents in parallel, while skills are stored as `SKILL.md` procedures.

Benchmark implications:

- test persistent memory across cold/warm runs;
- test skill creation and reuse;
- test delegation separately from ordinary tool use;
- capture terminal/file/browser activity where possible;
- keep local-vs-container terminal backend explicit.

Sources: Hermes upstream repository and documentation.

### Pi coding agent

Pi provides a particularly strong automation surface because it exposes print mode, JSON event output and RPC mode. Model/provider selection is explicit and sessions can be continued or resumed. For AIOS-bench, JSON/RPC should be preferred over scraping human-readable output.

Benchmark implications:

- use `--mode json` or RPC for telemetry;
- preserve session identity for longitudinal tests;
- record provider/model/thinking level independently;
- distinguish session persistence from agent memory.

Source: upstream Pi coding-agent documentation.

### OpenCode

OpenCode provides `run` for scripting, `--dir` for execution directory, `--model`, `--format json` for raw JSON events, and a headless `serve` mode with an HTTP API. Sessions can be resumed, exported and inspected; token/model statistics are available through the CLI.

Benchmark implications:

- prefer JSON event mode;
- use `--dir` to isolate the fixture;
- use exported sessions for post-run telemetry;
- record model variant/reasoning settings separately.

Source: OpenCode CLI documentation.

### Goose

Goose has a first-class non-interactive `goose run` command. It supports instruction files, recipes, `--no-session`, explicit provider/model selection, turn limits, and extension injection. Recipes are particularly relevant to the learning/skill dimension because they package reusable instructions, settings and extensions.

Benchmark implications:

- use `goose run --no-session -t ...` for cold tests;
- use persistent sessions for warm tests where appropriate;
- benchmark recipe creation/reuse separately from raw execution;
- explicitly pin extensions so capabilities are comparable.

Source: Goose CLI and task-running documentation.

### Letta Code

Letta Code is explicitly designed as a memory-first, long-lived agent. Current documentation describes local CLI, desktop and cloud operation, skills/subagents, continual learning, and headless invocation. The CLI supports `-p` headless messaging and agent/environment selection.

Benchmark implications:

- memory and learning should be first-class benchmark categories;
- use stable agent identity across warm/longitudinal runs;
- distinguish local environment from cloud environment;
- record agent ID and model separately.

Source: Letta Code upstream repository and current CLI documentation.

### Agent Zero

Agent Zero is structurally different from the CLI-first harnesses. Its primary interface is a Web UI, but it exposes an authenticated external API. The current `/api_message` endpoint accepts a message, context ID, agent profile and project name, and returns a context ID plus response. Agent Zero also provides persistent memory, knowledge, instruments and project state. The API is therefore a better benchmark integration point than trying to scrape its UI.

Benchmark implications:

- benchmark through the external API when a local Agent Zero server is available;
- pin a dedicated Agent Zero project/work directory for the fixture;
- preserve context IDs for longitudinal tests;
- record API-level telemetry plus filesystem results;
- do not treat UI automation as equivalent to an agent API integration.

Source: Agent Zero connectivity documentation and current `api_message.py` implementation.

## Strong secondary candidates

These are deliberately kept outside the first six adapters but should remain in the benchmark matrix.

### OpenHands

Excellent automation surface: headless mode, task/file input and JSONL event output. This is a strong candidate for a later adapter, particularly for coding and long-horizon tasks.

### Cline CLI

Strong headless integration: one-shot prompts, `--json` NDJSON events and explicit auto-approval/yolo operation. It is useful as a VS Code-adjacent comparison point.

### SWE-agent / mini-SWE-agent

Very strong benchmark infrastructure and trajectory tooling, including batch runs and trajectory inspection. It is more coding/SWE oriented than the personal AI-OS target, so it should be a secondary control rather than the primary general-purpose harness.

### Aider

A mature coding-focused CLI with ask/code/architect modes and strong local-model support. Valuable as a coding baseline, but not as representative of persistent personal-agent behavior.

## Selection rationale

The first six are intentionally diverse:

| Harness | Main differentiator | AI-OS relevance |
|---|---|---:|
| Hermes | self-improving memory + skills + delegation | Very high |
| Pi | clean JSON/RPC integration + extensibility | Very high |
| OpenCode | headless JSON + server/API + sessions | High |
| Goose | recipes + extensions + provider/model flexibility | High |
| Letta | persistent memory + continual learning | Very high |
| Agent Zero | autonomous general agent + persistent state + API | High |

The benchmark must not assume that a single harness has a single universal execution model. Adapter capability levels will therefore be recorded explicitly rather than silently treating missing telemetry as zero performance.
