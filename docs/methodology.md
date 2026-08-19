# Methodology

## What we are trying to measure

AIOS-bench evaluates whether an agent can become a reliable local personal AI OS rather than merely a strong coding chatbot.

### Primary dimensions

1. **Task success** — did the requested outcome happen?
2. **Tool accuracy** — were tools used correctly and only when useful?
3. **Recovery** — can the agent diagnose and recover from failures?
4. **Memory** — does it retain useful information across sessions without stale or invented facts?
5. **Learning** — does repeated exposure reduce errors, actions, and user intervention?
6. **Autonomy** — can it plan and execute without unnecessary supervision?
7. **Proportionality** — does a simple task receive a simple execution path?
8. **Context efficiency** — how much context/tool output is consumed to reach the result?
9. **Long-horizon reliability** — can it survive 20+ actions without losing the goal?
10. **Subagent efficiency** — does delegation improve outcomes enough to justify its cost?

## Experimental controls

For a model comparison, keep these fixed:

- model and quantization;
- llama.cpp/server version;
- context size;
- sampling parameters;
- seed where supported;
- hardware and power profile;
- task fixtures;
- workspace permissions;
- network policy;
- agent temperature/tool settings when comparing architecture rather than tuning.

Record any deviation in run metadata. Never compare a tuned run against an untuned run as if they were equivalent.

## Three stages

### Cold

Empty memory and skills. Measures baseline capability.

### Warm

Pre-populated memory/skills. Measures usefulness of persistence.

### Longitudinal

Repeat related tasks over multiple sessions. Measure whether the system actually improves.

## Learning gain

For a repeated task family, compare the first and later attempts using:

```text
learning_gain = normalized(first_run_cost - later_run_cost)
```

where cost can combine failures, tool calls, human interventions and token usage. Correctness remains a hard gate: a faster wrong answer is not an improvement.

## Human intervention

Count every user action required to unblock the agent, excluding the initial task prompt. Examples:

- answering a question that was not genuinely necessary;
- manually fixing an agent-created error;
- manually performing a tool action the agent could perform;
- approving an otherwise safe action repeatedly.

Destructive or genuinely ambiguous actions may legitimately require approval.

## Reasoning visibility

The benchmark intentionally does **not** request or store private chain-of-thought. Instead it records observable trajectory events: tool calls, command results, file changes, memory events, subagent events, retries and errors. This gives reproducible evidence of agent behavior without treating hidden reasoning as a benchmark artifact.

## Score philosophy

The current pilot score is deliberately conservative:

- correctness: 70%
- error efficiency: 15%
- human intervention: 10%
- proportionality: 5%

This is a v0.1 baseline, not a final scientific weighting. Longitudinal learning will receive a separate score rather than being hidden inside the raw task score.
