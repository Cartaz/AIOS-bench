from __future__ import annotations

import inspect
from pathlib import Path

from core import app_controller

ROOT = Path(__file__).resolve().parents[1]


def test_core_app_controller_does_not_import_qt_runtime():
    source = inspect.getsource(app_controller)
    assert "PySide6" not in source
    assert "QThread" not in source
    assert "QObject" not in source


def test_frontend_backend_transport_is_centralized():
    app = (ROOT / "ui" / "web" / "app.js").read_text(encoding="utf-8")
    backend = (ROOT / "ui" / "web" / "backend.js").read_text(encoding="utf-8")
    index = (ROOT / "ui" / "web" / "index.html").read_text(encoding="utf-8")

    assert "QWebChannel" not in app
    assert "qt.webChannelTransport" not in app
    assert "QWebChannel" in backend
    assert "webChannelTransport" in backend
    assert '<script type="module" src="app.js"></script>' in index
