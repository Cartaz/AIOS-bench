# Adapter protocol v0.1

An adapter is the only agent-specific component required by the benchmark runner.

The runner invokes:

```text
<adapter-command> '<json payload>'
```

The payload contains:

- `protocol`: `aios-bench/0.1`
- `task`: the complete task definition
- `workspace`: absolute path to the isolated workspace
- `run_id`: benchmark run identifier

The adapter must emit exactly one JSON trajectory object on stdout. Diagnostic text should go to stderr.

Example:

```json
{
  "agent": "example-agent",
  "task_id": "tool-01-scope",
  "success": true,
  "duration_s": 12.4,
  "input_tokens": 1200,
  "output_tokens": 210,
  "tool_calls": 2,
  "errors": 0,
  "retries": 0,
  "human_interventions": 0,
  "files_read": 5,
  "files_written": 0,
  "memory_reads": 0,
  "memory_writes": 0,
  "skills_created": 0,
  "events": [
    {"type":"tool","name":"read_file","path":"business/README.md"}
  ],
  "artifacts": [],
  "notes": "Completed read-only inspection."
}
```

## Event guidance

Adapters should record observable actions, not private chain-of-thought. Useful event types include:

- `tool`: tool name and relevant safe metadata
- `command`: command, exit code and duration
- `file_read`
- `file_write`
- `memory_read`
- `memory_write`
- `skill_create`
- `skill_update`
- `subagent_start`
- `subagent_end`
- `human_intervention`
- `error`

Do not include hidden chain-of-thought, secrets, credentials, or private user data in events.

## Local model requirement

For fair model comparisons, agent adapters should point at the same OpenAI-compatible endpoint and record the model identifier and inference configuration in their run metadata. The benchmark itself does not prescribe a provider.
