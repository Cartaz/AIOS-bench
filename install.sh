#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
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
  [[ -x .venv/bin/python ]] || return 1
  .venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
}

if ! venv_is_compatible; then
  echo "[INFO] Creating or repairing .venv with Python 3.12+"
  rm -rf .venv
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(f"[ERROR] .venv uses unsupported Python {sys.version.split()[0]}")
PY

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/python - <<'PY'
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from core.app_controller import AppController
from ui.bridge import Bridge

assert QWebChannel and QWebEngineView and AppController and Bridge
print("[OK] Critical Python/Qt imports verified")
PY

echo "[OK] AIOS-Bench installed. Launch with: .venv/bin/python main.py"
