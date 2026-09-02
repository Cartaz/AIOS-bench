#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_VERSION="${AIOS_BENCH_NODE_VERSION:-24.20.0}"
SKIP_MANAGED_HARNESSES="${AIOS_BENCH_SKIP_MANAGED_HARNESSES:-0}"
VENV_DIR="$ROOT_DIR/.venv"
VENV_BIN="$VENV_DIR/bin"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] Python 3.12+ is required but '$PYTHON_BIN' was not found." >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(f"[ERROR] Python 3.12+ required, found {sys.version.split()[0]}")
PY

venv_is_compatible() {
  [[ -x "$VENV_BIN/python" ]] || return 1
  "$VENV_BIN/python" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
}

if ! venv_is_compatible; then
  echo "[INFO] Creating or repairing .venv with Python 3.12+"
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_BIN/python" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(f"[ERROR] .venv uses unsupported Python {sys.version.split()[0]}")
PY

"$VENV_BIN/python" -m pip install --upgrade pip
"$VENV_BIN/python" -m pip install -r requirements.txt -r requirements-dev.txt

"$VENV_BIN/python" - <<'PY'
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from core.app_controller import AppController
from ui.bridge import Bridge

assert QWebChannel and QWebEngineView and AppController and Bridge
print("[OK] Critical Python/Qt imports verified")
PY

if command -v bwrap >/dev/null 2>&1; then
  if bwrap --die-with-parent --new-session --ro-bind / / --proc /proc --dev /dev -- /bin/true >/dev/null 2>&1; then
    echo "[OK] bubblewrap sandbox verified (required for strict black-box reconstruction grading)"
  else
    echo "[WARN] bubblewrap is installed but cannot create a sandbox; strict black-box reconstruction grading will fail closed." >&2
  fi
else
  echo "[WARN] bubblewrap not found; strict black-box reconstruction grading is unavailable until it is installed and usable." >&2
fi

install_project_node() {
  local current=""
  if [[ -x "$VENV_BIN/node" ]]; then
    current="$("$VENV_BIN/node" --version 2>/dev/null || true)"
  fi
  if [[ "$current" == "v$NODE_VERSION" ]]; then
    echo "[OK] Project-local Node $current already installed"
    return
  fi

  echo "[INFO] Installing project-local Node v$NODE_VERSION into .venv"
  "$VENV_BIN/nodeenv" -p --node="$NODE_VERSION" --prebuilt
  current="$("$VENV_BIN/node" --version 2>/dev/null || true)"
  if [[ "$current" != "v$NODE_VERSION" ]]; then
    echo "[ERROR] Project-local Node verification failed: expected v$NODE_VERSION, found '${current:-missing}'." >&2
    exit 1
  fi
  echo "[OK] Project-local Node $current verified"
}

install_npm_harness() {
  local label="$1"
  local package="$2"
  local executable="$3"
  echo "[INFO] Installing $label into .venv"
  NPM_CONFIG_PREFIX="$VENV_DIR" "$VENV_BIN/npm" install -g "$package"
  if [[ ! -x "$VENV_BIN/$executable" ]]; then
    echo "[ERROR] $label installation completed without expected executable '$VENV_BIN/$executable'." >&2
    exit 1
  fi
  echo "[OK] $label available at $VENV_BIN/$executable"
}

if [[ "$SKIP_MANAGED_HARNESSES" == "1" ]]; then
  echo "[INFO] Managed harness bootstrap skipped by AIOS_BENCH_SKIP_MANAGED_HARNESSES=1"
else
  install_project_node
  export PATH="$VENV_BIN:${PATH:-}"
  install_npm_harness "Pi Agent" "@mariozechner/pi-coding-agent" "pi"
  install_npm_harness "OpenCode" "opencode-ai" "opencode"
  install_npm_harness "Letta Code" "@letta-ai/letta-code" "letta"
  install_npm_harness "Claude Code" "@anthropic-ai/claude-code" "claude"
  install_npm_harness "DeepSeek Harness" "@deepseek-ai/dsh@0.1.2-alpha.5" "dsh"
  echo "[OK] Managed project-local harnesses installed"
fi

cat <<'EOF'
[INFO] External harnesses remain intentionally separate:
       - Hermes Agent: official per-user installer is a remote install script.
       - Goose: official CLI installer is a remote release script.
       - Agent Zero: service/container lifecycle must be configured explicitly.
       AIOS-Bench does not execute remote shell pipelines, sudo, or start services silently.
EOF

echo "[OK] AIOS-Bench installed. Launch with: .venv/bin/python main.py"
