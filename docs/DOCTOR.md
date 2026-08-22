# Doctor wizard

`aiosbench doctor` is the readiness and onboarding surface for the external harness matrix. Benchmark execution remains non-mutating: `aiosbench --all` never installs packages or rewrites host configuration.

## Modes

```bash
aiosbench doctor
aiosbench doctor --check
aiosbench doctor --setup
aiosbench doctor --repair
```

- `doctor` prints system and harness readiness and exits non-zero when the matrix is incomplete.
- `doctor --check` is explicitly non-interactive and non-mutating, suitable for scripts and CI.
- `doctor --setup` guides installation and local-model configuration.
- `doctor --repair` repeats the guided path for missing or broken components without changing benchmark execution semantics.

The wizard detects Python, Node/npm, bubblewrap and all active harnesses. It probes CLI versions best-effort. Agent Zero is treated as the service-backed integration it is rather than as a fake local executable.

## Installation safety

Every installation is opt-in. Package-manager commands are displayed before execution. Remote official installer pipelines such as Goose or Hermes require a separate confirmation whose default is **No**. Agent Zero remains a guided manual/service setup because its benchmark adapter depends on an isolated service, project bridge and model attestations.

Current recipes follow upstream installation documentation:

| Harness | Wizard installation path |
| --- | --- |
| Hermes | official installer; browser bootstrap skipped for the benchmark-oriented setup |
| Pi Agent | `npm install -g @mariozechner/pi-coding-agent` |
| OpenCode | `pacman` on Arch-family systems, otherwise npm |
| Goose | official stable CLI installer |
| Letta | `npm install -g @letta-ai/letta-code` |
| Agent Zero | guided external-service setup |
| Claude Code | npm CLI package |

The wizard does not promise that a newly installed harness is benchmark-ready merely because its binary exists. It prints the harness-specific provider/configuration step that still needs to be satisfied.

## Isolated benchmark profile

The wizard can write:

```text
${XDG_CONFIG_HOME:-~/.config}/aios-bench/profile.json
```

The profile contains only non-secret benchmark routing metadata: model id, OpenAI-compatible endpoint, Anthropic-compatible endpoint and the environment keys AIOS-bench can apply automatically. API keys and auth tokens are deliberately not persisted there.

An explicit process environment variable always wins over the saved profile. This allows one-off experiments without editing persistent state.

When `--model` is omitted, normal benchmark commands may use the saved profile model. The saved OpenAI-compatible endpoint is exposed as `AIOS_BENCH_ENDPOINT`; the Anthropic endpoint is exposed as `AIOS_BENCH_CLAUDE_BASE_URL`.

## Recommended onboarding

```bash
aiosbench doctor --setup
aiosbench doctor --check
aiosbench --all smoke
```

If the profile contains a model id, the final smoke command can omit `--model`. For publication-grade comparisons, still record `AIOS_BENCH_MODEL_DIGEST`/`AIOS_BENCH_MODEL_FILE` and `AIOS_BENCH_INFERENCE_CONFIG` as described in the main README.
