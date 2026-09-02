# Installation and harness bootstrap

The canonical installation remains:

```bash
chmod +x install.sh
./install.sh
```

`install.sh` owns the Python virtual environment and the project-local JavaScript toolchain. It does not require a system Node.js/npm installation.

## Project-local managed runtimes

The installer pins Node.js `24.20.0` inside `.venv` through `nodeenv` and installs the following CLI harnesses with `.venv` as the npm prefix:

- Pi Agent — `@mariozechner/pi-coding-agent`
- OpenCode — `opencode-ai`
- Letta Code — `@letta-ai/letta-code`
- Claude Code — `@anthropic-ai/claude-code`
- DeepSeek Harness — `@deepseek-ai/dsh@0.1.2-alpha.5`

AIOS-Bench subprocess ownership always prepends `.venv/bin` to child `PATH`. Therefore the canonical launch command:

```bash
.venv/bin/python main.py
```

finds project-local `node`, `npm` and managed harness executables without activating the virtual environment and without consulting a broken or incompatible system Node installation first.

`AIOS_BENCH_NODE_VERSION` can override the managed Node version for explicit testing. `AIOS_BENCH_SKIP_MANAGED_HARNESSES=1` skips Node/harness downloads; this is used by CI so the Python/Qt test matrix is not coupled to optional external registries.

## External runtimes

Three integrations remain intentionally external:

- **Hermes Agent** — upstream's supported Linux installer is a remote install script and owns a per-user runtime under `~/.hermes`.
- **Goose** — upstream distributes the CLI through a remote release installer/binaries.
- **Agent Zero** — AIOS-Bench integrates with a separately running service/container rather than a simple CLI package.

The canonical installer does not silently execute `curl | bash`, request `sudo`, install Docker, or start persistent services. These runtimes must be installed/configured explicitly when they are needed. Doctor remains available as a diagnostic/repair surface but is no longer required to install the project-local managed harnesses.

## Verification

After installation, the managed executables should exist under `.venv/bin`:

```bash
.venv/bin/node --version
.venv/bin/npm --version
.venv/bin/pi --version
.venv/bin/opencode --version
.venv/bin/letta --version
.venv/bin/claude --version
.venv/bin/dsh --version
```

DeepSeek Harness additionally requires functional Bubblewrap. `install.sh` probes Bubblewrap and reports a clear warning when its sandbox cannot be created.
