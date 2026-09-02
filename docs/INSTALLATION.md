# Installation and harness bootstrap

The canonical installation is:

```bash
chmod +x install.sh
./install.sh
```

The canonical launch command is:

```bash
.venv/bin/python main.py
```

`install.sh` resolves the repository root from any working directory, creates or repairs `.venv`, installs Python runtime/development requirements, verifies critical Python/Qt imports, provisions a project-local Node runtime and installs the managed npm harnesses into the same virtual environment. It does not require a system Node.js/npm installation.

## Project-local managed runtimes

The installer pins Node.js `24.20.0` inside `.venv` through `nodeenv` and installs:

- Pi Agent — `@earendil-works/pi-coding-agent@0.84.4`
- OpenCode — `opencode-ai@1.18.26`
- Letta Code — `@letta-ai/letta-code@0.31.11`
- Claude Code — `@anthropic-ai/claude-code@2.1.236`
- DeepSeek Harness — `@deepseek-ai/dsh@0.1.2-alpha.5`

Pi uses the current upstream `@earendil-works` package. Its npm lifecycle scripts are disabled by the managed install contract; the RPC/`--no-session` surface used by AIOS-Bench remains available.

AIOS-Bench-owned subprocesses prepend `.venv/bin` to `PATH`. Therefore project-local `node`, `npm` and harness executables win over ambient installations without requiring virtualenv activation.

The in-app Doctor **Installa** action uses the same `managed_runtimes` registry and installer as `install.sh`. It does not maintain a second unpinned npm path.

`AIOS_BENCH_NODE_VERSION` can override the managed Node version for explicit compatibility testing. `AIOS_BENCH_SKIP_MANAGED_HARNESSES=1` skips Node/harness downloads; the Python/Qt quality matrix uses this opt-out, while the separate `managed-bootstrap` CI job runs the ordinary installation path and verifies real project-local Node/npm/harness ownership.

## External runtimes

Three integrations remain intentionally external:

- **Hermes Agent** — upstream's supported Linux installer is a remote install script and owns a per-user runtime.
- **Goose** — upstream distributes the CLI through a remote release installer/binary path.
- **Agent Zero** — AIOS-Bench integrates with a separately running service/container.

AIOS-Bench does not silently execute `curl | bash`, request `sudo`, install Docker or start persistent services. Doctor displays official/manual guidance for these integrations.

Hermes and Goose are external only for **installation**: once their executable is available, the benchmark's saved local-inference profile pins their endpoint/provider/model at run time. Agent Zero remains external for both service lifecycle and remote model/service attestation.

## Local inference setup

After installation, open **Setup / Doctor** in the desktop application:

1. enter the OpenAI-compatible URL, normally `http://127.0.0.1:8080/v1`;
2. click **Trova modelli**;
3. select or enter the exact model id;
4. optionally enter an Anthropic-compatible URL for Claude Code;
5. click **Test e configura**.

The OpenAI profile is saved only if `/models` contains the selected id and a real `chat/completions` probe succeeds. A failed probe does not overwrite the previous valid profile. The optional Anthropic route is checked independently.

The saved profile is one AIOS-Bench setting, not a collection of modified personal harness configs. At task launch the benchmark generates isolated Pi/OpenCode configuration or environment-based bindings for Hermes, Goose, Letta, Claude and DeepSeek as appropriate. See `docs/harness-setup.md` for the exact per-harness contract.

## Bubblewrap

Bubblewrap is used for strict workspace/grader isolation. `install.sh` probes whether an installed `bwrap` can actually create a sandbox and reports a clear warning if not.

DeepSeek Harness additionally **requires** functional Bubblewrap for its isolated `DSH_HOME`; Doctor reports an installed DeepSeek runtime as blocked when Bubblewrap or a compatible Node version is missing.

## Verification

After installation, managed executables should exist under `.venv/bin`:

```bash
.venv/bin/node --version
.venv/bin/npm --version
.venv/bin/pi --version
.venv/bin/opencode --version
.venv/bin/letta --version
.venv/bin/claude --version
.venv/bin/dsh --version
```

The automated `managed-bootstrap` CI job exercises this same ordinary installation path rather than replacing it with mocked runtime discovery.
